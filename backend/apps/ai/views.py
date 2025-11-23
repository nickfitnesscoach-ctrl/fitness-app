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
from .throttles import AIRecognitionPerMinuteThrottle, AIRecognitionPerDayThrottle

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
            429: OpenApiResponse(description="Превышен лимит запросов (10/мин или 100/день)"),
            500: OpenApiResponse(description="Ошибка AI распознавания (после 3 попыток)"),
        },
        summary="Распознать блюда на фото",
        description="Отправь изображение еды в Base64 и получи список распознанных блюд с КБЖУ"
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

        try:
            # Initialize AI service
            ai_service = AIRecognitionService()

            # Recognize food items
            logger.info(f"Starting AI recognition for user {request.user.username}")
            result = ai_service.recognize_food(image_data_url, user_description=description)

            logger.info(
                f"AI recognition successful for user {request.user.username}. "
                f"Found {len(result.get('recognized_items', []))} items"
            )

            # Use serializer to add summary/totals
            response_serializer = AIRecognitionResponseSerializer(result)
            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK
            )

        except ValueError as e:
            logger.error(f"AI recognition validation error: {e}")
            return Response(
                {
                    "error": "Ошибка обработки изображения",
                    "detail": "Проверьте формат изображения и попробуйте снова"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.error(f"AI recognition unexpected error: {e}", exc_info=True)
            return Response(
                {
                    "error": "Ошибка AI распознавания",
                    "detail": "Не удалось распознать изображение. Попробуйте ещё раз."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
