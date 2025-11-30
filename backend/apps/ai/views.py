"""
Views for AI app.
"""

import base64
import logging
import time

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
from apps.ai_proxy.service import AIProxyRecognitionService
from apps.ai_proxy.exceptions import AIProxyError, AIProxyValidationError, AIProxyTimeoutError
from .throttles import AIRecognitionPerMinuteThrottle, AIRecognitionPerDayThrottle
from apps.billing.services import get_effective_plan_for_user
from apps.billing.usage import DailyUsage

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
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

        if request.FILES.get("image"):
            # Multipart file upload - convert to data URL
            logger.info(
                f"Received multipart image: name={request.FILES['image'].name}, "
                f"size={request.FILES['image'].size} bytes, "
                f"content_type={request.FILES['image'].content_type}"
            )
            try:
                data["image"] = self._file_to_data_url(request.FILES["image"])
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

        serializer = AIRecognitionRequestSerializer(data=data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        image_data_url = serializer.validated_data['image']
        description = serializer.validated_data.get('description', '')
        comment = serializer.validated_data.get('comment', '')

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
            # Initialize AI Proxy service (replaces old OpenRouter service)
            ai_service = AIProxyRecognitionService()

            # Recognize food items
            recognition_start = time.time()
            logger.info(f"Starting AI Proxy recognition for user {request.user.username}")
            result = ai_service.recognize_food(
                image_data_url,
                user_description=description,
                user_comment=comment
            )
            recognition_elapsed = time.time() - recognition_start

            logger.info(
                f"AI recognition successful for user {request.user.username}. "
                f"Found {len(result.get('recognized_items', []))} items, "
                f"recognition_time={recognition_elapsed:.2f}s"
            )

            # Increment photo usage counter after successful recognition
            DailyUsage.objects.increment_photo_requests(request.user)
            logger.info(
                f"Incremented photo counter for user {request.user.username}. "
                f"Total today: {usage.photo_ai_requests + 1}"
            )

            # Use serializer to add summary/totals
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
