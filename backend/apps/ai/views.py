"""
Views for AI app.
"""

import base64
import logging
import time
from datetime import date

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    AIRecognitionRequestSerializer,
    AIRecognitionResponseSerializer,
    RecognizedItemSerializer
)
from .services import recognize_and_save_meal
from apps.ai_proxy.exceptions import AIProxyError, AIProxyValidationError, AIProxyTimeoutError
from .throttles import AIRecognitionPerMinuteThrottle, AIRecognitionPerDayThrottle
from apps.billing.services import get_effective_plan_for_user
from apps.billing.usage import DailyUsage
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@extend_schema(tags=['AI Recognition'])
class AIRecognitionView(APIView):
    """
    POST /api/v1/ai/recognize/ - Распознать блюда на фотографии

    Принимает изображение (multipart/form-data или Base64) и возвращает список распознанных блюд с КБЖУ.

    **Лимиты:**
    - 10 запросов в минуту с одного IP
    - 100 запросов в день с одного IP

    **Бизнес-логика:**
    1. Валидация изображения (multipart file или Base64, JPEG/PNG)
    2. Отправка изображения в LLM-модель (OpenRouter + Gemini 2.0)
    3. Парсинг JSON-ответа (до 3 попыток при ошибке)
    4. Возврат списка распознанных блюд с КБЖУ

    **Безопасность:**
    - Требуется JWT аутентификация
    - Rate limiting по IP адресу
    - Валидация формата изображения
    - Валидация структуры JSON ответа
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [AIRecognitionPerMinuteThrottle, AIRecognitionPerDayThrottle]
    MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

    def _file_to_data_url(self, image_file):
        """Convert uploaded file to data URL for serializer validation."""
        if not image_file or getattr(image_file, "size", 0) <= 0:
            raise ValueError("Image file is empty")

        if image_file.size > self.MAX_IMAGE_SIZE_BYTES:
            raise ValueError(f"Image exceeds maximum allowed size of {self.MAX_IMAGE_SIZE_BYTES // (1024 * 1024)}MB")

        content_type = getattr(image_file, "content_type", None) or "application/octet-stream"
        if not content_type.startswith("image/"):
            raise ValueError(f"Unsupported content type: {content_type}")

        try:
            image_file.seek(0)
            encoded_bytes = image_file.read()
        except Exception as exc:
            logger.exception(f"Failed to read image file: {exc}")
            raise ValueError("Failed to read image file")

        if not encoded_bytes:
            raise ValueError("Failed to read image bytes from uploaded file")

        encoded = base64.b64encode(encoded_bytes).decode("utf-8")
        return f"data:{content_type};base64,{encoded}"

    @extend_schema(
        request=AIRecognitionRequestSerializer,
        responses={
            200: AIRecognitionResponseSerializer,
            400: OpenApiResponse(description="Некорректные данные (неверный формат изображения или отсутствует)"),
            429: OpenApiResponse(description="Превышен лимит запросов (10/мин или 100/день или дневной лимит по тарифу)"),
            500: OpenApiResponse(description="Ошибка AI Proxy распознавания"),
        },
        summary="Распознать блюда на фото",
        description="""
Отправь изображение еды в multipart/form-data или Base64 и получи список распознанных блюд с КБЖУ.

**Параметры:**
- `image` (обязательно): Изображение в формате multipart/form-data (файл) или Base64 (data:image/jpeg;base64,...)
- `description` (опционально): Дополнительное описание блюд (устаревшее поле)
- `comment` (опционально): Комментарий пользователя о блюде (новое поле, передается в AI Proxy)
- `date` (опционально): Дата приёма пищи

