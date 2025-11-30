"""
Views for AI app.
"""

import base64
import logging
import time
from typing import Iterable

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
    MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

    @staticmethod
    def _log_client_response(http_status: int, payload: dict):
        logger.info("AI response to client: status=%s, error=%s", http_status, payload.get("error"))

    @staticmethod
    def _log_request_files(files: Iterable[str]):
        file_list = list(files)
        if file_list:
            logger.info(f"Incoming multipart files: {file_list}")
        else:
            logger.info("No multipart files received")

    @staticmethod
    def _log_request_summary(request):
        logger.info(
            "AI recognize request: FILE_KEYS=%s, CONTENT_TYPES=%s, SIZES=%s",
            list(request.FILES.keys()),
            [getattr(f, "content_type", None) for f in request.FILES.values()],
            [getattr(f, "size", None) for f in request.FILES.values()],
        )

    def _file_to_data_url(self, image_file):
        """Convert uploaded file to data URL for existing serializer validation."""
        if getattr(image_file, "size", 0) <= 0:
            raise ValueError("Image file is empty")

        if image_file.size > self.MAX_IMAGE_SIZE_BYTES:
            raise ValueError("Image exceeds maximum allowed size of 10MB")

        content_type = image_file.content_type or "application/octet-stream"
        if not content_type.startswith("image/"):
            raise ValueError(f"Unsupported content type: {content_type}")

        try:
            image_file.seek(0)
            encoded_bytes = image_file.read()
        except Exception as exc:
            logger.exception("AI image convert failed during read: %s", exc)
            raise

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
Отправь изображение еды в Base64 и получи список распознанных блюд с КБЖУ.

**Параметры:**
- `image` (обязательно): Изображение в формате multipart/form-data (ключ `image`) или Base64 (data:image/jpeg;base64,...)
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

        self._log_request_summary(request)

        # Log multipart payload details
        self._log_request_files(request.FILES.keys())
        if request.FILES.get("image"):
            image_file = request.FILES["image"]
            logger.info(
                "Received image file: name=%s, size=%s bytes, content_type=%s",
                getattr(image_file, "name", "<unknown>"),
                getattr(image_file, "size", "<unknown>"),
                getattr(image_file, "content_type", "<unknown>"),
            )

        data = request.data.copy()

        if not data.get("image"):
            if request.FILES.get("image"):
                try:
                    data["image"] = self._file_to_data_url(request.FILES["image"])
                except ValueError as exc:
                    logger.warning("AI INVALID_IMAGE: %s", exc)
                    payload = {
                        "error": "INVALID_IMAGE",
                        "detail": str(exc),
                    }
                    self._log_client_response(status.HTTP_400_BAD_REQUEST, payload)
                    return Response(
                        payload,
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                except Exception as exc:
                    logger.exception("AI image conversion failed: %s", exc)
                    payload = {
                        "error": "AI_SERVICE_ERROR",
                        "detail": "Сервис распознавания временно недоступен. Попробуйте позже",
                    }
                    self._log_client_response(status.HTTP_502_BAD_GATEWAY, payload)
                    return Response(payload, status=status.HTTP_502_BAD_GATEWAY)
            else:
                logger.warning("AI MISSING_IMAGE: no file in request.FILES and no image field")
                payload = {
                    "error": "MISSING_IMAGE",
                    "detail": "Изображение обязательно",
                }
                self._log_client_response(status.HTTP_400_BAD_REQUEST, payload)
                return Response(
                    payload,
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = AIRecognitionRequestSerializer(data=data)

        if not serializer.is_valid():
            logger.warning("AI INVALID_IMAGE: serializer validation failed: %s", serializer.errors)
            payload = {
                "error": "INVALID_IMAGE",
                "detail": serializer.errors.get("image", ["Некорректные данные запроса"])[0],
                "fields": serializer.errors,
            }
            self._log_client_response(status.HTTP_400_BAD_REQUEST, payload)
            return Response(
                payload,
                status=status.HTTP_400_BAD_REQUEST,
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

            if not result.get("recognized_items"):
                logger.info(
                    "AI NO_FOOD_DETECTED for user %s: empty recognition result after %.2fs",
                    request.user.username,
                    recognition_elapsed,
                )
                payload = {
                    "error": "NO_FOOD_DETECTED",
                    "detail": "Мы не нашли на фото еду. Попробуйте другое изображение",
                }
                self._log_client_response(status.HTTP_200_OK, payload)
                return Response(
                    payload,
                    status=status.HTTP_200_OK,
                )

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
            payload = {
                "error": "AI_SERVICE_TIMEOUT",
                "detail": "Сервис распознавания не ответил вовремя. Попробуйте позже или используйте фото меньшего размера.",
                "timeout": True
            }
            self._log_client_response(status.HTTP_503_SERVICE_UNAVAILABLE, payload)
            return Response(
                payload,
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        except AIProxyValidationError as e:
            view_total = time.time() - view_start_time
            logger.warning(
                f"AI INVALID_IMAGE from AI Proxy for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s"
            )
            payload = {
                "error": "INVALID_IMAGE",
                "detail": "Некорректный формат изображения. Проверьте data URL и попробуйте снова"
            }
            self._log_client_response(status.HTTP_400_BAD_REQUEST, payload)
            return Response(
                payload,
                status=status.HTTP_400_BAD_REQUEST
            )

        except AIProxyError as e:
            view_total = time.time() - view_start_time
            logger.error(
                f"AI Proxy error for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s",
                exc_info=True
            )
            payload = {
                "error": "AI_SERVICE_ERROR",
                "detail": "Сервис распознавания временно недоступен. Попробуйте позже"
            }
            self._log_client_response(status.HTTP_502_BAD_GATEWAY, payload)
            return Response(
                payload,
                status=status.HTTP_502_BAD_GATEWAY
            )

        except ValueError as e:
            view_total = time.time() - view_start_time
            logger.warning(
                f"AI INVALID_IMAGE during recognition for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s"
            )
            payload = {
                "error": "INVALID_IMAGE",
                "detail": "Проверьте формат изображения и попробуйте снова"
            }
            self._log_client_response(status.HTTP_400_BAD_REQUEST, payload)
            return Response(
                payload,
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            view_total = time.time() - view_start_time
            logger.error(
                f"AI recognition unexpected error for user {request.user.username}: {e}, "
                f"total_view_time={view_total:.2f}s",
                exc_info=True
            )
            payload = {
                "error": "AI_SERVICE_ERROR",
                "detail": "Сервис распознавания временно недоступен. Попробуйте позже"
            }
            self._log_client_response(status.HTTP_500_INTERNAL_SERVER_ERROR, payload)
            return Response(
                payload,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
