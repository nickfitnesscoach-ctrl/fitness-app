"""
Tests for billing throttling (rate limiting).

Verifies that:
- BillingPollingThrottle correctly limits polling endpoints
- Normal polling (1-3 sec intervals) works without 429
- Abusive polling (>120 req/min) is blocked with 429
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.billing.models import Subscription, SubscriptionPlan

User = get_user_model()


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create_user(
        username="throttle_test",
        email="throttle_test@example.com",
        password="testpass123",
    )


@pytest.fixture
def authenticated_client(user):
    """Create authenticated API client."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def free_plan(db):
    """Get or create FREE subscription plan."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="FREE",
        defaults={
            "name": "FREE",
            "display_name": "Free",
            "price": Decimal("0.00"),
            "daily_photo_limit": 10,
            "is_active": True,
            "is_test": False,
        }
    )
    return plan


@pytest.fixture
def subscription(user, free_plan, db):
    """Get user subscription (auto-created by signal)."""
    # Subscription is auto-created by post_save signal on User model
    # Just return it
    return user.subscription


@pytest.mark.django_db
class TestBillingPollingThrottle:
    """Tests for BillingPollingThrottle (120 req/min)."""

    @pytest.fixture(autouse=True)
    def setup_cache(self):
        """Clear cache before each test to avoid throttle state leaking."""
        from django.core.cache import cache
        cache.clear()
        yield
        cache.clear()

    def test_normal_polling_allowed(self, authenticated_client, subscription):
        """
        Normal polling (60 requests in 1 minute) should work without 429.

        Scenario: User polls /billing/me/ every 1 second for 1 minute.
        Expected: All 60 requests succeed (< 120 req/min limit).
        """
        url = "/api/v1/billing/me/"

        # Mock DailyUsage to avoid DB overhead
        with patch("apps.billing.usage.DailyUsage") as mock_usage:
            mock_usage.objects.get_today.return_value.photo_ai_requests = 5

            # 60 requests = 1 req/sec for 1 minute
            for i in range(60):
                response = authenticated_client.get(url)
                assert response.status_code == status.HTTP_200_OK, (
                    f"Request {i+1}/60 failed with {response.status_code}. "
                    f"Normal polling should not trigger throttle."
                )

    def test_abusive_polling_blocked(self, authenticated_client, subscription):
        """
        Abusive polling (>120 requests) should be blocked with 429.

        Scenario: User sends 121 requests rapidly.
        Expected: First 120 succeed, 121st returns 429 Too Many Requests.
        """
        url = "/api/v1/billing/me/"

        # Mock DailyUsage to avoid DB overhead
        with patch("apps.billing.usage.DailyUsage") as mock_usage:
            mock_usage.objects.get_today.return_value.photo_ai_requests = 5

            # First 120 requests should succeed
            for i in range(120):
                response = authenticated_client.get(url)
                assert response.status_code == status.HTTP_200_OK, (
                    f"Request {i+1}/120 should succeed (within limit)"
                )

            # 121st request should be throttled
            response = authenticated_client.get(url)
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS, (
                "Request 121 should be throttled (exceeds 120 req/min limit)"
            )

    def test_subscription_details_throttled(self, authenticated_client, subscription):
        """
        GET /billing/subscription/ should also be throttled with same limit.

        Both polling endpoints share the same throttle scope (billing_polling).
        """
        url = "/api/v1/billing/subscription/"

        # First 120 requests should succeed
        for i in range(120):
            response = authenticated_client.get(url)
            assert response.status_code == status.HTTP_200_OK, (
                f"Request {i+1}/120 should succeed"
            )

        # 121st request should be throttled
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_throttle_scoped_per_user(self, user, free_plan, db):
        """
        Throttle should be scoped per user, not globally.

        Two different users should each get their own 120 req/min allowance.
        """
        from django.utils import timezone
        from datetime import timedelta

        # Create second user (subscription auto-created by signal)
        user2 = User.objects.create_user(
            username="throttle_test2",
            email="throttle_test2@example.com",
            password="testpass123",
        )

        client1 = APIClient()
        client1.force_authenticate(user=user)

        client2 = APIClient()
        client2.force_authenticate(user=user2)

        url = "/api/v1/billing/me/"

        with patch("apps.billing.usage.DailyUsage") as mock_usage:
            mock_usage.objects.get_today.return_value.photo_ai_requests = 5

            # User 1: exhaust their limit (120 requests)
            for i in range(120):
                response = client1.get(url)
                assert response.status_code == status.HTTP_200_OK

            # User 1: 121st request should be throttled
            response = client1.get(url)
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

            # User 2: should still be able to make requests (separate quota)
            response = client2.get(url)
            assert response.status_code == status.HTTP_200_OK, (
                "User 2 should have separate throttle quota from User 1"
            )

    def test_other_endpoints_not_affected(self, authenticated_client, subscription):
        """
        BillingPollingThrottle should NOT affect other billing endpoints.

        /billing/plans/ should remain unrestricted (or have its own throttle).
        """
        polling_url = "/api/v1/billing/me/"
        plans_url = "/api/v1/billing/plans/"

        with patch("apps.billing.usage.DailyUsage") as mock_usage:
            mock_usage.objects.get_today.return_value.photo_ai_requests = 5

            # Exhaust polling quota
            for i in range(120):
                response = authenticated_client.get(polling_url)
                assert response.status_code == status.HTTP_200_OK

            # Polling endpoint should be throttled
            response = authenticated_client.get(polling_url)
            assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

            # Plans endpoint should still work (no throttle or different throttle)
            response = authenticated_client.get(plans_url)
            assert response.status_code == status.HTTP_200_OK, (
                "/billing/plans/ should not be affected by polling throttle"
            )
