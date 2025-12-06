"""
Base exception classes for FoodMind AI.

Hierarchy:
    FoodMindException (base)
    ├── ValidationError - input/data validation errors
    ├── NotFoundError - resource not found
    ├── PermissionDeniedError - access denied
    ├── BusinessLogicError - domain/business rule violations
    │   ├── DailyLimitExceededError
    │   ├── SubscriptionRequiredError
    │   └── InvalidStateError
    └── ExternalServiceError - third-party service failures
        ├── AIServiceError
        └── PaymentServiceError
"""


class FoodMindException(Exception):
    """Base exception for all FoodMind AI errors."""
    
    default_message = "An error occurred"
    default_code = "error"
    
    def __init__(self, message=None, code=None, details=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self):
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# Validation errors
class ValidationError(FoodMindException):
    """Input or data validation failed."""
    default_message = "Validation error"
    default_code = "validation_error"


# Not found errors
class NotFoundError(FoodMindException):
    """Requested resource not found."""
    default_message = "Resource not found"
    default_code = "not_found"


class UserNotFoundError(NotFoundError):
    """User not found."""
    default_message = "User not found"
    default_code = "user_not_found"


class PlanNotFoundError(NotFoundError):
    """Subscription plan not found."""
    default_message = "Subscription plan not found"
    default_code = "plan_not_found"


# Permission errors
class PermissionDeniedError(FoodMindException):
    """Access to resource denied."""
    default_message = "Permission denied"
    default_code = "permission_denied"


# Business logic errors
class BusinessLogicError(FoodMindException):
    """Business rule violation."""
    default_message = "Business logic error"
    default_code = "business_error"


class DailyLimitExceededError(BusinessLogicError):
    """Daily limit for operation exceeded."""
    default_message = "Daily limit exceeded"
    default_code = "daily_limit_exceeded"


class SubscriptionRequiredError(BusinessLogicError):
    """Operation requires active subscription."""
    default_message = "Active subscription required"
    default_code = "subscription_required"


class InvalidStateError(BusinessLogicError):
    """Object is in invalid state for operation."""
    default_message = "Invalid state for this operation"
    default_code = "invalid_state"


# External service errors
class ExternalServiceError(FoodMindException):
    """External service failure."""
    default_message = "External service error"
    default_code = "external_service_error"


class AIServiceError(ExternalServiceError):
    """AI recognition service failure."""
    default_message = "AI service unavailable"
    default_code = "ai_service_error"


class AIServiceTimeoutError(AIServiceError):
    """AI service timeout."""
    default_message = "AI service timeout"
    default_code = "ai_service_timeout"


class PaymentServiceError(ExternalServiceError):
    """Payment service failure."""
    default_message = "Payment service error"
    default_code = "payment_service_error"
