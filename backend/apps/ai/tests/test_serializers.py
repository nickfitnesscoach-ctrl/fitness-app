"""
test_serializers.py — тесты валидации входных данных.

Проверяем:
- data_url работает
- image + data_url → ошибка
- ничего → ошибка
- defaults meal_type/date
"""

from __future__ import annotations

from django.utils import timezone
import pytest

from apps.ai.serializers import AIRecognizeRequestSerializer


@pytest.mark.django_db
class TestAISerializers:
    def test_data_url_valid(self):
        s = AIRecognizeRequestSerializer(data={"data_url": _small_png_data_url()})
        assert s.is_valid(), s.errors
        assert s.validated_data["meal_type"] == "SNACK"
        assert s.validated_data["date"] == timezone.localdate()
        assert "normalized_image" in s.validated_data

    def test_both_image_and_data_url_invalid(self):
        s = AIRecognizeRequestSerializer(data={"data_url": _small_png_data_url(), "image": "x"})
        assert not s.is_valid()

    def test_no_image_invalid(self):
        s = AIRecognizeRequestSerializer(data={})
        assert not s.is_valid()

    def test_meal_type_default(self):
        s = AIRecognizeRequestSerializer(data={"data_url": _small_png_data_url()})
        assert s.is_valid(), s.errors
        assert s.validated_data["meal_type"] == "SNACK"

    def test_meal_type_custom(self):
        s = AIRecognizeRequestSerializer(
            data={"data_url": _small_png_data_url(), "meal_type": "BREAKFAST"}
        )
        assert s.is_valid(), s.errors
        assert s.validated_data["meal_type"] == "BREAKFAST"

    def test_invalid_meal_type(self):
        s = AIRecognizeRequestSerializer(
            data={"data_url": _small_png_data_url(), "meal_type": "INVALID"}
        )
        assert not s.is_valid()
        assert "meal_type" in s.errors


def _small_png_data_url() -> str:
    """Минимальный валидный PNG 1x1 (base64)."""
    return (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+X2ZkAAAAASUVORK5CYII="
    )
