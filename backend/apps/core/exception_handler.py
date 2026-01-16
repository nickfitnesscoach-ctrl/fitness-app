"""
Custom exception handler for DRF.
Returns unified error format for all API exceptions.

Target format:
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": { ... }
  }
}
"""

import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import Throttled

from apps.core.exceptions import (
    FoodMindException,
    ValidationError,
    NotFoundError,
    PermissionDeniedError,
    BusinessLogicError,
    DailyLimitExceededError,
    ExternalServiceError,
)

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    Returns unified error format for all exceptions.
    """
    # Special handling for Throttled exception (rate limiting)
    if isinstance(exc, Throttled):
        return _handle_throttled_exception(exc, context)

    # Let DRF handle its own exceptions first
    response = exception_handler(exc, context)

    if response is not None:
        # Convert DRF errors to unified format
        return _convert_drf_error(response, exc)

    # Handle our domain exceptions
    if isinstance(exc, FoodMindException):
        return _handle_foodmind_exception(exc)

    # Log unexpected exceptions
    view = context.get('view', None)
    view_name = view.__class__.__name__ if view else 'Unknown'
    logger.exception(f"[{view_name}] Unhandled exception: {exc}")

    return Response(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Произошла внутренняя ошибка",
                "details": {}
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def _handle_throttled_exception(exc: Throttled, context):
    """
    Handle DRF Throttled exception with AI Error Contract.
    Returns structured error response for rate limiting.
    """
    from apps.ai.error_contract import AIErrorRegistry
    import uuid

    # Get wait time from exception
    wait_seconds = int(exc.wait) if exc.wait else 60

    # Get request_id from context if available
    request = context.get('request')
    request_id = request.headers.get('X-Request-ID') if request else None
    if not request_id:
        request_id = uuid.uuid4().hex

    error_def = AIErrorRegistry.RATE_LIMIT

    # Override retry_after_sec with actual wait time from throttle
    error_data = error_def.to_dict(trace_id=request_id)
    error_data['retry_after_sec'] = wait_seconds

    logger.warning(
        "[Throttle] Rate limit exceeded: user=%s wait=%s request_id=%s",
        getattr(request, 'user', None),
        wait_seconds,
        request_id,
    )

    response = Response(error_data, status=status.HTTP_429_TOO_MANY_REQUESTS)
    response['X-Request-ID'] = request_id
    if wait_seconds:
        response['Retry-After'] = str(wait_seconds)

    return response


def _convert_drf_error(response, exc):
    """Convert DRF error response to unified format."""
    import uuid
    from apps.ai.error_contract import AIErrorRegistry

    data = response.data

    # Already in our format
    if isinstance(data, dict) and "error" in data and isinstance(data["error"], dict):
        return response

    # DRF validation errors: { "field": ["error1", "error2"] }
    if isinstance(data, dict):
        # Check for field validation errors
        has_field_errors = any(
            isinstance(v, list) for v in data.values()
            if not isinstance(v, str)
        )

        if has_field_errors:
            # Detect image-specific validation errors
            image_fields = {"image", "file", "photo", "upload", "normalized_image"}
            error_field = None
            error_message = None

            for field, errors in data.items():
                if isinstance(errors, list) and errors:
                    error_field = field
                    error_message = errors[0]
                    break
                elif isinstance(errors, str):
                    error_field = field
                    error_message = errors
                    break

            # If error is image-related, return AI Error Contract format
            if error_field and error_field.lower() in image_fields:
                trace_id = uuid.uuid4().hex
                error_def = AIErrorRegistry.INVALID_IMAGE

                # Use AIErrorResponse format instead of generic VALIDATION_ERROR
                response.data = error_def.to_dict(trace_id=trace_id)
                response['X-Request-ID'] = trace_id

                logger.warning(
                    "[ValidationError->AIError] Image validation failed: field=%s error=%s trace_id=%s",
                    error_field,
                    error_message,
                    trace_id,
                )

                return response

            # Non-image validation errors: use legacy format
            first_error = f"{error_field}: {error_message}" if error_field else "Ошибка валидации данных"

            response.data = {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": first_error,
                    "details": data
                }
            }
            return response

        # DRF detail errors: { "detail": "message" }
        if "detail" in data:
            response.data = {
                "error": {
                    "code": _status_to_code(response.status_code),
                    "message": str(data["detail"]),
                    "details": {}
                }
            }
            return response

        # Non-field errors
        if "non_field_errors" in data:
            errors = data["non_field_errors"]
            message = errors[0] if isinstance(errors, list) and errors else str(errors)
            response.data = {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": message,
                    "details": data
                }
            }
            return response

    # List of errors (rare case)
    if isinstance(data, list):
        response.data = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": data[0] if data else "Ошибка валидации",
                "details": {"errors": data}
            }
        }
        return response

    return response


def _handle_foodmind_exception(exc: FoodMindException):
    """Handle FoodMindException subclasses."""
    status_code = _get_status_code(exc)

    return Response(
        {
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        },
        status=status_code
    )


def _get_status_code(exc: FoodMindException) -> int:
    """Map exception type to HTTP status code."""
    if isinstance(exc, ValidationError):
        return status.HTTP_400_BAD_REQUEST
    if isinstance(exc, NotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(exc, PermissionDeniedError):
        return status.HTTP_403_FORBIDDEN
    if isinstance(exc, DailyLimitExceededError):
        return status.HTTP_429_TOO_MANY_REQUESTS
    if isinstance(exc, BusinessLogicError):
        return status.HTTP_409_CONFLICT
    if isinstance(exc, ExternalServiceError):
        return status.HTTP_502_BAD_GATEWAY
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _status_to_code(status_code: int) -> str:
    """Map HTTP status code to error code."""
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(status_code, "ERROR")
