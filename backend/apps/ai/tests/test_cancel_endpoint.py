"""
Tests for POST /api/v1/ai/cancel/ endpoint.

Acceptance Criteria:
- AC-1: Cancel всегда фиксируется в логах (даже noop)
- AC-2: Cancel с идентификаторами меняет БД (MealPhoto.status = CANCELLED)
- AC-3: Идемпотентность (дубликат client_cancel_id → не создаёт дубликат event)
- AC-4: Не ломает existing flows (retry, normal processing)
"""

import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.nutrition.models import CancelEvent, Meal, MealPhoto

User = get_user_model()


class CancelEndpointTestCase(TestCase):
    """Tests for POST /api/v1/ai/cancel/ endpoint."""

    def setUp(self):
        """Create test user and client."""
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse("ai:cancel")

    def _create_meal_with_photo(self, photo_status="PENDING"):
        """Helper: создать meal + photo для тестов."""
        meal = Meal.objects.create(
            user=self.user, meal_type="LUNCH", date=date.today(), status="DRAFT"
        )
        photo = MealPhoto.objects.create(
            meal=meal, image="test.jpg", status=photo_status
        )
        return meal, photo

    def test_ac1_cancel_always_logged_even_noop(self):
        """
        AC-1: Cancel всегда фиксируется (даже если отменять нечего).

        Шаги:
        1. Отправить cancel без task_ids/meal_photo_ids
        2. Проверить: CancelEvent создан с noop=True
        3. Проверить: response.noop=True
        """
        client_cancel_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {"client_cancel_id": str(client_cancel_id), "run_id": 1, "reason": "user_cancel"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertTrue(response.data["cancel_received"])
        self.assertTrue(response.data["noop"])
        self.assertEqual(response.data["cancelled_tasks"], 0)
        self.assertEqual(response.data["updated_photos"], 0)

        # Проверка: CancelEvent создан в БД
        event = CancelEvent.objects.get(client_cancel_id=client_cancel_id)
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.run_id, 1)
        self.assertTrue(event.noop)
        self.assertEqual(event.cancelled_tasks, 0)
        self.assertEqual(event.updated_photos, 0)

    def test_ac2_cancel_updates_meal_photo_status(self):
        """
        AC-2: Cancel с meal_photo_ids обновляет MealPhoto.status = CANCELLED.

        Шаги:
        1. Создать meal + photo со status=PENDING
        2. Отправить cancel с meal_photo_ids=[photo.id]
        3. Проверить: photo.status стал CANCELLED
        4. Проверить: CancelEvent.updated_photos = 1
        """
        meal, photo = self._create_meal_with_photo(photo_status="PENDING")
        client_cancel_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {
                "client_cancel_id": str(client_cancel_id),
                "run_id": 2,
                "meal_id": meal.id,
                "meal_photo_ids": [photo.id],
                "reason": "user_cancel",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertFalse(response.data["noop"])
        self.assertEqual(response.data["updated_photos"], 1)

        # Проверка: photo.status обновлён
        photo.refresh_from_db()
        self.assertEqual(photo.status, "CANCELLED")

        # Проверка: CancelEvent создан с updated_photos=1
        event = CancelEvent.objects.get(client_cancel_id=client_cancel_id)
        self.assertEqual(event.updated_photos, 1)
        self.assertEqual(event.noop, False)

    def test_ac2_cancel_multiple_photos(self):
        """
        AC-2: Cancel может отменить несколько фото сразу.

        Шаги:
        1. Создать meal с 3 photos (все PENDING)
        2. Отправить cancel с meal_photo_ids=[id1, id2, id3]
        3. Проверить: все 3 photos стали CANCELLED
        4. Проверить: CancelEvent.updated_photos = 3
        """
        meal = Meal.objects.create(
            user=self.user, meal_type="LUNCH", date=date.today(), status="DRAFT"
        )
        photos = [
            MealPhoto.objects.create(meal=meal, image=f"test{i}.jpg", status="PENDING")
            for i in range(3)
        ]
        photo_ids = [p.id for p in photos]

        client_cancel_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {
                "client_cancel_id": str(client_cancel_id),
                "run_id": 3,
                "meal_id": meal.id,
                "meal_photo_ids": photo_ids,
                "reason": "user_cancel",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_photos"], 3)

        # Проверка: все photos стали CANCELLED
        for photo in photos:
            photo.refresh_from_db()
            self.assertEqual(photo.status, "CANCELLED")

    def test_ac2_cancel_does_not_update_terminal_photos(self):
        """
        AC-2: Cancel НЕ обновляет photos в terminal статусах (SUCCESS/FAILED/CANCELLED).

        Шаги:
        1. Создать 3 photos: SUCCESS, FAILED, CANCELLED
        2. Отправить cancel с их IDs
        3. Проверить: статусы НЕ изменились, updated_photos = 0
        """
        meal = Meal.objects.create(
            user=self.user, meal_type="LUNCH", date=date.today(), status="DRAFT"
        )
        photo_success = MealPhoto.objects.create(meal=meal, image="s.jpg", status="SUCCESS")
        photo_failed = MealPhoto.objects.create(meal=meal, image="f.jpg", status="FAILED")
        photo_cancelled = MealPhoto.objects.create(meal=meal, image="c.jpg", status="CANCELLED")

        client_cancel_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {
                "client_cancel_id": str(client_cancel_id),
                "meal_photo_ids": [photo_success.id, photo_failed.id, photo_cancelled.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_photos"], 0)
        self.assertTrue(response.data["noop"])

        # Проверка: статусы не изменились
        photo_success.refresh_from_db()
        photo_failed.refresh_from_db()
        photo_cancelled.refresh_from_db()

        self.assertEqual(photo_success.status, "SUCCESS")
        self.assertEqual(photo_failed.status, "FAILED")
        self.assertEqual(photo_cancelled.status, "CANCELLED")

    def test_ac3_idempotency_duplicate_client_cancel_id(self):
        """
        AC-3: Идемпотентность — дубликат client_cancel_id не создаёт новый event.

        Шаги:
        1. Отправить cancel с client_cancel_id=X
        2. Отправить ещё раз с тем же client_cancel_id=X
        3. Проверить: только 1 CancelEvent в БД
        4. Проверить: второй запрос вернул тот же результат (cached)
        """
        meal, photo = self._create_meal_with_photo(photo_status="PENDING")
        client_cancel_id = uuid.uuid4()

        payload = {
            "client_cancel_id": str(client_cancel_id),
            "run_id": 4,
            "meal_photo_ids": [photo.id],
        }

        # Первый запрос
        response1 = self.client.post(self.url, payload, format="json")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data["updated_photos"], 1)

        # Второй запрос (дубликат)
        response2 = self.client.post(self.url, payload, format="json")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data["updated_photos"], 1)  # Cached result
        self.assertIn("already processed", response2.data["message"].lower())

        # Проверка: только 1 CancelEvent в БД
        events = CancelEvent.objects.filter(client_cancel_id=client_cancel_id)
        self.assertEqual(events.count(), 1)

    def test_ac4_cancel_does_not_break_existing_flows(self):
        """
        AC-4: Cancel не ломает existing flows.

        Шаги:
        1. Создать meal с photo (status=PENDING)
        2. Отправить cancel (photo становится CANCELLED)
        3. Попробовать обновить photo вручную (как будто retry)
        4. Проверить: операция проходит без ошибок
        """
        meal, photo = self._create_meal_with_photo(photo_status="PENDING")
        client_cancel_id = uuid.uuid4()

        # Cancel photo
        response = self.client.post(
            self.url,
            {"client_cancel_id": str(client_cancel_id), "meal_photo_ids": [photo.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        photo.refresh_from_db()
        self.assertEqual(photo.status, "CANCELLED")

        # Попытка retry: обновить photo вручную (как будто новая обработка)
        photo.status = "PROCESSING"
        photo.save()

        photo.refresh_from_db()
        self.assertEqual(photo.status, "PROCESSING")

        # Всё работает, никаких constraint violations

    @patch("apps.ai.services.celery_app.control.revoke")
    def test_cancel_revokes_celery_tasks(self, mock_revoke):
        """
        Test: Cancel с task_ids отзывает Celery tasks.

        Шаги:
        1. Отправить cancel с task_ids=["task1", "task2"]
        2. Проверить: celery_app.control.revoke вызван 2 раза
        3. Проверить: CancelEvent.cancelled_tasks = 2
        """
        client_cancel_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {
                "client_cancel_id": str(client_cancel_id),
                "task_ids": ["task1", "task2"],
                "reason": "user_cancel",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cancelled_tasks"], 2)
        self.assertEqual(mock_revoke.call_count, 2)

        # Проверка: CancelEvent сохранён с cancelled_tasks=2
        event = CancelEvent.objects.get(client_cancel_id=client_cancel_id)
        self.assertEqual(event.cancelled_tasks, 2)

    def test_cancel_without_client_cancel_id_returns_400(self):
        """
        Test: Cancel без client_cancel_id возвращает 400 BAD REQUEST.

        Обязательное поле должно валидироваться сериализатором.
        """
        response = self.client.post(
            self.url, {"run_id": 5, "reason": "user_cancel"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check if error is in standard DRF format or wrapped format
        if "error" in response.data:
            self.assertIn("client_cancel_id", response.data["error"]["details"])
        else:
            self.assertIn("client_cancel_id", response.data)

    def test_cancel_with_invalid_uuid_returns_400(self):
        """
        Test: Cancel с невалидным UUID возвращает 400 BAD REQUEST.
        """
        response = self.client.post(
            self.url, {"client_cancel_id": "not-a-uuid", "run_id": 6}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check if error is in standard DRF format or wrapped format
        if "error" in response.data:
            self.assertIn("client_cancel_id", response.data["error"]["details"])
        else:
            self.assertIn("client_cancel_id", response.data)

    def test_cancel_only_updates_own_user_photos(self):
        """
        Test: Cancel обновляет только фото текущего пользователя (security).

        Шаги:
        1. Создать meal/photo для другого пользователя
        2. Попытаться отменить его photo через свой cancel
        3. Проверить: photo.status НЕ изменился, updated_photos = 0
        """
        other_user = User.objects.create_user(
            username="otheruser", email="other@test.com", password="otherpass123"
        )
        other_meal = Meal.objects.create(
            user=other_user, meal_type="LUNCH", date=date.today(), status="DRAFT"
        )
        other_photo = MealPhoto.objects.create(
            meal=other_meal, image="other.jpg", status="PENDING"
        )

        client_cancel_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {"client_cancel_id": str(client_cancel_id), "meal_photo_ids": [other_photo.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_photos"], 0)
        self.assertTrue(response.data["noop"])

        # Проверка: other_photo.status НЕ изменился
        other_photo.refresh_from_db()
        self.assertEqual(other_photo.status, "PENDING")

    def test_cancel_with_deleted_meal_id_does_not_crash(self):
        """
        Test: Cancel с meal_id удалённого meal не падает с 500.

        Сценарий:
        1. Создать meal
        2. Удалить meal
        3. Отправить cancel с meal_id удалённого meal
        4. Проверить: 200 OK
        5. Проверить: CancelEvent создан с meal=None
        6. Проверить: event.payload содержит meal_id для аудита

        Защита от race condition: frontend fire-and-forget cancel → meal deleted → cancel arrives.
        """
        meal = Meal.objects.create(
            user=self.user, meal_type="LUNCH", date=date.today(), status="DRAFT"
        )
        deleted_meal_id = meal.id

        # Удалить meal (симуляция race condition)
        meal.delete()

        client_cancel_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {
                "client_cancel_id": str(client_cancel_id),
                "run_id": 99,
                "meal_id": deleted_meal_id,
                "reason": "user_cancel",
            },
            format="json",
        )

        # AC-1: Никогда не падает с 500
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertTrue(response.data["cancel_received"])

        # AC-2: CancelEvent создан
        event = CancelEvent.objects.get(client_cancel_id=client_cancel_id)
        self.assertEqual(event.user, self.user)

        # AC-3: event.meal is None (because meal deleted)
        self.assertIsNone(event.meal)

        # AC-4: payload содержит meal_id для аудита
        self.assertEqual(event.payload["meal_id"], deleted_meal_id)
        self.assertTrue(event.noop)  # noop because meal not found

    def test_e2e_smoke_cancel_mid_processing_meal_exists(self):
        """
        E2E Smoke: Cancel mid-processing when meal exists.

        Сценарий:
        1. Создать meal + photo (PROCESSING)
        2. Отправить cancel с meal_id
        3. Проверить: 200 OK
        4. Проверить: CancelEvent.meal IS NOT NULL
        5. Проверить: photo.status = CANCELLED

        Expected: meal FK заполнен, cancel обработан успешно.
        """
        meal, photo = self._create_meal_with_photo(photo_status="PROCESSING")
        client_cancel_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {
                "client_cancel_id": str(client_cancel_id),
                "run_id": 100,
                "meal_id": meal.id,
                "meal_photo_ids": [photo.id],
                "reason": "user_cancel",
            },
            format="json",
        )

        # AC-1: 200 OK
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")

        # AC-2: CancelEvent created with meal FK populated
        event = CancelEvent.objects.get(client_cancel_id=client_cancel_id)
        self.assertIsNotNone(event.meal)
        self.assertEqual(event.meal.id, meal.id)

        # AC-3: Photo cancelled
        photo.refresh_from_db()
        self.assertEqual(photo.status, "CANCELLED")

        # AC-4: Not noop (because photo was updated)
        self.assertFalse(event.noop)
        self.assertEqual(event.updated_photos, 1)

    def test_e2e_smoke_cancel_after_meal_deletion(self):
        """
        E2E Smoke: Cancel after meal deletion (race condition).

        Сценарий:
        1. Создать meal
        2. Удалить meal
        3. Отправить cancel с meal_id (симуляция late arrival)
        4. Проверить: 200 OK
        5. Проверить: CancelEvent.meal IS NULL
        6. Проверить: payload содержит meal_id

        Expected: No crash, graceful handling of missing meal.
        """
        meal = Meal.objects.create(
            user=self.user, meal_type="LUNCH", date=date.today(), status="DRAFT"
        )
        deleted_meal_id = meal.id
        meal.delete()

        client_cancel_id = uuid.uuid4()

        response = self.client.post(
            self.url,
            {
                "client_cancel_id": str(client_cancel_id),
                "run_id": 101,
                "meal_id": deleted_meal_id,
                "reason": "user_cancel",
            },
            format="json",
        )

        # AC-1: 200 OK (no crash)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")

        # AC-2: CancelEvent created with meal=None
        event = CancelEvent.objects.get(client_cancel_id=client_cancel_id)
        self.assertIsNone(event.meal)

        # AC-3: Payload preserves meal_id for audit
        self.assertEqual(event.payload["meal_id"], deleted_meal_id)

        # AC-4: noop (because meal not found, no photos to update)
        self.assertTrue(event.noop)
