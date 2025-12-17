"""
billing/test_limits.py

Тесты дневных лимитов фото и базовой логики plan resolution.

ВАЖНО:
- SubscriptionPlan.code обязателен (SSOT)
- daily usage менеджер теперь: increment_photo_ai_requests
- FREE план по бизнес-логике "всегда есть", но в тестах создаём явно,
  чтобы тесты были независимыми.

Эти тесты не проверяют YooKassa "по сети" — только наш код/валидацию.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APIClient

from .models import Payment, Subscription, SubscriptionPlan
from .services import get_effective_plan_for_user
from .usage import DailyUsage


class DailyUsageTestCase(TestCase):
    """Тесты DailyUsage и учёта использования."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_get_today_creates_new_record(self):
        usage = DailyUsage.objects.get_today(self.user)
        self.assertEqual(usage.user, self.user)
        self.assertEqual(usage.date, timezone.now().date())
        self.assertEqual(usage.photo_ai_requests, 0)

    def test_get_today_returns_existing_record(self):
        existing = DailyUsage.objects.create(
            user=self.user,
            date=timezone.now().date(),
            photo_ai_requests=5,
        )
        usage = DailyUsage.objects.get_today(self.user)
        self.assertEqual(usage.id, existing.id)
        self.assertEqual(usage.photo_ai_requests, 5)

    def test_increment_photo_ai_requests(self):
        usage1 = DailyUsage.objects.increment_photo_ai_requests(self.user)
        self.assertEqual(usage1.photo_ai_requests, 1)

        usage2 = DailyUsage.objects.increment_photo_ai_requests(self.user)
        self.assertEqual(usage2.photo_ai_requests, 2)
        self.assertEqual(usage2.id, usage1.id)

    def test_is_today_property(self):
        today_usage = DailyUsage.objects.create(
            user=self.user, date=timezone.now().date(), photo_ai_requests=1
        )
        self.assertTrue(today_usage.is_today)

        yesterday_usage = DailyUsage.objects.create(
            user=self.user,
            date=timezone.now().date() - timedelta(days=1),
            photo_ai_requests=1,
        )
        self.assertFalse(yesterday_usage.is_today)


class GetEffectivePlanTestCase(TestCase):
    """Тесты get_effective_plan_for_user."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        self.free_plan = SubscriptionPlan.objects.create(
            code="FREE",
            name="FREE",  # legacy optional, но пусть будет
            display_name="Бесплатный",
            price=Decimal("0.00"),
            duration_days=0,
            daily_photo_limit=3,
            is_active=True,
        )

        self.pro_monthly = SubscriptionPlan.objects.create(
            code="PRO_MONTHLY",
            name="MONTHLY",  # legacy
            display_name="PRO месяц",
            price=Decimal("299.00"),
            duration_days=30,
            daily_photo_limit=None,
            is_active=True,
        )

    def test_returns_free_when_no_subscription(self):
        plan = get_effective_plan_for_user(self.user)
        self.assertEqual(plan.code, "FREE")

    def test_returns_active_subscription_plan(self):
        Subscription.objects.create(
            user=self.user,
            plan=self.pro_monthly,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True,
        )
        plan = get_effective_plan_for_user(self.user)
        self.assertEqual(plan.code, "PRO_MONTHLY")

    def test_returns_free_when_subscription_expired(self):
        Subscription.objects.create(
            user=self.user,
            plan=self.pro_monthly,
            start_date=timezone.now() - timedelta(days=60),
            end_date=timezone.now() - timedelta(days=30),
            is_active=True,
        )
        plan = get_effective_plan_for_user(self.user)
        self.assertEqual(plan.code, "FREE")


class CreateUniversalPaymentTestCase(TestCase):
    """Тесты /billing/create-payment/ (без реальных запросов в YooKassa)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        self.free_plan = SubscriptionPlan.objects.create(
            code="FREE",
            name="FREE",
            display_name="Бесплатный",
            price=Decimal("0.00"),
            duration_days=0,
            is_active=True,
        )

        self.pro_monthly = SubscriptionPlan.objects.create(
            code="PRO_MONTHLY",
            name="MONTHLY",
            display_name="PRO месяц",
            price=Decimal("299.00"),
            duration_days=30,
            is_active=True,
        )

        # создаём подписку (free)
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True,
        )

    @patch("apps.billing.yookassa_client.YooKassaClient.create_payment")
    def test_create_monthly_payment(self, mock_create_payment):
        mock_create_payment.return_value = {
            "id": "test-monthly-payment",
            "status": "pending",
            "amount": {"value": "299.00", "currency": "RUB"},
            "confirmation": {"type": "redirect", "confirmation_url": "https://yookassa.ru/payments/test"},
            "metadata": {},
        }

        self.client.force_authenticate(user=self.user)

        url = reverse("billing:create-payment")
        response = self.client.post(url, {"plan_code": "PRO_MONTHLY"}, format="json")

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertIn("payment_id", response.data)
        self.assertIn("confirmation_url", response.data)

    def test_create_payment_rejects_free_plan(self):
        self.client.force_authenticate(user=self.user)

        url = reverse("billing:create-payment")
        response = self.client.post(url, {"plan_code": "FREE"}, format="json")

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_create_payment_missing_plan_code(self):
        self.client.force_authenticate(user=self.user)

        url = reverse("billing:create-payment")
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "MISSING_PLAN_CODE")


class WebhookFreePlanPreventionTestCase(TestCase):
    """
    Тест: даже если кто-то странным способом создал "платёж" на FREE,
    обработчик succeeded не должен активировать/продлевать FREE через оплату.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        self.free_plan = SubscriptionPlan.objects.create(
            code="FREE",
            name="FREE",
            display_name="Бесплатный",
            price=Decimal("0.00"),
            duration_days=0,
            is_active=True,
        )

        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.free_plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=365),
            is_active=True,
        )

    @patch("apps.billing.services.YooKassaService.parse_webhook_notification")
    def test_webhook_prevents_free_plan_activation(self, mock_parse):
        payment = Payment.objects.create(
            user=self.user,
            subscription=self.subscription,
            plan=self.free_plan,
            amount=Decimal("0.00"),
            currency="RUB",
            status="PENDING",
            yookassa_payment_id="test-free-payment",
            provider="YOOKASSA",
        )

        mock_notification = MagicMock()
        mock_notification.event = "payment.succeeded"
        mock_notification.object.id = "test-free-payment"
        mock_notification.object.payment_method = None
        mock_parse.return_value = mock_notification

        # Импортируем обработчик из webhooks.handlers (внутренний модуль для тестов)
        from apps.billing.webhooks.handlers import handle_payment_succeeded

        handle_payment_succeeded(mock_notification.object)

        payment.refresh_from_db()
        self.assertEqual(payment.status, "SUCCEEDED")
        self.assertIn("Cannot activate FREE plan", payment.error_message)

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan.code, "FREE")
