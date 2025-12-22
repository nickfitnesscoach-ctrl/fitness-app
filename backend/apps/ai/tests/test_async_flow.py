"""
test_async_flow.py — тесты async API (202 + Celery).

Проверяем:
- POST /ai/recognize/ → 202, task_id, meal_id
- defaults (meal_type=SNACK, date=today)
- task status polling
"""

from __future__ import annotations

from datetime import date
from unittest.mock import Mock, patch

from django.urls import reverse
from django.utils import timezone
import pytest
from rest_framework.test import APIClient

from apps.nutrition.models import Meal


@pytest.mark.django_db
class TestAIAsyncFlow:
    def setup_method(self):
        self.client = APIClient()

    def test_recognize_returns_202_and_creates_meal(self, django_user_model):
        user = django_user_model.objects.create_user(username="u1", password="pass")
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
        assert "meal_id" in body

        meal = Meal.objects.get(id=body["meal_id"])
        assert meal.user_id == user.id
        assert meal.meal_type == "LUNCH"
        assert meal.date == timezone.localdate()

        delay_mock.assert_called_once()

    def test_meal_created_with_defaults(self, django_user_model):
        user = django_user_model.objects.create_user(username="u2", password="pass")
        self.client.force_authenticate(user=user)

        url = reverse("ai:recognize-food")
        fake_task = Mock()
        fake_task.id = "task-456"

        with patch("apps.ai.views.recognize_food_async.delay", return_value=fake_task):
            resp = self.client.post(
                url,
                data={"data_url": _small_png_data_url()},
                format="json",
            )

        assert resp.status_code == 202
        meal_id = resp.json()["meal_id"]
        meal = Meal.objects.get(id=meal_id)
        assert meal.meal_type == "SNACK"
        assert meal.date == timezone.localdate()

    def test_meal_created_with_custom_date(self, django_user_model):
        user = django_user_model.objects.create_user(username="u3", password="pass")
        self.client.force_authenticate(user=user)

        url = reverse("ai:recognize-food")
        fake_task = Mock()
        fake_task.id = "task-789"
        custom_date = date(2025, 12, 1)

        with patch("apps.ai.views.recognize_food_async.delay", return_value=fake_task):
            resp = self.client.post(
                url,
                data={
                    "data_url": _small_png_data_url(),
                    "meal_type": "DINNER",
                    "date": str(custom_date),
                },
                format="json",
            )

        assert resp.status_code == 202
        meal = Meal.objects.get(id=resp.json()["meal_id"])
        assert meal.meal_type == "DINNER"
        assert meal.date == custom_date

    def test_task_status_processing(self, django_user_model):
        user = django_user_model.objects.create_user(username="u4", password="pass")
        self.client.force_authenticate(user=user)

        url = reverse("ai:task-status", kwargs={"task_id": "abc"})
        fake_res = Mock()
        fake_res.state = "PENDING"

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(url)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "processing"

    def test_task_status_success(self, django_user_model):
        user = django_user_model.objects.create_user(username="u5", password="pass")
        self.client.force_authenticate(user=user)

        url = reverse("ai:task-status", kwargs={"task_id": "abc"})
        fake_res = Mock()
        fake_res.state = "SUCCESS"
        fake_res.result = {"meal_id": 1, "items": [], "totals": {"calories": 0}}

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(url)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert "result" in body

    def test_task_status_failed(self, django_user_model):
        user = django_user_model.objects.create_user(username="u6", password="pass")
        self.client.force_authenticate(user=user)

        url = reverse("ai:task-status", kwargs={"task_id": "abc"})
        fake_res = Mock()
        fake_res.state = "FAILURE"
        fake_res.result = Exception("boom")

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(url)

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"


def _small_png_data_url() -> str:
    """Минимальный валидный PNG 1x1 (base64)."""
    return (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ZkAAAAASUVORK5CYII="
    )
