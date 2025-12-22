"""
Tests for AI Recognition API.

These tests mock the AI Proxy integration layer to test the business logic
in views without making real HTTP calls.
"""

import base64
import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai_proxy.exceptions import (
    AIProxyError,
    AIProxyTimeoutError,
    AIProxyValidationError,
)

User = get_user_model()


# Use in-memory cache for tests to avoid Redis dependency
TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-test-cache",
    }
}


def create_test_image_data_url() -> str:
    """Create a valid minimal JPEG data URL for testing."""
    img = Image.new("RGB", (50, 50), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=50)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


@override_settings(CACHES=TEST_CACHES)
class AIRecognitionAPITestCase(APITestCase):
    """Test AI Recognition API endpoint."""

    @classmethod
    def setUpClass(cls):
        """Generate test image once for all tests."""
        super().setUpClass()
        cls.valid_image_data_url = create_test_image_data_url()

    def setUp(self):
        """Create test user."""
        self.user = User.objects.create_user(
            username="testuser", password="testpass123", email="test@example.com"
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse("ai:recognize-food")

    def test_successful_recognition(self):
        """Test successful food recognition with mocked AI Proxy response."""
        mock_response = {
            "recognized_items": [
                {
                    "name": "Куриная грудка",
                    "confidence": 0.95,
                    "estimated_weight": 150,
                    "calories": 165,
                    "protein": 31.0,
                    "fat": 3.6,
                    "carbohydrates": 0.0,
                },
                {
                    "name": "Рис отварной",
                    "confidence": 0.88,
                    "estimated_weight": 200,
                    "calories": 260,
                    "protein": 5.4,
                    "fat": 0.6,
                    "carbohydrates": 56.0,
                },
            ]
        }

        with patch("apps.ai.services.AIProxyRecognitionService") as MockService:
            MockService.return_value.recognize_food.return_value = mock_response
            response = self.client.post(
                self.url,
                data={"image": self.valid_image_data_url, "description": ""},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Check response structure
        self.assertIn("recognized_items", data)
        self.assertIn("total_calories", data)
        self.assertEqual(len(data["recognized_items"]), 2)

        # Check X-Request-ID header
        self.assertIn("X-Request-ID", response)

    def test_empty_recognition(self):
        """Test when AI doesn't recognize any food."""
        mock_response = {"recognized_items": []}

        with patch("apps.ai.services.AIProxyRecognitionService") as MockService:
            MockService.return_value.recognize_food.return_value = mock_response
            response = self.client.post(
                self.url,
                data={"image": self.valid_image_data_url, "description": ""},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["recognized_items"]), 0)
        self.assertEqual(data["total_calories"], 0)

    def test_ai_service_error(self):
        """Test handling of AI service errors."""
        with patch("apps.ai.services.AIProxyRecognitionService") as MockService:
            MockService.return_value.recognize_food.side_effect = AIProxyError(
                "AI service unavailable"
            )
            response = self.client.post(
                self.url,
                data={"image": self.valid_image_data_url, "description": ""},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        data = response.json()
        self.assertEqual(data["error"], "AI_PROXY_ERROR")
        self.assertIn("X-Request-ID", response)

    def test_ai_proxy_timeout(self):
        """Test handling of AI Proxy timeout."""
        with patch("apps.ai.services.AIProxyRecognitionService") as MockService:
            MockService.return_value.recognize_food.side_effect = AIProxyTimeoutError(
                "Request timed out"
            )
            response = self.client.post(
                self.url,
                data={"image": self.valid_image_data_url, "description": ""},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = response.json()
        self.assertEqual(data["error"], "AI_SERVICE_TIMEOUT")
        self.assertIn("X-Request-ID", response)

    def test_ai_proxy_validation_error(self):
        """Test handling of AI Proxy validation errors."""
        with patch("apps.ai.services.AIProxyRecognitionService") as MockService:
            MockService.return_value.recognize_food.side_effect = AIProxyValidationError(
                "Invalid image format"
            )
            response = self.client.post(
                self.url,
                data={"image": self.valid_image_data_url, "description": ""},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["error"], "INVALID_IMAGE")
        self.assertIn("X-Request-ID", response)

    def test_invalid_image_format(self):
        """Test validation of invalid image format."""
        response = self.client.post(
            self.url,
            data={"image": "invalid-base64-data", "description": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_image(self):
        """Test validation when image is missing."""
        response = self.client.post(
            self.url, data={"description": "Test description"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request(self):
        """Test that unauthenticated requests are rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.post(
            self.url,
            data={"image": self.valid_image_data_url, "description": ""},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_with_user_description(self):
        """Test recognition with user-provided description."""
        mock_response = {
            "recognized_items": [
                {
                    "name": "Овсянка на молоке 2.5%",
                    "confidence": 0.92,
                    "estimated_weight": 300,
                    "calories": 320,
                    "protein": 12.5,
                    "fat": 8.2,
                    "carbohydrates": 48.0,
                }
            ]
        }

        with patch("apps.ai.services.AIProxyRecognitionService") as MockService:
            MockService.return_value.recognize_food.return_value = mock_response
            response = self.client.post(
                self.url,
                data={
                    "image": self.valid_image_data_url,
                    "description": "Овсянка на молоке 2.5%",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data["recognized_items"]), 1)
