"""
Views for AI app.
"""

import logging

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
from .services import AIRecognitionService
from apps.ai_proxy.service import AIProxyRecognitionService
from apps.ai_proxy.exceptions import AIProxyError, AIProxyValidationError
from .throttles import AIRecognitionPerMinuteThrottle, AIRecognitionPerDayThrottle
from apps.billing.services import get_effective_plan_for_user
from apps.billing.usage import DailyUsage

logger = logging.getLogger(__name__)


@extend_schema(tags=['AI Recognition'])
class AIRecognitionView(APIView):
    """
    POST /api/v1/ai/recognize/ - Распознать блюда на фотографии

    Принимает изображение в формате Base64 и возвращает список распознанных блюд с КБЖУ.

    **Лимиты:**
    - 10 запросов в минуту с одного IP
    - 100 запросов в день с одного IP

    **Бизнес-логика:**
    1. Валидация изображения (Base64, JPEG/PNG)
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
Отправь изображение еды в Base64 и получи список распознанных блюд с КБЖУ.

**Параметры:**
- `image` (обязательно): Изображение в формате Base64 (data:image/jpeg;base64,...)
- `description` (опционально): Дополнительное описание блюд (устаревшее поле)
- `comment` (опционально): Комментарий пользователя о блюде (новое поле, передается в AI Proxy)
- `date` (опционально): Дата приёма пищи

**Обработка:**
Изображение отправляется в AI Proxy сервис (внутренний сервис EatFit24), который использует OpenRouter для распознавания.
        """
    )
    def post(self, request):
        """Handle POST request for AI food recognition."""
        serializer = AIRecognitionRequestSerializer(data=request.data)

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
            logger.info(f"Starting AI Proxy recognition for user {request.user.username}")
            result = ai_service.recognize_food(
                image_data_url,
                user_description=description,
                user_comment=comment
            )

            logger.info(
                f"AI recognition successful for user {request.user.username}. "
                f"Found {len(result.get('recognized_items', []))} items"
            )

            # Increment photo usage counter after successful recognition
            DailyUsage.objects.increment_photo_requests(request.user)
            logger.info(
                f"Incremented photo counter for user {request.user.username}. "
                f"Total today: {usage.photo_ai_requests + 1}"
            )

            # Use serializer to add summary/totals
            response_serializer = AIRecognitionResponseSerializer(result)
            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK
            )

        except AIProxyValidationError as e:
            logger.error(f"AI Proxy validation error: {e}")
            return Response(
                {
                    "error": "INVALID_IMAGE",
                    "detail": "Некорректный формат изображения. Проверьте data URL и попробуйте снова"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        except AIProxyError as e:
            logger.error(f"AI Proxy error: {e}", exc_info=True)
            return Response(
                {
                    "error": "AI_PROXY_ERROR",
                    "detail": "Сервис распознавания временно недоступен. Попробуйте позже"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except ValueError as e:
            logger.error(f"AI recognition validation error: {e}")
            return Response(
                {
                    "error": "INVALID_IMAGE",
                    "detail": "Проверьте формат изображения и попробуйте снова"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.error(f"AI recognition unexpected error: {e}", exc_info=True)
            return Response(
                {
                    "error": "AI_SERVICE_ERROR",
                    "detail": "Сервис распознавания временно недоступен. Попробуйте позже"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
