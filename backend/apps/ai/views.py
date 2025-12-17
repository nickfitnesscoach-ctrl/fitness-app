"""
Views for AI app.
"""

import base64
import logging
import time
from datetime import date

from django.conf import settings
from django.core.files.base import ContentFile
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
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
from .throttles import AIRecognitionPerMinuteThrottle, AIRecognitionPerDayThrottle, TaskStatusThrottle
from apps.billing.services import get_effective_plan_for_user
from apps.billing.usage import DailyUsage
from apps.nutrition.models import Meal
# B-013: Image compression
from apps.common.image_utils import compress_image

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
            original_size = image_file.size
            logger.info(
                f"Received multipart image: name={image_file.name}, "
                f"size={image_file.size} bytes, "
                f"content_type={image_file.content_type}"
            )
            try:
                # B-013: Compress image before processing
                image_file = compress_image(image_file)
                compressed_size = image_file.size if hasattr(image_file, 'size') else len(image_file.read())
                if hasattr(image_file, 'seek'):
                    image_file.seek(0)
                logger.info(f"Image compression: {original_size} -> {compressed_size} bytes")
                
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
        # [SECURITY FIX 2024-12] Атомарная проверка + инкремент
        # Раньше проверка и инкремент были отдельны → race condition.
        # Теперь используем check_and_increment_if_allowed для атомарности.
        plan = get_effective_plan_for_user(request.user)
        allowed, used_count = DailyUsage.objects.check_and_increment_if_allowed(
            user=request.user,
            limit=plan.daily_photo_limit,
            amount=1
        )

        if not allowed:
            logger.warning(
                f"User {request.user.username} exceeded daily photo limit. "
                f"Plan: {plan.name}, Limit: {plan.daily_photo_limit}, Used: {used_count}"
            )
            return Response(
                {
                    "error": "DAILY_LIMIT_REACHED",
                    "detail": f"Превышен дневной лимит {plan.daily_photo_limit} фото. Обновите тариф для безлимитного распознавания.",
                    "current_plan": plan.name,
                    "daily_limit": plan.daily_photo_limit,
                    "used_today": used_count
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Check if async mode is enabled
        async_enabled = getattr(settings, 'AI_ASYNC_ENABLED', False)
        
        if async_enabled:
            # ASYNC MODE: Create meal, send task to Celery, return immediately
            return self._handle_async_recognition(
                request=request,
                image_file=image_file,
                image_data_url=image_data_url,
                meal_type=meal_type,
                meal_date=meal_date,
                description=description,
                comment=comment,
                view_start_time=view_start_time
            )
        
        # SYNC MODE: Process immediately (existing behavior)
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

    def _handle_async_recognition(
        self,
        request,
        image_file,
        image_data_url,
        meal_type,
        meal_date,
        description,
        comment,
        view_start_time
    ):
        """
        Handle async recognition: create meal, dispatch Celery task, return immediately.
        """
        from .tasks import recognize_food_async
        
        try:
            # 1. Create Meal with photo (without food items yet)
            if image_file:
                image_file.seek(0)
            
            meal = Meal.objects.create(
                user=request.user,
                meal_type=meal_type,
                date=meal_date,
                photo=image_file
            )
            
            logger.info(f"Created Meal id={meal.id} for async processing, user={request.user.username}")
            
            # 2. Dispatch Celery task
            task = recognize_food_async.delay(
                meal_id=str(meal.id),
                image_data_url=image_data_url,
                user_id=request.user.id,
                description=description,
                comment=comment
            )
            
            view_total = time.time() - view_start_time
            logger.info(
                f"Async AI recognition task dispatched for user {request.user.username}, "
                f"meal_id={meal.id}, task_id={task.id}, dispatch_time={view_total:.3f}s"
            )
            
            # 3. Return immediately with 202 Accepted
            return Response(
                {
                    "meal_id": str(meal.id),
                    "task_id": task.id,
                    "status": "processing",
                    "message": "Изображение отправлено на распознавание"
                },
                status=status.HTTP_202_ACCEPTED
            )
            
        except Exception as e:
            view_total = time.time() - view_start_time
            logger.error(
                f"Failed to dispatch async recognition for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s",
                exc_info=True
            )
            return Response(
                {
                    "error": "AI_SERVICE_ERROR",
                    "detail": "Не удалось запустить распознавание. Попробуйте позже."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=['AI Recognition'])
class TaskStatusView(APIView):
    """
    GET /api/v1/ai/task/<task_id>/ - Проверить статус задачи распознавания
    
    Возвращает текущий статус Celery задачи и результат при завершении.
    """
    
    permission_classes = [IsAuthenticated]
    # B-004 FIX: Rate limit polling to prevent Redis overload
    throttle_classes = [TaskStatusThrottle]
    
    @extend_schema(
        summary="Проверить статус задачи распознавания",
        description="""
Возвращает состояние асинхронной задачи распознавания.

**Возможные состояния (state):**
- `PENDING` - Задача в очереди, ожидает выполнения
- `STARTED` - Задача начала выполняться
- `RETRY` - Задача перезапускается после ошибки
- `SUCCESS` - Задача успешно завершена (результат в поле result)
- `FAILURE` - Задача завершилась с ошибкой

**При SUCCESS возвращается result с:**
- meal_id, recognized_items[], totals{}
        """,
        parameters=[
            OpenApiParameter(
                name='task_id',
                type=str,
                location=OpenApiParameter.PATH,
                description='ID задачи Celery'
            )
        ],
        responses={
            200: OpenApiResponse(description="Статус задачи"),
            404: OpenApiResponse(description="Задача не найдена"),
        }
    )
    def get(self, request, task_id):
        """Get task status by task_id."""
        from celery.result import AsyncResult
        
        try:
            task_result = AsyncResult(task_id)
            
            response_data = {
                "task_id": task_id,
                "state": task_result.state,
            }
            
            if task_result.state == 'SUCCESS':
                response_data["result"] = task_result.result
            elif task_result.state == 'FAILURE':
                response_data["error"] = str(task_result.result) if task_result.result else "Unknown error"
            elif task_result.state == 'PENDING':
                response_data["message"] = "Задача ожидает выполнения"
            elif task_result.state == 'STARTED':
                response_data["message"] = "Задача выполняется"
            elif task_result.state == 'RETRY':
                response_data["message"] = "Задача перезапускается"
            
            logger.debug(f"Task {task_id} status: {task_result.state}")
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}", exc_info=True)
            return Response(
                {
                    "error": "TASK_ERROR",
                    "detail": "Не удалось получить статус задачи"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
