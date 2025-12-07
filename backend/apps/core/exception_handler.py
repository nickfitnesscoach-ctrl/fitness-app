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


def _convert_drf_error(response, exc):
    """Convert DRF error response to unified format."""
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
            # Build human-readable message from first error
            first_error = None
            for field, errors in data.items():
                if isinstance(errors, list) and errors:
                    first_error = f"{field}: {errors[0]}"
                    break
                elif isinstance(errors, str):
                    first_error = f"{field}: {errors}"
                    break
            
            response.data = {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": first_error or "Ошибка валидации данных",
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
