"""
test_tasks.py — тесты Celery задачи recognize_food_async.

Проверяем:
- grams=0 → grams=1 (clamp)
- Decimal поля сохраняются корректно
- FoodItem создаётся в БД
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from apps.nutrition.models import Meal


@pytest.mark.django_db
class TestAITasks:
    def test_grams_zero_saved_as_one(self, django_user_model):
        user = django_user_model.objects.create_user(username="tu1", password="pass")
        meal = Meal.objects.create(user=user, meal_type="SNACK", date="2025-12-01")

        # service.recognize_food() вернёт items с grams=0
        fake_result = Mock()
        fake_result.items = [
            {
                "name": "Test Food",
                "grams": 0,
                "calories": 10.0,
                "protein": 1.0,
                "fat": 1.0,
                "carbohydrates": 1.0,
                "confidence": None,
            }
        ]
        fake_result.totals = {
            "calories": 10.0,
            "protein": 1.0,
            "fat": 1.0,
            "carbohydrates": 1.0,
        }
        fake_result.meta = {"request_id": "rid"}

        with patch("apps.ai.tasks.AIProxyService") as svc_cls:
            svc = svc_cls.return_value
            svc.recognize_food.return_value = fake_result

            from apps.ai.tasks import recognize_food_async

            out = recognize_food_async.run(
                meal_id=meal.id,
                image_bytes=b"x",
                mime_type="image/png",
                user_comment="",
                request_id="rid",
                user_id=user.id,
            )

        meal.refresh_from_db()
        items = list(meal.items.all())
        assert len(items) == 1
        assert items[0].grams == 1  # clamp сработал
        assert out["items"][0]["grams"] == 1

    def test_decimal_fields_saved_correctly(self, django_user_model):
        user = django_user_model.objects.create_user(username="tu2", password="pass")
        meal = Meal.objects.create(user=user, meal_type="SNACK", date="2025-12-01")

        fake_result = Mock()
        fake_result.items = [
            {
                "name": "Decimals",
                "grams": 100,
                "calories": "123.45",
                "protein": "10.5",
                "fat": "2.25",
                "carbohydrates": "30.0",
                "confidence": 0.9,
            }
        ]
        fake_result.totals = {
            "calories": 123.45,
            "protein": 10.5,
            "fat": 2.25,
            "carbohydrates": 30.0,
        }
        fake_result.meta = {}

        with patch("apps.ai.tasks.AIProxyService") as svc_cls:
            svc = svc_cls.return_value
            svc.recognize_food.return_value = fake_result

            from apps.ai.tasks import recognize_food_async

            recognize_food_async.run(
                meal_id=meal.id,
                image_bytes=b"x",
                mime_type="image/png",
                user_comment="",
                request_id="rid",
                user_id=user.id,
            )

        item = meal.items.first()
        assert float(item.calories) == 123.45
        assert float(item.protein) == 10.5
        assert float(item.fat) == 2.25
        assert float(item.carbohydrates) == 30.0

    def test_multiple_items_created(self, django_user_model):
        user = django_user_model.objects.create_user(username="tu3", password="pass")
        meal = Meal.objects.create(user=user, meal_type="LUNCH", date="2025-12-01")

        fake_result = Mock()
        fake_result.items = [
            {
                "name": "Item 1",
                "grams": 100,
                "calories": 100.0,
                "protein": 10.0,
                "fat": 5.0,
                "carbohydrates": 15.0,
                "confidence": 0.95,
            },
            {
                "name": "Item 2",
                "grams": 50,
                "calories": 50.0,
                "protein": 5.0,
                "fat": 2.0,
                "carbohydrates": 8.0,
                "confidence": 0.85,
            },
        ]
        fake_result.totals = {
            "calories": 150.0,
            "protein": 15.0,
            "fat": 7.0,
            "carbohydrates": 23.0,
        }
        fake_result.meta = {}

        with patch("apps.ai.tasks.AIProxyService") as svc_cls:
            svc = svc_cls.return_value
            svc.recognize_food.return_value = fake_result

            from apps.ai.tasks import recognize_food_async

            out = recognize_food_async.run(
                meal_id=meal.id,
                image_bytes=b"x",
                mime_type="image/png",
                user_comment="",
                request_id="rid",
                user_id=user.id,
            )

        meal.refresh_from_db()
        items = list(meal.items.all())
        assert len(items) == 2
        assert out["total_calories"] == 150.0
