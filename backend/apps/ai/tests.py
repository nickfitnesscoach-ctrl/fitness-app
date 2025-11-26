"""
Tests for AI Recognition API.
"""

import base64
import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai.services import AIRecognitionService

User = get_user_model()


class AIRecognitionAPITestCase(APITestCase):
    """Test AI Recognition API endpoint."""

    def setUp(self):
        """Create test user and get valid test image."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        self.client.force_authenticate(user=self.user)
        self.url = reverse('ai:recognize-food')

        # Create a minimal valid JPEG image (1x1 pixel)
        # JPEG header + minimal data
        jpeg_data = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c'
            b'\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c'
            b'\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x0b\x08\x00'
            b'\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01'
            b'\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05'
            b'\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04'
            b'\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A'
            b'\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82'
            b'\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz'
            b'\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2'
            b'\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2'
            b'\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1'
            b'\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9'
            b'\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfe\xab\xff\xd9'
        )
        self.valid_image_base64 = base64.b64encode(jpeg_data).decode('utf-8')
        self.valid_image_data_url = f"data:image/jpeg;base64,{self.valid_image_base64}"

    def test_successful_recognition(self):
        """Test successful food recognition with mocked AI response."""
        mock_response = {
            "recognized_items": [
                {
                    "name": "Куриная грудка",
                    "confidence": 0.95,
                    "estimated_weight": 150,
                    "calories": 165,
                    "protein": 31.0,
                    "fat": 3.6,
                    "carbohydrates": 0.0
                },
                {
                    "name": "Рис отварной",
                    "confidence": 0.88,
                    "estimated_weight": 200,
                    "calories": 260,
                    "protein": 5.4,
                    "fat": 0.6,
                    "carbohydrates": 56.0
                }
            ]
        }

        with patch.object(AIRecognitionService, 'recognize_food', return_value=mock_response):
            response = self.client.post(
                self.url,
                data={
                    'image': self.valid_image_data_url,
                    'description': ''
                },
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Check response structure matches frontend expectations
        self.assertIn('recognized_items', data)
        self.assertIn('total_calories', data)
        self.assertIn('total_protein', data)
        self.assertIn('total_fat', data)
        self.assertIn('total_carbohydrates', data)

        # Check recognized items
        self.assertEqual(len(data['recognized_items']), 2)

        # Check field mapping (estimated_weight -> grams)
        first_item = data['recognized_items'][0]
        self.assertIn('grams', first_item)
        self.assertEqual(first_item['grams'], 150)
        self.assertEqual(first_item['name'], 'Куриная грудка')

        # Check totals calculation
        self.assertEqual(data['total_calories'], 425)  # 165 + 260
        self.assertEqual(data['total_protein'], 36.4)  # 31.0 + 5.4
        self.assertEqual(data['total_fat'], 4.2)  # 3.6 + 0.6
        self.assertEqual(data['total_carbohydrates'], 56.0)  # 0.0 + 56.0

    def test_empty_recognition(self):
        """Test when AI doesn't recognize any food."""
        mock_response = {
            "recognized_items": []
        }

        with patch.object(AIRecognitionService, 'recognize_food', return_value=mock_response):
            response = self.client.post(
                self.url,
                data={
                    'image': self.valid_image_data_url,
                    'description': ''
                },
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data['recognized_items']), 0)
        self.assertEqual(data['total_calories'], 0)
        self.assertEqual(data['total_protein'], 0)
        self.assertEqual(data['total_fat'], 0)
        self.assertEqual(data['total_carbohydrates'], 0)

    def test_ai_service_error(self):
        """Test handling of AI service errors."""
        with patch.object(
            AIRecognitionService,
            'recognize_food',
            side_effect=Exception('AI service unavailable')
        ):
            response = self.client.post(
                self.url,
                data={
                    'image': self.valid_image_data_url,
                    'description': ''
                },
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('detail', data)
        # Check standardized error code
        self.assertEqual(data['error'], 'AI_SERVICE_ERROR')
        self.assertIn('Сервис распознавания', data['detail'])

    def test_invalid_image_format(self):
        """Test validation of invalid image format."""
        response = self.client.post(
            self.url,
            data={
                'image': 'invalid-base64-data',
                'description': ''
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_image(self):
        """Test validation when image is missing."""
        response = self.client.post(
            self.url,
            data={
                'description': 'Test description'
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request(self):
        """Test that unauthenticated requests are rejected."""
        self.client.force_authenticate(user=None)

        response = self.client.post(
            self.url,
            data={
                'image': self.valid_image_data_url,
                'description': ''
            },
            format='json'
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
                    "carbohydrates": 48.0
                }
            ]
        }

        with patch.object(AIRecognitionService, 'recognize_food', return_value=mock_response):
            response = self.client.post(
                self.url,
                data={
                    'image': self.valid_image_data_url,
                    'description': 'Овсянка на молоке 2.5%, 1 ч.л. сахара'
                },
                format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data['recognized_items']), 1)
        self.assertIn('2.5%', data['recognized_items'][0]['name'])
