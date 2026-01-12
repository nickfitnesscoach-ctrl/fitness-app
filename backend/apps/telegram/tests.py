"""
ТЕСТЫ ДЛЯ TELEGRAM APP: Personal Plan API

Зачем нужен этот файл:
- Это "страховка" от поломок. Когда ты меняешь код API (views/serializers/models),
  эти тесты сразу покажут, что сломалось.
- Особенно важно для прода: бот/фронт может работать, пока пользователи не упрутся
  в редкий сценарий (например, лимит планов). Тесты ловят это заранее.

Что именно проверяем:
1) users/get-or-create/ — получить существующего юзера или создать нового по telegram_id
2) personal-plan/survey/ — сохранить анкету (опрос)
3) personal-plan/plan/ — сохранить AI-план
4) personal-plan/count-today/ — счётчик планов "за сегодня" + лимиты

Важно:
- Это тесты, не прод-код. Тут нет "уязвимостей" как таковых.
- Но тесты фиксируют поведение API (контракт). Если контракт меняется — обновляем тесты.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import PersonalPlan, PersonalPlanSurvey, TelegramUser


class PersonalPlanAPITestCase(TestCase):
    """
    Набор интеграционных тестов для DRF эндпоинтов Telegram app.
    (Интеграционные = дергаем реальные URL через APIClient и проверяем ответ + базу.)
    """

    # "Магические числа" выносим в константы — проще поддерживать
    TG_ID_EXISTING = 123456789
    TG_ID_NEW = 987654321
    DAILY_LIMIT = 3

    @classmethod
    def setUpTestData(cls):
        """
        Создаём фикстуры один раз на весь класс (быстрее, чем setUp на каждый тест).
        """
        # Django user (обычный)
        cls.user = User.objects.create_user(
            username=f"tg_{cls.TG_ID_EXISTING}",
            email=f"test_{cls.TG_ID_EXISTING}@telegram.bot",
            first_name="Test User",
        )

        # Связка TelegramUser → Django User
        cls.telegram_user = TelegramUser.objects.create(
            user=cls.user,
            telegram_id=cls.TG_ID_EXISTING,
            username="testuser",
            first_name="Test",
            last_name="User",
        )

    def setUp(self):
        """
        Выполняется перед каждым тестом.
        Держим тут только то, что реально надо заново для каждого теста.
        """
        self.client = APIClient()
        # Добавляем секрет бота в заголовки (если настроен)
        self.bot_secret = getattr(settings, "TELEGRAM_BOT_API_SECRET", None)
        if self.bot_secret:
            self.client.credentials(HTTP_X_BOT_SECRET=self.bot_secret)

    # ---------------------------
    # helpers (чтобы не копипастить)
    # ---------------------------

    def _url(self, name: str) -> str:
        """Удобный шорткат для reverse()."""
        return reverse(name)

    def _survey_payload(self, **overrides) -> dict:
        """
        Базовый payload анкеты. В тестах мы меняем только нужные поля через overrides.
        """
        payload = {
            "telegram_id": self.TG_ID_EXISTING,
            "gender": "male",
            "age": 30,
            "height_cm": 180,
            "weight_kg": 80.5,
            "target_weight_kg": 75.0,
            "activity": "moderate",
            "training_level": "intermediate",
            "body_goals": ["weight_loss"],
            "health_limitations": [],
            "body_now_id": 2,
            "body_now_label": "Athletic",
            "body_now_file": "body_2.png",
            "body_ideal_id": 3,
            "body_ideal_label": "Fit",
            "body_ideal_file": "body_3.png",
            "timezone": "Europe/Moscow",
            "utc_offset_minutes": 180,
        }
        payload.update(overrides)
        return payload

    def _create_survey_in_db(self) -> PersonalPlanSurvey:
        """
        Создаём анкету напрямую в БД (без API), когда нужно подготовить данные для plan.
        """
        return PersonalPlanSurvey.objects.create(
            user=self.user,
            gender="male",
            age=30,
            height_cm=180,
            weight_kg=80.5,
            activity="moderate",
            body_now_id=2,
            body_now_file="body_2.png",
            body_ideal_id=3,
            body_ideal_file="body_3.png",
            timezone="Europe/Moscow",
            utc_offset_minutes=180,
        )

    # ---------------------------
    # tests: users/get-or-create
    # ---------------------------

    def test_get_user_or_create_existing(self):
        """
        Если telegram_id уже есть — API должен вернуть created=false.
        """
        url = self._url("telegram-user-get-or-create")

        response = self.client.get(
            url,
            {
                "telegram_id": self.TG_ID_EXISTING,
                "username": "testuser",
                "full_name": "Test User",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("telegram_id"), self.TG_ID_EXISTING)
        self.assertEqual(response.data.get("created"), False)

    def test_get_user_or_create_new(self):
        """
        Если telegram_id новый — API должен создать TelegramUser и вернуть created=true.
        """
        url = self._url("telegram-user-get-or-create")

        response = self.client.get(
            url,
            {
                "telegram_id": self.TG_ID_NEW,
                "username": "newuser",
                "full_name": "New User",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("telegram_id"), self.TG_ID_NEW)
        self.assertEqual(response.data.get("created"), True)

        # Проверяем, что запись реально появилась в базе
        self.assertTrue(TelegramUser.objects.filter(telegram_id=self.TG_ID_NEW).exists())

    def test_get_user_or_create_missing_telegram_id(self):
        """
        Если telegram_id не передан — ожидаем 400 и поле error в ответе.
        """
        url = self._url("telegram-user-get-or-create")
        response = self.client.get(url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    # ---------------------------
    # tests: personal-plan/survey
    # ---------------------------

    def test_create_survey(self):
        """
        Успешное создание анкеты: 201 + проверяем, что survey привязана к user.
        """
        url = self._url("personal-plan-create-survey")
        response = self.client.post(url, self._survey_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get("gender"), "male")
        self.assertEqual(response.data.get("age"), 30)

        self.assertEqual(PersonalPlanSurvey.objects.count(), 1)
        survey = PersonalPlanSurvey.objects.first()
        self.assertIsNotNone(survey)
        self.assertEqual(survey.user, self.user)

    def test_create_survey_invalid_data(self):
        """
        Невалидные данные анкеты должны вернуть 400.
        """
        url = self._url("personal-plan-create-survey")
        payload = self._survey_payload(gender="invalid")  # invalid choice

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------------------------
    # tests: personal-plan/plan
    # ---------------------------

    def test_create_plan(self):
        """
        Успешное создание плана: 201 + проверяем связь user ↔ survey ↔ plan.
        Также проверяем X-Request-ID и идемпотентность (200 на повтор).
        """
        survey = self._create_survey_in_db()

        url = self._url("personal-plan-create-plan")
        payload = {
            "telegram_id": self.TG_ID_EXISTING,
            "survey_id": survey.id,
            "ai_text": "Your personal plan...",
            "ai_model": "gpt-4",
            "prompt_version": "v1.0",
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get("ai_text"), "Your personal plan...")
        self.assertIn("X-Request-ID", response.headers)
        request_id = response.headers["X-Request-ID"]

        self.assertEqual(PersonalPlan.objects.count(), 1)
        plan = PersonalPlan.objects.first()
        self.assertIsNotNone(plan)
        self.assertEqual(plan.user, self.user)
        self.assertEqual(plan.survey, survey)

        # Повтор: должен вернуть тот же план (200 OK)
        response_retry = self.client.post(url, payload, format="json")
        self.assertEqual(response_retry.status_code, status.HTTP_200_OK)
        self.assertEqual(response_retry.data["id"], plan.id)
        self.assertIn("X-Request-ID", response_retry.headers)
        # RID должен быть новым (т.к. мы его не прокидывали, а бэк генерит если нет)
        self.assertNotEqual(response_retry.headers["X-Request-ID"], request_id)

    def test_create_plan_user_not_found(self):
        """
        Если telegram_id не существует — ожидаем 404.
        """
        url = self._url("personal-plan-create-plan")
        payload = {"telegram_id": 999999999, "ai_text": "Your personal plan..."}

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_plan_daily_limit(self):
        """
        Проверяем ограничение по числу планов в день.
        Сначала создаём LIMIT планов, потом пытаемся создать ещё один.
        """
        # Создаём максимальное число планов напрямую в БД
        for i in range(self.DAILY_LIMIT):
            PersonalPlan.objects.create(user=self.user, ai_text=f"Plan {i}")

        url = self._url("personal-plan-create-plan")
        payload = {"telegram_id": self.TG_ID_EXISTING, "ai_text": "One more plan"}

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(response.data["error"]["code"], "DAILY_LIMIT_REACHED")
        self.assertIn("X-Request-ID", response.headers)
        self.assertEqual(response.data["error"]["request_id"], response.headers["X-Request-ID"])

    # ---------------------------
    # tests: personal-plan/count-today
    # ---------------------------

    def test_count_plans_today(self):
        """
        Если у пользователя 2 плана за сегодня:
        - count=2
        - limit=DAILY_LIMIT
        - can_create=true
        """
        PersonalPlan.objects.create(user=self.user, ai_text="Plan 1")
        PersonalPlan.objects.create(user=self.user, ai_text="Plan 2")

        url = self._url("personal-plan-count-today")
        response = self.client.get(url, {"telegram_id": self.TG_ID_EXISTING})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("count"), 2)
        self.assertEqual(response.data.get("limit"), self.DAILY_LIMIT)
        self.assertEqual(response.data.get("can_create"), True)

    def test_count_plans_today_user_not_found(self):
        """
        Если telegram_id не найден — по контракту возвращаем:
        count=0, can_create=true (а не 404).
        """
        url = self._url("personal-plan-count-today")
        response = self.client.get(url, {"telegram_id": 999999999})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("count"), 0)
        self.assertEqual(response.data.get("limit"), self.DAILY_LIMIT)
        self.assertEqual(response.data.get("can_create"), True)

    def test_count_plans_today_missing_telegram_id(self):
        """
        telegram_id обязателен → если нет, то 400 и понятная ошибка.
        """
        url = self._url("personal-plan-count-today")
        response = self.client.get(url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("telegram_id is required", response.data.get("error", ""))

    def test_count_plans_today_invalid_telegram_id(self):
        """
        telegram_id должен быть числом → иначе 400.
        """
        url = self._url("personal-plan-count-today")
        response = self.client.get(url, {"telegram_id": "invalid_id"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("Invalid telegram_id", response.data.get("error", ""))

    def test_count_plans_today_limit_reached(self):
        """
        Если лимит достигнут:
        - count=DAILY_LIMIT
        - can_create=false
        """
        for i in range(self.DAILY_LIMIT):
            PersonalPlan.objects.create(user=self.user, ai_text=f"Plan {i + 1}")

        url = self._url("personal-plan-count-today")
        response = self.client.get(url, {"telegram_id": self.TG_ID_EXISTING})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("count"), self.DAILY_LIMIT)
        self.assertEqual(response.data.get("limit"), self.DAILY_LIMIT)
        self.assertEqual(response.data.get("can_create"), False)


class BotSecretProtectionTestCase(TestCase):
    """
    Тесты для проверки защиты Bot API через X-Bot-Secret заголовок.

    Критично для безопасности:
    - Без секрета все write-endpoints должны возвращать 403
    - С правильным секретом — работать нормально
    - В DEBUG режиме без секрета — разрешать доступ (для локальной разработки)
    """

    @classmethod
    def setUpTestData(cls):
        """Создаём тестовые данные."""
        cls.user = User.objects.create_user(
            username="tg_111222333",
            email="test@telegram.bot",
            first_name="Test",
        )
        cls.telegram_user = TelegramUser.objects.create(
            user=cls.user,
            telegram_id=111222333,
            username="testuser",
            first_name="Test",
            last_name="User",
        )

    def setUp(self):
        """Создаём клиент без секрета по умолчанию."""
        self.client = APIClient()
        self.test_secret = "test_bot_secret_12345"

    @override_settings(TELEGRAM_BOT_API_SECRET="test_bot_secret_12345", DEBUG=False)
    def test_write_endpoint_without_secret_returns_403(self):
        """
        В production (DEBUG=False) без секрета должен быть 403.
        Проверяем на примере get_user_or_create (он пишет в БД).
        """
        url = reverse("telegram-user-get-or-create")
        response = self.client.get(url, {"telegram_id": 999888777})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)
        error_msg = (
            response.data["error"]["message"]
            if isinstance(response.data["error"], dict)
            else response.data["error"]
        )
        self.assertIn("secret", error_msg.lower())

    @override_settings(TELEGRAM_BOT_API_SECRET="test_bot_secret_12345", DEBUG=False)
    def test_write_endpoint_with_wrong_secret_returns_403(self):
        """Неправильный секрет тоже должен давать 403."""
        self.client.credentials(HTTP_X_BOT_SECRET="wrong_secret")

        url = reverse("telegram-user-get-or-create")
        response = self.client.get(url, {"telegram_id": 999888777})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(TELEGRAM_BOT_API_SECRET="test_bot_secret_12345", DEBUG=False)
    def test_write_endpoint_with_correct_secret_works(self):
        """С правильным секретом должно работать."""
        self.client.credentials(HTTP_X_BOT_SECRET=self.test_secret)

        url = reverse("telegram-user-get-or-create")
        response = self.client.get(url, {"telegram_id": 999888777, "full_name": "New User"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(TelegramUser.objects.filter(telegram_id=999888777).exists())

    @override_settings(TELEGRAM_BOT_API_SECRET=None, DEBUG=True)
    def test_debug_mode_allows_requests_without_secret(self):
        """
        В DEBUG режиме без секрета в настройках разрешаем доступ
        (для локальной разработки).
        """
        url = reverse("telegram-user-get-or-create")
        response = self.client.get(url, {"telegram_id": 999888666, "full_name": "Debug User"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(TELEGRAM_BOT_API_SECRET="test_bot_secret_12345", DEBUG=False)
    def test_create_survey_requires_secret(self):
        """create_survey тоже должен требовать секрет."""
        url = reverse("personal-plan-create-survey")
        payload = {
            "telegram_id": 111222333,
            "gender": "male",
            "age": 25,
            "height_cm": 175,
            "weight_kg": 70,
            "activity": "moderate",
            "body_now_id": 1,
            "body_now_file": "body.png",
            "body_ideal_id": 2,
            "body_ideal_file": "ideal.png",
            "timezone": "UTC",
            "utc_offset_minutes": 0,
        }

        # Без секрета
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # С секретом
        self.client.credentials(HTTP_X_BOT_SECRET=self.test_secret)
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @override_settings(TELEGRAM_BOT_API_SECRET="test_bot_secret_12345", DEBUG=False)
    def test_create_plan_requires_secret(self):
        """create_plan тоже должен требовать секрет."""
        url = reverse("personal-plan-create-plan")
        payload = {
            "telegram_id": 111222333,
            "ai_text": "Your plan...",
            "ai_model": "gpt-4",
            "prompt_version": "v1",
        }

        # Без секрета
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # С секретом
        self.client.credentials(HTTP_X_BOT_SECRET=self.test_secret)
        response = self.client.post(url, payload, format="json")
        # Ожидаем 201 или любой не-403 код (user существует)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(TELEGRAM_BOT_API_SECRET="test_bot_secret_12345", DEBUG=False)
    def test_count_plans_today_requires_secret(self):
        """count_plans_today тоже защищён (чтобы не ддосили)."""
        url = reverse("personal-plan-count-today")

        # Без секрета
        response = self.client.get(url, {"telegram_id": 111222333})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # С секретом
        self.client.credentials(HTTP_X_BOT_SECRET=self.test_secret)
        response = self.client.get(url, {"telegram_id": 111222333})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_read_only_endpoint_is_public(self):
        """
        get_invite_link — read-only endpoint, должен работать без секрета.
        """
        url = reverse("telegram-get-invite-link")
        response = self.client.get(url)

        # Должен работать даже без секрета (но может вернуть ошибку если TELEGRAM_BOT_USERNAME не настроен)
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR]
        )

    @override_settings(TELEGRAM_BOT_API_SECRET="test_bot_secret_12345", DEBUG=False)
    def test_save_test_results_requires_secret(self):
        """save_test_results тоже должен требовать секрет."""
        url = reverse("save-test-results")
        payload = {
            "telegram_id": 111222333,
            "first_name": "Test",
            "last_name": "User",
            "username": "testuser",
            "answers": {
                "gender": "M",
                "age": 25,
                "weight": 70,
                "height": 175,
                "goal": "weight_loss",
                "activity_level": "medium",
            },
        }

        # Без секрета
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # С секретом
        self.client.credentials(HTTP_X_BOT_SECRET=self.test_secret)
        response = self.client.post(url, payload, format="json")
        # Ожидаем успех или ошибку не связанную с секретом
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)