**Обработка:**
Изображение отправляется в AI Proxy сервис (внутренний сервис EatFit24), который использует OpenRouter для распознавания.
        """
    )
    def post(self, request):
        """Handle POST request for AI food recognition."""
        view_start_time = time.time()
        logger.info(f"AI recognition request START for user {request.user.username}")

        # Handle multipart/form-data file upload
        # Convert uploaded file to data URL if present
        data = {}

        # Copy text fields (avoiding file objects that can't be pickled)
        for key, value in request.data.items():
            if key != 'image':  # Skip image field, we'll handle it separately
                data[key] = value

        image_file = None
        image_data_url = None

        if request.FILES.get("image"):
            # Multipart file upload
            image_file = request.FILES["image"]
            logger.info(
                f"Received multipart image: name={image_file.name}, "
                f"size={image_file.size} bytes, "
                f"content_type={image_file.content_type}"
            )
            try:
                image_data_url = self._file_to_data_url(image_file)
                data["image"] = image_data_url
                logger.info("Successfully converted multipart file to data URL")
            except ValueError as e:
                logger.warning(f"Invalid multipart file: {e}")
                return Response(
                    {
                        "error": "INVALID_IMAGE",
                        "detail": str(e)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Failed to convert multipart file: {e}", exc_info=True)
                return Response(
                    {
                        "error": "AI_SERVICE_ERROR",
                        "detail": "Сервис распознавания временно недоступен. Попробуйте позже"
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        elif 'image' in request.data:
            # Base64 image already in request.data
            image_data_url = request.data['image']
            data['image'] = image_data_url
            
            # Convert base64 to ContentFile for saving to model
            try:
                format, imgstr = image_data_url.split(';base64,') 
                ext = format.split('/')[-1] 
                image_file = ContentFile(base64.b64decode(imgstr), name=f'meal_{int(time.time())}.{ext}')
            except Exception as e:
                logger.warning(f"Failed to convert base64 to file: {e}")
                # We can continue without saving file if strictly necessary, but requirement says save it.
                # If base64 is invalid, serializer will catch it anyway.

        serializer = AIRecognitionRequestSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure we have a valid image_data_url from serializer (it validates it)
        image_data_url = serializer.validated_data['image']
        description = serializer.validated_data.get('description', '')
        comment = serializer.validated_data.get('comment', '')
        meal_date = serializer.validated_data.get('date', date.today())
        meal_type = serializer.validated_data.get('meal_type', 'SNACK')

        # Check daily photo limit based on user's subscription plan
        plan = get_effective_plan_for_user(request.user)
        usage = DailyUsage.objects.get_today(request.user)

        if plan.daily_photo_limit is not None and usage.photo_ai_requests >= plan.daily_photo_limit:
            logger.warning(
                f"User {request.user.username} exceeded daily photo limit. "
                f"Plan: {plan.name}, Limit: {plan.daily_photo_limit}, Used: {usage.photo_ai_requests}"
            )
            return Response(
                {
                    "error": "DAILY_LIMIT_REACHED",
                    "detail": f"Превышен дневной лимит {plan.daily_photo_limit} фото. Обновите тариф для безлимитного распознавания.",
                    "current_plan": plan.name,
                    "daily_limit": plan.daily_photo_limit,
                    "used_today": usage.photo_ai_requests
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        try:
            # Call service to create meal, recognize and save food items
            service_result = recognize_and_save_meal(
                user=request.user,
                image_file=image_file,
                image_data_url=image_data_url,
                meal_type=meal_type,
                meal_date=meal_date,
                description=description,
                comment=comment
            )

            meal = service_result['meal']
            recognized_items = service_result['recognized_items']

            # Build response
            result = {
                'meal_id': meal.id,
                'recognized_items': recognized_items,
                'photo_url': request.build_absolute_uri(meal.photo.url) if meal.photo else None
            }

            response_serializer = AIRecognitionResponseSerializer(result)

            view_total = time.time() - view_start_time
            logger.info(
                f"AI recognition request COMPLETED for user {request.user.username}, "
                f"total_view_time={view_total:.2f}s"
            )

            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK
            )

        except AIProxyTimeoutError as e:
            view_total = time.time() - view_start_time
            logger.error(
                f"AI Proxy timeout for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s"
            )
            return Response(
                {
                    "error": "AI_SERVICE_TIMEOUT",
                    "detail": "Сервис распознавания не ответил вовремя. Попробуйте позже или используйте фото меньшего размера.",
                    "timeout": True
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        except AIProxyValidationError as e:
            view_total = time.time() - view_start_time
            logger.error(
                f"AI Proxy validation error for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s"
            )
            return Response(
                {
                    "error": "INVALID_IMAGE",
                    "detail": "Некорректный формат изображения. Проверьте data URL и попробуйте снова"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        except AIProxyError as e:
            view_total = time.time() - view_start_time
            logger.error(
                f"AI Proxy error for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s",
                exc_info=True
            )
            return Response(
                {
                    "error": "AI_PROXY_ERROR",
                    "detail": "Сервис распознавания временно недоступен. Попробуйте позже"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except ValueError as e:
            view_total = time.time() - view_start_time
            logger.error(
                f"AI recognition validation error for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s"
            )
            return Response(
                {
                    "error": "INVALID_IMAGE",
                    "detail": "Проверьте формат изображения и попробуйте снова"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            view_total = time.time() - view_start_time
            logger.error(
                f"AI recognition unexpected error for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s",
                exc_info=True
            )
            return Response(
                {
                    "error": "AI_SERVICE_ERROR",
                    "detail": "Сервис распознавания временно недоступен. Попробуйте позже"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
