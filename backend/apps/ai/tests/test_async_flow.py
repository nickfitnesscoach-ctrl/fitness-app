"""
test_async_flow.py — тесты async API (202 + Celery).

Проверяем:
- POST /ai/recognize/ → 202, task_id, meal_id
- defaults (meal_type=SNACK, date=today)
- task status polling
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
import pytest
from rest_framework.test import APIClient

from apps.billing.models import Subscription, SubscriptionPlan
from apps.billing.usage import DailyUsage
from apps.nutrition.models import Meal


@pytest.mark.django_db
class TestAIAsyncFlow:
    def setup_method(self):
        self.client = APIClient()
        cache.clear()

    def test_recognize_returns_202(self, django_user_model):
        """P1-1: View returns 202 and does NOT create meal upfront."""
        user = django_user_model.objects.create_user(
            username="u1", password="pass", email="u1@t.com"
        )
        self.client.force_authenticate(user=user)

        url = reverse("ai:recognize-food")

        fake_task = Mock()
        fake_task.id = "task-123"

        with patch(
            "apps.ai.views.recognize_food_async.delay", return_value=fake_task
        ) as delay_mock:
            resp = self.client.post(
                url,
                data={"data_url": _small_png_data_url(), "meal_type": "LUNCH"},
                format="json",
            )

        assert resp.status_code == 202
        body = resp.json()
        assert body["task_id"] == "task-123"
        assert body["status"] == "processing"
        assert body["meal_id"] is None  # P1-1: No meal created yet

        # Verify no meal created in DB
        assert Meal.objects.filter(user=user).count() == 0

        # Verify ownership saved in cache
        assert cache.get(f"ai_task_owner:{fake_task.id}") == user.id

        delay_mock.assert_called_once()

    def test_task_status_processing(self, django_user_model):
        user = django_user_model.objects.create_user(
            username="u4", password="pass", email="u4@t.com"
        )
        self.client.force_authenticate(user=user)
        task_id = "abc"

        # Setup ownership
        cache.set(f"ai_task_owner:{task_id}", user.id)

        url = reverse("ai:task-status", kwargs={"task_id": task_id})
        fake_res = Mock()
        fake_res.state = "PENDING"

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(url)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "processing"

    def test_task_status_success(self, django_user_model):
        user = django_user_model.objects.create_user(
            username="u5", password="pass", email="u5@t.com"
        )
        self.client.force_authenticate(user=user)
        task_id = "abc"

        # Setup ownership
        cache.set(f"ai_task_owner:{task_id}", user.id)

        url = reverse("ai:task-status", kwargs={"task_id": task_id})
        fake_res = Mock()
        fake_res.state = "SUCCESS"
        fake_res.result = {"meal_id": 1, "items": [], "totals": {"calories": 0}}

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(url)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert "result" in body
        assert body["result"]["items"] == []  # Guaranteed by TaskStatusView

    def test_task_status_failed(self, django_user_model):
        user = django_user_model.objects.create_user(
            username="u6", password="pass", email="u6@t.com"
        )
        self.client.force_authenticate(user=user)
        task_id = "abc"

        # Setup ownership
        cache.set(f"ai_task_owner:{task_id}", user.id)

        url = reverse("ai:task-status", kwargs={"task_id": task_id})
        fake_res = Mock()
        fake_res.state = "FAILURE"
        fake_res.result = Exception("boom")

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(url)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"

    def test_task_status_404_if_not_owner(self, django_user_model):
        """P0 Security: If user polls a task they don't own, return 404."""
        user_a = django_user_model.objects.create_user(
            username="ua", password="pass", email="ua@t.com"
        )
        user_b = django_user_model.objects.create_user(
            username="ub", password="pass", email="ub@t.com"
        )
        self.client.force_authenticate(user=user_b)

        task_id = "task-owner-a"
        # Ownership belongs to user_a
        cache.set(f"ai_task_owner:{task_id}", user_a.id)

        url = reverse("ai:task-status", kwargs={"task_id": task_id})

        resp = self.client.get(url)
        assert resp.status_code == 404

    def test_limit_exceeded_returns_429_no_meal_created(self, django_user_model):
        """P1-4: When limit exceeded, 429 returned and Meal NOT created."""
        user = django_user_model.objects.create_user(
            username="u_limit", password="pass", email="limit@t.com"
        )
        self.client.force_authenticate(user=user)

        # Create FREE plan with limit=3
        free_plan, _ = SubscriptionPlan.objects.get_or_create(
            code="FREE",
            defaults={
                "name": "FREE",
                "display_name": "Бесплатный",
                "price": Decimal("0"),
                "duration_days": 0,
                "daily_photo_limit": 3,
                "is_active": True,
            },
        )

        # Create subscription
        Subscription.objects.get_or_create(
            user=user,
            defaults={
                "plan": free_plan,
                "start_date": timezone.now(),
                "end_date": timezone.now() + timezone.timedelta(days=365),
                "is_active": True,
            },
        )

        # Exhaust limit (set usage to 3)
        usage = DailyUsage.objects.get_today(user)
        usage.photo_ai_requests = 3
        usage.save()

        # Count meals before
        meal_count_before = Meal.objects.filter(user=user).count()

        url = reverse("ai:recognize-food")
        resp = self.client.post(
            url,
            data={"data_url": _small_png_data_url()},
            format="json",
        )

        # Should return 429
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"] == "DAILY_PHOTO_LIMIT_EXCEEDED"

        # No new Meal should be created
        meal_count_after = Meal.objects.filter(user=user).count()
        assert meal_count_after == meal_count_before


def _small_png_data_url() -> str:
    return (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ZkAAAAASUVORK5CYII="
    )
