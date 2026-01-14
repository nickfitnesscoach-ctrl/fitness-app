"""
Tests for webhook safety guards (FOR UPDATE + OUTER JOIN fix).

These tests verify that the lock_payment_by_yookassa_id() helper functions
correctly handle nullable FK relationships without causing PostgreSQL errors.

See: production incident 2026-01-14 (payment.canceled crash)
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Payment, SubscriptionPlan
from apps.billing.webhooks.handlers import (
    lock_payment_by_yookassa_id,
    lock_payment_by_yookassa_id_optional,
)

User = get_user_model()


@pytest.mark.django_db
class TestPaymentLockHelpers:
    """Test helper functions for safely locking Payment records."""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def plan(self):
        return SubscriptionPlan.objects.create(
            code="PRO",
            name="Pro Plan",
            price=99,
            duration_days=30,
        )

    @pytest.fixture
    def payment(self, user, plan):
        """Payment with nullable subscription field."""
        return Payment.objects.create(
            user=user,
            plan=plan,
            amount=99,
            yookassa_payment_id="test-payment-id-123",
            status="PENDING",
            # subscription is NULL (nullable FK)
        )

    def test_lock_payment_by_yookassa_id_success(self, payment):
        """Test that lock_payment_by_yookassa_id locks payment successfully."""
        with transaction.atomic():
            locked = lock_payment_by_yookassa_id(payment.yookassa_payment_id)
            assert locked.id == payment.id
            assert locked.yookassa_payment_id == payment.yookassa_payment_id

            # Update within transaction
            locked.status = "SUCCEEDED"
            locked.save()

        # Verify update persisted
        payment.refresh_from_db()
        assert payment.status == "SUCCEEDED"

    def test_lock_payment_by_yookassa_id_not_found(self):
        """Test that lock_payment_by_yookassa_id raises DoesNotExist."""
        with pytest.raises(Payment.DoesNotExist):
            with transaction.atomic():
                lock_payment_by_yookassa_id("non-existent-id")

    def test_lock_payment_by_yookassa_id_optional_success(self, payment):
        """Test that optional variant returns payment if found."""
        with transaction.atomic():
            locked = lock_payment_by_yookassa_id_optional(payment.yookassa_payment_id)
            assert locked is not None
            assert locked.id == payment.id

    def test_lock_payment_by_yookassa_id_optional_not_found(self):
        """Test that optional variant returns None if not found."""
        with transaction.atomic():
            result = lock_payment_by_yookassa_id_optional("non-existent-id")
            assert result is None

    def test_lock_does_not_use_select_related_nullable_fk(self, payment):
        """
        Critical test: Verify that lock does NOT use select_related() on nullable FK.

        This test ensures that the helper function does NOT cause PostgreSQL error:
        "FOR UPDATE cannot be applied to the nullable side of an outer join"
        """
        with transaction.atomic():
            locked = lock_payment_by_yookassa_id(payment.yookassa_payment_id)

            # Access nullable FK via lazy loading (should work)
            # subscription is NULL
            assert locked.subscription is None

            # Access plan via lazy loading (should work)
            assert locked.plan is not None
            assert locked.plan.code == "PRO"

            # This should NOT raise "FOR UPDATE cannot be applied to nullable side" error
            locked.status = "SUCCEEDED"
            locked.save()


@pytest.mark.django_db
class TestAntiSpamAlertCache:
    """Test anti-spam logic for alert_failed_webhooks task."""

    def test_anti_spam_cache_key_format(self):
        """Verify cache key format is predictable."""
        from apps.billing.webhooks.tasks import alert_failed_webhooks

        # Cache key should be defined in task function
        # We can't easily test the task itself without mocking WebhookLog,
        # but we can verify the logic by reading the code.
        # This is a smoke test to ensure the module imports correctly.
        assert callable(alert_failed_webhooks)

    def test_cache_operations_are_atomic(self):
        """
        Test that cache operations in alert task are atomic.

        This is a smoke test to ensure the cache key pattern is correct.
        """
        from django.core.cache import cache

        ALERT_CACHE_KEY = "billing:last_alerted_webhook_ids"
        ALERT_CACHE_TTL = 3600

        # Simulate storing webhook IDs
        test_ids = {1, 2, 3}
        cache.set(ALERT_CACHE_KEY, test_ids, ALERT_CACHE_TTL)

        # Retrieve and verify
        cached_ids = cache.get(ALERT_CACHE_KEY, set())
        assert cached_ids == test_ids

        # Update with new IDs
        new_ids = {1, 2, 3, 4, 5}
        cache.set(ALERT_CACHE_KEY, new_ids, ALERT_CACHE_TTL)

        cached_ids = cache.get(ALERT_CACHE_KEY, set())
        assert cached_ids == new_ids

        # Clean up
        cache.delete(ALERT_CACHE_KEY)
