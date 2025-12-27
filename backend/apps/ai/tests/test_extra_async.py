from __future__ import annotations
from unittest.mock import Mock, patch
from django.core.cache import cache
from django.urls import reverse
import pytest
from rest_framework.test import APIClient
from apps.nutrition.models import Meal


@pytest.mark.django_db
class TestAIAsyncFlowExtra:
    def setup_method(self):
        self.client = APIClient()
        cache.clear()

    def test_task_status_cache_miss_fallback_success(self, django_user_model):
        """P1: Cache MISS + payload.owner_id match + meal_id=None -> 200 OK (Empty/Error case)."""
        user = django_user_model.objects.create_user(username="u_cache1", password="pass")
        self.client.force_authenticate(user=user)
        task_id = "miss_success"

        # Cache is EMPTY
        cache.delete(f"ai_task_owner:{task_id}")

        fake_res = Mock()
        fake_res.ready.return_value = True
        fake_res.state = "SUCCESS"
        # Payload has owner_id matching user
        fake_res.result = {
            "owner_id": user.id,
            "meal_id": None,
            "error": "EMPTY_RESULT",
            "items": [],
            "totals": {},
        }

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(reverse("ai:task-status", kwargs={"task_id": task_id}))

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"  # Based on error presence in payload logic
        # Hygiene check
        assert "owner_id" not in body["result"]
        # Cache refilled
        assert cache.get(f"ai_task_owner:{task_id}") == user.id

    def test_task_status_cache_miss_fallback_db_verify(self, django_user_model):
        """P1: Cache MISS + payload.owner_id match + meal_id exists -> DB Verify."""
        user = django_user_model.objects.create_user(username="u_cache2", password="pass")
        self.client.force_authenticate(user=user)

        meal = Meal.objects.create(user=user, meal_type="SNACK", date="2025-12-01")
        task_id = "miss_db_verify"
        cache.delete(f"ai_task_owner:{task_id}")

        fake_res = Mock()
        fake_res.ready.return_value = True
        fake_res.state = "SUCCESS"
        fake_res.result = {"owner_id": user.id, "meal_id": meal.id, "items": [], "totals": {}}

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(reverse("ai:task-status", kwargs={"task_id": task_id}))

        assert resp.status_code == 200
        assert cache.get(f"ai_task_owner:{task_id}") == user.id

    def test_task_status_cache_miss_fallback_fail_mismatch(self, django_user_model):
        """P1: Cache MISS + owner_id mismatch -> 404."""
        user = django_user_model.objects.create_user(username="u_cache3", password="pass")
        other_user_id = user.id + 999
        self.client.force_authenticate(user=user)

        task_id = "miss_mismatch"
        cache.delete(f"ai_task_owner:{task_id}")

        fake_res = Mock()
        fake_res.ready.return_value = True
        fake_res.state = "SUCCESS"
        fake_res.result = {
            "owner_id": other_user_id,  # Mismatch
            "meal_id": None,
            "items": [],
            "totals": {},
        }

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(reverse("ai:task-status", kwargs={"task_id": task_id}))

        assert resp.status_code == 404

    def test_task_status_payload_hygiene(self, django_user_model):
        """P1: Ensure owner_id is scrubbed from response."""
        user = django_user_model.objects.create_user(username="u_hyg", password="pass")
        self.client.force_authenticate(user=user)
        task_id = "hygiene_task"
        cache.set(f"ai_task_owner:{task_id}", user.id)

        fake_res = Mock()
        fake_res.state = "SUCCESS"
        fake_res.result = {"owner_id": user.id, "meal_id": 1, "items": [], "totals": {}}

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(reverse("ai:task-status", kwargs={"task_id": task_id}))

        assert "owner_id" not in resp.json()["result"]

    def test_task_status_totals_guarantee(self, django_user_model):
        """P0: Check that totals and items are added if missing."""
        user = django_user_model.objects.create_user(username="u_tot", password="pass")
        self.client.force_authenticate(user=user)
        task_id = "totals_task"
        cache.set(f"ai_task_owner:{task_id}", user.id)

        fake_res = Mock()
        fake_res.state = "SUCCESS"
        # Payload missing items and totals
        fake_res.result = {"meal_id": 1}

        with patch("apps.ai.views.AsyncResult", return_value=fake_res):
            resp = self.client.get(reverse("ai:task-status", kwargs={"task_id": task_id}))

        result = resp.json()["result"]
        assert result["items"] == []
        assert result["totals"] == {}
