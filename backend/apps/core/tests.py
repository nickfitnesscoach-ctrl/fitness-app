"""
Tests for core exceptions.
"""

from django.test import TestCase

from .exceptions import (
    FoodMindException,
    ValidationError,
    NotFoundError,
    UserNotFoundError,
    PlanNotFoundError,
    PermissionDeniedError,
    BusinessLogicError,
    DailyLimitExceededError,
    SubscriptionRequiredError,
    InvalidStateError,
    ExternalServiceError,
    AIServiceError,
    AIServiceTimeoutError,
    PaymentServiceError,
)


class ExceptionsTestCase(TestCase):
    """Tests for custom exception classes."""

    def test_base_exception_default_values(self):
        """Test FoodMindException with default values."""
        exc = FoodMindException()
        self.assertEqual(exc.message, "An error occurred")
        self.assertEqual(exc.code, "error")
        self.assertEqual(exc.details, {})

    def test_base_exception_custom_values(self):
        """Test FoodMindException with custom values."""
        exc = FoodMindException(
            message="Custom error",
            code="custom_code",
            details={"key": "value"}
        )
        self.assertEqual(exc.message, "Custom error")
        self.assertEqual(exc.code, "custom_code")
        self.assertEqual(exc.details, {"key": "value"})

    def test_exception_to_dict(self):
        """Test to_dict method."""
        exc = FoodMindException(
            message="Test error",
            code="test_error",
            details={"field": "name"}
        )
        result = exc.to_dict()
        self.assertEqual(result, {
            "error": "test_error",
            "message": "Test error",
            "details": {"field": "name"},
        })

    def test_validation_error(self):
        """Test ValidationError defaults."""
        exc = ValidationError()
        self.assertEqual(exc.code, "validation_error")
        self.assertEqual(exc.message, "Validation error")

    def test_not_found_error(self):
        """Test NotFoundError defaults."""
        exc = NotFoundError()
        self.assertEqual(exc.code, "not_found")

    def test_user_not_found_error(self):
        """Test UserNotFoundError defaults."""
        exc = UserNotFoundError()
        self.assertEqual(exc.code, "user_not_found")
        self.assertEqual(exc.message, "User not found")

    def test_plan_not_found_error(self):
        """Test PlanNotFoundError defaults."""
        exc = PlanNotFoundError()
        self.assertEqual(exc.code, "plan_not_found")

    def test_permission_denied_error(self):
        """Test PermissionDeniedError defaults."""
        exc = PermissionDeniedError()
        self.assertEqual(exc.code, "permission_denied")

    def test_business_logic_error(self):
        """Test BusinessLogicError defaults."""
        exc = BusinessLogicError()
        self.assertEqual(exc.code, "business_error")

    def test_daily_limit_exceeded_error(self):
        """Test DailyLimitExceededError defaults."""
        exc = DailyLimitExceededError()
        self.assertEqual(exc.code, "daily_limit_exceeded")

    def test_subscription_required_error(self):
        """Test SubscriptionRequiredError defaults."""
        exc = SubscriptionRequiredError()
        self.assertEqual(exc.code, "subscription_required")

    def test_invalid_state_error(self):
        """Test InvalidStateError defaults."""
        exc = InvalidStateError()
        self.assertEqual(exc.code, "invalid_state")

    def test_external_service_error(self):
        """Test ExternalServiceError defaults."""
        exc = ExternalServiceError()
        self.assertEqual(exc.code, "external_service_error")

    def test_ai_service_error(self):
        """Test AIServiceError defaults."""
        exc = AIServiceError()
        self.assertEqual(exc.code, "ai_service_error")

    def test_ai_service_timeout_error(self):
        """Test AIServiceTimeoutError defaults."""
        exc = AIServiceTimeoutError()
        self.assertEqual(exc.code, "ai_service_timeout")

    def test_payment_service_error(self):
        """Test PaymentServiceError defaults."""
        exc = PaymentServiceError()
        self.assertEqual(exc.code, "payment_service_error")

    def test_exception_inheritance(self):
        """Test exception inheritance hierarchy."""
        self.assertTrue(issubclass(ValidationError, FoodMindException))
        self.assertTrue(issubclass(NotFoundError, FoodMindException))
        self.assertTrue(issubclass(UserNotFoundError, NotFoundError))
        self.assertTrue(issubclass(BusinessLogicError, FoodMindException))
        self.assertTrue(issubclass(DailyLimitExceededError, BusinessLogicError))
        self.assertTrue(issubclass(ExternalServiceError, FoodMindException))
        self.assertTrue(issubclass(AIServiceError, ExternalServiceError))
        self.assertTrue(issubclass(AIServiceTimeoutError, AIServiceError))

    def test_exception_can_be_raised_and_caught(self):
        """Test that exceptions can be raised and caught properly."""
        with self.assertRaises(FoodMindException):
            raise ValidationError("Invalid input")

        with self.assertRaises(NotFoundError):
            raise UserNotFoundError()

        with self.assertRaises(ExternalServiceError):
            raise AIServiceTimeoutError("Service timed out")
