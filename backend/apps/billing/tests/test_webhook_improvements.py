"""
Tests for webhook security, idempotency, trace_id, and queue routing.

These tests cover the A2-A5 requirements for production-grade billing.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.test.client import RequestFactory

from apps.billing.models import Payment, SubscriptionPlan, WebhookLog
from apps.billing.webhooks.views import (
    _get_client_ip_secure,
    _is_trusted_proxy,
    _extract_provider_event_id,
    _sanitize_payload,
)
from apps.billing.webhooks.handlers import handle_yookassa_event
from apps.billing.webhooks.tasks import process_yookassa_webhook

User = get_user_model()


class TestWebhookXFFSecurity(TestCase):
    """A2: Test XFF trust only from trusted proxies."""

    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(WEBHOOK_TRUST_XFF=False)
    def test_xff_ignored_when_trust_disabled(self):
        """When WEBHOOK_TRUST_XFF=False, XFF header should be ignored."""
        request = self.factory.post("/")
        request.META["REMOTE_ADDR"] = "1.2.3.4"
        request.META["HTTP_X_FORWARDED_FOR"] = "185.71.76.1"  # YooKassa IP

        client_ip, remote_addr = _get_client_ip_secure(request)

        # Should use REMOTE_ADDR, not XFF
        self.assertEqual(client_ip, "1.2.3.4")
        self.assertEqual(remote_addr, "1.2.3.4")

    @override_settings(WEBHOOK_TRUST_XFF=True, WEBHOOK_TRUSTED_PROXIES=["172.24.0.0/16"])
    def test_xff_trusted_from_trusted_proxy(self):
        """When XFF is enabled and request is from trusted proxy, use XFF."""
        request = self.factory.post("/")
        request.META["REMOTE_ADDR"] = "172.24.0.1"  # Trusted proxy (Docker)
        request.META["HTTP_X_FORWARDED_FOR"] = "185.71.76.1"  # YooKassa IP

        client_ip, remote_addr = _get_client_ip_secure(request)

        # Should trust XFF
        self.assertEqual(client_ip, "185.71.76.1")
        self.assertEqual(remote_addr, "172.24.0.1")

    @override_settings(WEBHOOK_TRUST_XFF=True, WEBHOOK_TRUSTED_PROXIES=["172.24.0.0/16"])
    def test_xff_ignored_from_untrusted_source(self):
        """When XFF is enabled but request is NOT from trusted proxy, ignore XFF."""
        request = self.factory.post("/")
        request.META["REMOTE_ADDR"] = "1.2.3.4"  # Not trusted
        request.META["HTTP_X_FORWARDED_FOR"] = "185.71.76.1"  # Spoofed YooKassa IP

        client_ip, remote_addr = _get_client_ip_secure(request)

        # Should NOT trust XFF, use REMOTE_ADDR
        self.assertEqual(client_ip, "1.2.3.4")
        self.assertEqual(remote_addr, "1.2.3.4")

    @override_settings(WEBHOOK_TRUST_XFF=True, WEBHOOK_TRUSTED_PROXIES=["127.0.0.1"])
    def test_trusted_proxy_exact_match(self):
        """Trusted proxy exact IP match."""
        self.assertTrue(_is_trusted_proxy("127.0.0.1"))
        self.assertFalse(_is_trusted_proxy("127.0.0.2"))

    @override_settings(WEBHOOK_TRUST_XFF=True, WEBHOOK_TRUSTED_PROXIES=["10.0.0.0/8"])
    def test_trusted_proxy_cidr_match(self):
        """Trusted proxy CIDR match."""
        self.assertTrue(_is_trusted_proxy("10.0.0.1"))
        self.assertTrue(_is_trusted_proxy("10.255.255.255"))
        self.assertFalse(_is_trusted_proxy("11.0.0.1"))


class TestWebhookIdempotencyEventId(TestCase):
    """A3: Test idempotency using provider_event_id."""

    def test_extract_provider_event_id_from_uuid(self):
        """Extract event_id from payload.uuid."""
        payload = {
            "uuid": "abc-123-def",
            "type": "notification",
            "event": "payment.succeeded",
            "object": {"id": "payment-1"},
        }
        event_id = _extract_provider_event_id(payload)
        self.assertEqual(event_id, "abc-123-def")

    def test_extract_provider_event_id_from_id(self):
        """Extract event_id from payload.id when type=notification."""
        payload = {
            "id": "notification-456",
            "type": "notification",
            "event": "payment.succeeded",
            "object": {"id": "payment-1"},
        }
        event_id = _extract_provider_event_id(payload)
        self.assertEqual(event_id, "notification-456")

    def test_extract_provider_event_id_fallback(self):
        """When no uuid/id, return None for fallback key."""
        payload = {
            "type": "notification",
            "event": "payment.succeeded",
            "object": {"id": "payment-1"},
        }
        event_id = _extract_provider_event_id(payload)
        self.assertIsNone(event_id)

    def test_duplicate_webhook_with_same_event_id(self):
        """A3: Duplicate webhook with same event_id should be ignored."""
        # Create first webhook log
        WebhookLog.objects.create(
            event_id="test-event-id-123",
            event_type="payment.succeeded",
            provider_event_id="test-event-id-123",
            status="SUCCESS",
            raw_payload={"test": "data"},
        )

        # Try to create duplicate
        with self.assertRaises(Exception):  # Should raise IntegrityError
            WebhookLog.objects.create(
                event_id="test-event-id-123",  # Same event_id
                event_type="payment.succeeded",
                provider_event_id="test-event-id-123",
                status="RECEIVED",
                raw_payload={"test": "data2"},
            )


class TestWebhookTraceId(TestCase):
    """A4: Test trace_id propagation."""

    def setUp(self):
        # Create test data
        self.free_plan, _ = SubscriptionPlan.objects.get_or_create(
            code="FREE",
            defaults={
                "display_name": "Free",
                "price": Decimal("0"),
                "duration_days": 0,
                "is_active": True,
            },
        )
        self.pro_plan, _ = SubscriptionPlan.objects.get_or_create(
            code="PRO_MONTHLY",
            defaults={
                "display_name": "PRO Monthly",
                "price": Decimal("299"),
                "duration_days": 30,
                "is_active": True,
            },
        )
        self.user = User.objects.create_user(
            username="testwebhook_trace",
            email="testwebhook_trace@example.com",
            password="testpass123",
        )
        self.payment = Payment.objects.create(
            user=self.user,
            subscription=self.user.subscription,
            plan=self.pro_plan,
            amount=Decimal("299"),
            currency="RUB",
            status="PENDING",
            provider="YOOKASSA",
            yookassa_payment_id="trace_test_payment_123",
            description="Test payment",
        )

    def test_trace_id_stored_in_webhook_log(self):
        """Trace ID should be stored in WebhookLog."""
        log = WebhookLog.objects.create(
            event_id="trace-test-event",
            event_type="payment.succeeded",
            trace_id="abc12345",
            status="RECEIVED",
            raw_payload={},
        )
        self.assertEqual(log.trace_id, "abc12345")

    def test_handle_yookassa_event_accepts_trace_id(self):
        """handle_yookassa_event should accept trace_id parameter."""
        payload = {
            "type": "notification",
            "event": "payment.succeeded",
            "object": {
                "id": "trace_test_payment_123",
                "status": "succeeded",
            },
        }

        # Should not raise
        handle_yookassa_event(
            event_type="payment.succeeded",
            payload=payload,
            trace_id="test-trace-123",
        )

    @patch("apps.billing.webhooks.tasks.handle_yookassa_event")
    def test_celery_task_passes_trace_id(self, mock_handler):
        """Celery task should pass trace_id to handler."""
        log = WebhookLog.objects.create(
            event_id="celery-trace-test-2",
            event_type="payment.succeeded",
            trace_id="celery-trace-abc",
            status="QUEUED",
            raw_payload={"object": {"id": "test"}},
        )

        # Call task with trace_id
        process_yookassa_webhook(log.id, trace_id="celery-trace-abc")

        # Verify trace_id was passed
        mock_handler.assert_called_once()
        call_kwargs = mock_handler.call_args.kwargs
        self.assertEqual(call_kwargs.get("trace_id"), "celery-trace-abc")


class TestWebhookQueueRouting(TestCase):
    """A5: Test Celery queue configuration."""

    def test_task_has_billing_queue(self):
        """process_yookassa_webhook should be routed to billing queue."""
        # Check task decorator options
        self.assertEqual(process_yookassa_webhook.queue, "billing")

    def test_task_has_ack_late(self):
        """Task should have ack_late=True for reliability."""
        self.assertTrue(process_yookassa_webhook.ack_late)


class TestPayloadSanitization(TestCase):
    """Test sensitive data sanitization."""

    def test_sanitize_payload_redacts_card_details(self):
        """Card details should be redacted except last4."""
        payload = {
            "type": "notification",
            "event": "payment.succeeded",
            "object": {
                "id": "payment-123",
                "status": "succeeded",
                "payment_method": {
                    "id": "pm-123",
                    "type": "bank_card",
                    "saved": True,
                    "card": {
                        "first6": "411111",
                        "last4": "1234",
                        "expiry_month": "12",
                        "expiry_year": "2025",
                        "card_type": "Visa",
                    },
                },
            },
        }

        sanitized = _sanitize_payload(payload)

        # last4 should be preserved
        self.assertEqual(sanitized["object"]["payment_method"]["card"]["last4"], "1234")
        # redacted flag should be set
        self.assertTrue(sanitized["object"]["payment_method"]["card"]["redacted"])
        # sensitive fields should NOT be present
        self.assertNotIn("first6", sanitized["object"]["payment_method"]["card"])
        self.assertNotIn("expiry_month", sanitized["object"]["payment_method"]["card"])
