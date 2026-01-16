"""
test_invalid_status.py — Test INVALID_STATUS error when retrying SUCCESS photos.

Test coverage:
1. Create a SUCCESS photo
2. Attempt retry with meal_photo_id
3. Verify INVALID_STATUS error with Error Contract compliance
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.nutrition.models import Meal, MealPhoto
from django.utils import timezone


@pytest.mark.django_db
class TestInvalidStatusError:
    """Test INVALID_STATUS error returned when retrying non-failed photos."""

    def setup_method(self):
        self.client = APIClient()

    def test_retry_success_photo_returns_invalid_status(self, django_user_model):
        """
        When user tries to retry a SUCCESS photo, INVALID_STATUS error is returned.

        Steps:
        1. Create user + authenticate
        2. Create Meal + MealPhoto with status=SUCCESS
        3. POST /ai/recognize/ with meal_photo_id (retry attempt)
        4. Verify HTTP 400
        5. Verify error_code=INVALID_STATUS
        6. Verify Error Contract compliance (trace_id, allow_retry, user_actions)
        """
        # 1. Create user
        user = django_user_model.objects.create_user(
            username="test_invalid_status", password="pass", email="test@t.com"
        )
        self.client.force_authenticate(user=user)

        # 2. Create Meal + MealPhoto with status=SUCCESS
        meal = Meal.objects.create(
            user=user,
            meal_type="BREAKFAST",
            date=timezone.now().date(),
            status="DRAFT",
        )
        meal_photo = MealPhoto.objects.create(
            meal=meal,
            image="test_photo.jpg",  # Dummy path
            status="SUCCESS",  # Terminal success status
        )

        # 3. Attempt retry (POST with meal_photo_id = DB id)
        url = reverse("ai:recognize-food")
        response = self.client.post(
            url,
            data={
                "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ZkAAAAASUVORK5CYII=",
                "meal_photo_id": str(meal_photo.id),
            },
            format="json",
        )

        # 4. Verify HTTP 400
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

        # 5. Verify error_code
        body = response.json()
        assert body["error_code"] == "INVALID_STATUS", (
            f"Expected INVALID_STATUS, got {body.get('error_code')}"
        )

        # 6. Verify Error Contract compliance
        assert "trace_id" in body, "trace_id missing in INVALID_STATUS response"
        assert isinstance(body["trace_id"], str), "trace_id should be a string"
        assert len(body["trace_id"]) > 0, "trace_id should be non-empty"

        assert body["allow_retry"] is False, "allow_retry should be False for INVALID_STATUS"

        assert "user_actions" in body, "user_actions missing"
        assert isinstance(body["user_actions"], list), "user_actions should be a list"
        assert "contact_support" in body["user_actions"], (
            "user_actions should include 'contact_support'"
        )

        assert "user_title" in body, "user_title missing"
        assert isinstance(body["user_title"], str), "user_title should be a string"

        assert "user_message" in body, "user_message missing"
        assert isinstance(body["user_message"], str), "user_message should be a string"

        # Verify X-Request-ID header
        assert "X-Request-ID" in response, "X-Request-ID header missing"
        assert response["X-Request-ID"] == body["trace_id"], (
            "X-Request-ID header should match trace_id"
        )

    def test_retry_processing_photo_returns_invalid_status(self, django_user_model):
        """
        When user tries to retry a PROCESSING photo, INVALID_STATUS error is returned.
        """
        user = django_user_model.objects.create_user(
            username="test_processing", password="pass", email="test2@t.com"
        )
        self.client.force_authenticate(user=user)

        meal = Meal.objects.create(
            user=user,
            meal_type="LUNCH",
            date=timezone.now().date(),
            status="DRAFT",
        )
        meal_photo = MealPhoto.objects.create(
            meal=meal,
            image="test_photo2.jpg",
            status="PROCESSING",  # Non-terminal status
        )

        url = reverse("ai:recognize-food")
        response = self.client.post(
            url,
            data={
                "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ZkAAAAASUVORK5CYII=",
                "meal_photo_id": str(meal_photo.id),
            },
            format="json",
        )

        assert response.status_code == 400
        body = response.json()
        assert body["error_code"] == "INVALID_STATUS"
        assert "trace_id" in body

    def test_retry_failed_photo_does_not_return_invalid_status(self, django_user_model):
        """
        When user tries to retry a FAILED photo, NO error is returned.
        (This is the happy path for retry)
        """
        user = django_user_model.objects.create_user(
            username="test_retry_ok", password="pass", email="test3@t.com"
        )
        self.client.force_authenticate(user=user)

        meal = Meal.objects.create(
            user=user,
            meal_type="DINNER",
            date=timezone.now().date(),
            status="DRAFT",
        )
        meal_photo = MealPhoto.objects.create(
            meal=meal,
            image="test_photo3.jpg",
            status="FAILED",  # Retryable status
        )

        url = reverse("ai:recognize-food")
        response = self.client.post(
            url,
            data={
                "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ZkAAAAASUVORK5CYII=",
                "meal_photo_id": str(meal_photo.id),
            },
            format="json",
        )

        # Should NOT return INVALID_STATUS (will proceed to normal processing)
        # Might return INVALID_IMAGE (because test image is corrupted) or 200/202
        # But definitely NOT 400 INVALID_STATUS
        assert response.status_code != 400 or response.json().get("error_code") != "INVALID_STATUS", (
            "Retry on FAILED photo should NOT return INVALID_STATUS"
        )
