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
                image_bytes=b"\x89PNG\r\n\x1a\n" + b"x" * 10,
                mime_type="image/png",
                user_comment="",
                request_id="rid",
                user_id=user.id,
            )

        meal.refresh_from_db()
        items = list(meal.items.all())
        assert len(items) == 1
        assert items[0].grams == 1  # clamp сработал
        assert out["items"][0]["amount_grams"] == 1  # API uses amount_grams

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
                image_bytes=b"\x89PNG\r\n\x1a\n" + b"x" * 10,
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
                image_bytes=b"\x89PNG\r\n\x1a\n" + b"x" * 10,
                mime_type="image/png",
                user_comment="",
                request_id="rid",
                user_id=user.id,
            )

        meal.refresh_from_db()
        items = list(meal.items.all())
        assert len(items) == 2
        assert out["total_calories"] == 150.0

    def test_usage_incremented_after_success(self, django_user_model):
        """P0-1: After successful AI recognition, usage counter should increment."""
        user = django_user_model.objects.create_user(username="tu4", password="pass")
        meal = Meal.objects.create(user=user, meal_type="SNACK", date="2025-12-01")

        fake_result = Mock()
        fake_result.items = [
            {
                "name": "Test",
                "grams": 100,
                "calories": 100.0,
                "protein": 10.0,
                "fat": 5.0,
                "carbohydrates": 10.0,
                "confidence": 0.9,
            }
        ]
        fake_result.totals = {"calories": 100.0, "protein": 10.0, "fat": 5.0, "carbohydrates": 10.0}
        fake_result.meta = {}

        with patch("apps.ai.tasks.AIProxyService") as svc_cls:
            svc = svc_cls.return_value
            svc.recognize_food.return_value = fake_result

            with patch(
                "apps.billing.usage.DailyUsage.objects.increment_photo_ai_requests"
            ) as mock_increment:
                from apps.ai.tasks import recognize_food_async

                recognize_food_async.run(
                    meal_id=meal.id,
                    image_bytes=b"\x89PNG\r\n\x1a\n" + b"x" * 10,
                    mime_type="image/png",
                    user_comment="",
                    request_id="rid",
                    user_id=user.id,
                )

                # EXPECTED: Called once after success
                mock_increment.assert_called_once_with(user)

    def test_usage_not_incremented_on_ai_error(self, django_user_model):
        """P0-1: On AI error, usage counter should NOT increment."""
        from apps.ai_proxy import AIProxyValidationError

        user = django_user_model.objects.create_user(username="tu5", password="pass")
        meal = Meal.objects.create(user=user, meal_type="SNACK", date="2025-12-01")

        with patch("apps.ai.tasks.AIProxyService") as svc_cls:
            svc = svc_cls.return_value
            svc.recognize_food.side_effect = AIProxyValidationError("Bad image")

            with patch(
                "apps.billing.usage.DailyUsage.objects.increment_photo_ai_requests"
            ) as mock_increment:
                from apps.ai.tasks import recognize_food_async

                out = recognize_food_async.run(
                    meal_id=meal.id,
                    image_bytes=b"\x89PNG\r\n\x1a\n" + b"x" * 10,
                    mime_type="image/png",
                    user_comment="",
                    request_id="rid",
                    user_id=user.id,
                )

                # EXPECTED: Returns error payload, NOT raises
                assert out["error"] == "AI_ERROR"
                # EXPECTED: NOT called on error
                mock_increment.assert_not_called()
                # EXPECTED: Meal deleted
                assert not Meal.objects.filter(id=meal.id).exists()

    def test_meal_deleted_on_empty_result(self, django_user_model):
        """P0-2/P1-1: If AI returns success but no items, meal should be deleted."""
        user = django_user_model.objects.create_user(username="tu6", password="pass")
        meal = Meal.objects.create(user=user, meal_type="SNACK", date="2025-12-01")

        fake_result = Mock()
        fake_result.items = []  # Empty!
        fake_result.totals = {}
        fake_result.meta = {}

        with patch("apps.ai.tasks.AIProxyService") as svc_cls:
            svc = svc_cls.return_value
            svc.recognize_food.return_value = fake_result

            from apps.ai.tasks import recognize_food_async

            out = recognize_food_async.run(
                meal_id=meal.id,
                image_bytes=b"\x89PNG\r\n\x1a\n" + b"x" * 10,
                mime_type="image/png",
                user_id=user.id,
            )

            assert out["error"] == "EMPTY_RESULT"
            assert not Meal.objects.filter(id=meal.id).exists()

    def test_meal_deleted_on_controlled_error(self, django_user_model):
        """P0-2: If AI returns meta is_error, meal should be deleted."""
        user = django_user_model.objects.create_user(username="tu7", password="pass")
        meal = Meal.objects.create(user=user, meal_type="SNACK", date="2025-12-01")

        fake_result = Mock()
        fake_result.items = []
        fake_result.meta = {"is_error": True, "error_code": "BLURRY_IMAGE"}

        with patch("apps.ai.tasks.AIProxyService") as svc_cls:
            svc = svc_cls.return_value
            svc.recognize_food.return_value = fake_result

            from apps.ai.tasks import recognize_food_async

            out = recognize_food_async.run(
                meal_id=meal.id,
                image_bytes=b"\x89PNG\r\n\x1a\n" + b"x" * 10,
                mime_type="image/png",
                user_id=user.id,
            )

            assert out["error"] == "BLURRY_IMAGE"
            assert not Meal.objects.filter(id=meal.id).exists()

    def test_security_meal_ownership_isolation(self, django_user_model):
        """P0 Security: If meal_id belongs to another user, it must NOT be touched."""
        user_a = django_user_model.objects.create_user(
            username="user_a", password="pass", email="a@test.com"
        )
        user_b = django_user_model.objects.create_user(
            username="user_b", password="pass", email="b@test.com"
        )

        meal_a = Meal.objects.create(user=user_a, meal_type="SNACK", date="2025-12-01")

        fake_result = Mock()
        fake_result.items = []  # Force empty to see if it tries to delete
        fake_result.meta = {}

        with patch("apps.ai.tasks.AIProxyService") as svc_cls:
            svc = svc_cls.return_value
            svc.recognize_food.return_value = fake_result

            from apps.ai.tasks import recognize_food_async

            # User B tries to process using Meal A's ID
            recognize_food_async.run(
                meal_id=meal_a.id,
                image_bytes=b"\x89PNG\r\n\x1a\n" + b"x" * 10,
                mime_type="image/png",
                user_id=user_b.id,  # Different user!
            )

            # EXPECTED: meal_a still exists because ownership check failed (meal was None in task)
            assert Meal.objects.filter(id=meal_a.id).exists()

    def test_strict_meal_creation_only_on_success(self, django_user_model):
        """P1-1: Meal should be created ONLY if AI returns items."""
        user = django_user_model.objects.create_user(username="tu8", password="pass")

        fake_result = Mock()
        fake_result.items = [{"name": "Apple", "grams": 100, "calories": 52}]
        fake_result.totals = {"calories": 52}
        fake_result.meta = {}

        with patch("apps.ai.tasks.AIProxyService") as svc_cls:
            svc = svc_cls.return_value
            svc.recognize_food.return_value = fake_result

            from apps.ai.tasks import recognize_food_async

            out = recognize_food_async.run(
                meal_id=None,  # No meal provided
                meal_type="BREAKFAST",
                date="2025-12-01",
                image_bytes=b"\x89PNG\r\n\x1a\n" + b"x" * 10,
                mime_type="image/png",
                user_id=user.id,
            )

            new_meal_id = out["meal_id"]
            assert new_meal_id is not None
            assert Meal.objects.filter(id=new_meal_id, user=user).exists()
