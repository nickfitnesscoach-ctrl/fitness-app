"""
Модели Telegram интеграции.

Зачем этот файл:
- Храним связь "наш пользователь (Django User)" ↔ "пользователь Telegram"
- Храним результаты лид-магнита (AI тест)
- Храним анкету Personal Plan и сгенерированные планы

Важно:
- Это слой данных (DB). Тут должно быть максимально предсказуемо и аккуратно:
  валидировать базовые вещи, не хранить мусор, не ломать индексы.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


class TelegramUser(models.Model):
    """
    Telegram профиль пользователя.

    По сути: "расширение" Django User данными из Telegram.
    Также сюда складываем результаты лид-магнита (AI теста) и расчёты КБЖУ.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="telegram_profile",
        verbose_name="Пользователь Django",
    )

    telegram_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        verbose_name="Telegram ID",
        help_text="Уникальный ID пользователя в Telegram",
    )

    username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Telegram Username",
        help_text="@username пользователя (может отсутствовать)",
    )

    first_name = models.CharField(max_length=255, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=255, blank=True, verbose_name="Фамилия")

    language_code = models.CharField(
        max_length=10,
        default="ru",
        verbose_name="Язык",
        help_text="Код языка пользователя (ru, en, etc.)",
    )

    is_premium = models.BooleanField(
        default=False,
        verbose_name="Telegram Premium",
        help_text="Является ли пользователь подписчиком Telegram Premium",
    )

    # Лид-магнит (AI тест)
    ai_test_completed = models.BooleanField(
        default=False,
        verbose_name="AI тест пройден",
        help_text="Прошел ли пользователь лид-магнит тест",
    )

    ai_test_answers = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Ответы AI теста",
        help_text="JSON с ответами пользователя из лид-магнита",
    )

    # Статус клиента (для панели тренера)
    is_client = models.BooleanField(
        default=False,
        verbose_name="Клиент",
        help_text="Является ли пользователь клиентом (добавлен в список клиентов)",
    )

    # Рекомендации КБЖУ из теста
    recommended_calories = models.IntegerField(
        null=True, blank=True, verbose_name="Рекомендованные калории"
    )
    recommended_protein = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Рекомендованные белки (г)",
    )
    recommended_fat = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Рекомендованные жиры (г)",
    )
    recommended_carbs = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Рекомендованные углеводы (г)",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Telegram пользователь"
        verbose_name_plural = "Telegram пользователи"
        ordering = ["-created_at"]
        indexes = [
            # telegram_id уже db_index=True, но этот индекс исторически мог существовать.
            # Оставляем как есть, чтобы не трогать миграции прямо сейчас.
            models.Index(fields=["telegram_id"]),
            models.Index(fields=["ai_test_completed"]),
            models.Index(fields=["is_client"]),
        ]

    def __str__(self) -> str:
        # Человекочитаемое имя для админки/логов
        if self.username:
            return f"@{self.username} ({self.user.username})"
        return f"tg:{self.telegram_id} ({self.user.username})"

    @property
    def display_name(self) -> str:
        """Имя для отображения в UI."""
        full = f"{self.first_name} {self.last_name}".strip()
        if full:
            return full
        if self.username:
            return f"@{self.username}"
        return f"User {self.telegram_id}"

    def clean(self):
        """Базовая валидация на уровне модели (последний рубеж)."""
        if self.telegram_id is not None and self.telegram_id <= 0:
            raise ValidationError({"telegram_id": "Telegram ID должен быть положительным числом"})

        if self.language_code and len(self.language_code) > 10:
            raise ValidationError({"language_code": "Слишком длинный language_code"})

        # ai_test_answers лучше хранить как dict (если оно есть)
        if self.ai_test_answers is not None and not isinstance(self.ai_test_answers, dict):
            raise ValidationError(
                {"ai_test_answers": "ai_test_answers должен быть объектом (словарём)"}
            )


class PersonalPlanSurvey(models.Model):
    """
    Анкета пользователя перед генерацией персонального плана.

    Это "сырьё" для AI: возраст/рост/вес/цели/ограничения/тип фигуры/часовой пояс.
    """

    GENDER_CHOICES = [("male", "Мужской"), ("female", "Женский")]

    ACTIVITY_CHOICES = [
        ("sedentary", "Сидячий образ жизни"),
        ("light", "Легкая активность"),
        ("moderate", "Умеренная активность"),
        ("active", "Активный образ жизни"),
        ("very_active", "Очень активный образ жизни"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="personal_plan_surveys",
        verbose_name="Пользователь",
    )

    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, verbose_name="Пол")
    age = models.PositiveSmallIntegerField(
        verbose_name="Возраст", help_text="Возраст в годах (14-80)"
    )
    height_cm = models.PositiveSmallIntegerField(
        verbose_name="Рост (см)", help_text="Рост (120-250)"
    )
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Вес (кг)")
    target_weight_kg = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Целевой вес (кг)"
    )

    activity = models.CharField(
        max_length=20, choices=ACTIVITY_CHOICES, verbose_name="Уровень активности"
    )

    training_level = models.CharField(
        max_length=32, null=True, blank=True, verbose_name="Уровень тренированности"
    )

    body_goals = models.JSONField(default=list, blank=True, verbose_name="Цели по телу")
    health_limitations = models.JSONField(
        default=list, blank=True, verbose_name="Ограничения по здоровью"
    )

    body_now_id = models.PositiveSmallIntegerField(verbose_name="ID текущего типа фигуры")
    body_now_label = models.TextField(
        null=True, blank=True, verbose_name="Описание текущего типа фигуры"
    )
    body_now_file = models.TextField(verbose_name="Файл текущего типа фигуры")

    body_ideal_id = models.PositiveSmallIntegerField(verbose_name="ID идеального типа фигуры")
    body_ideal_label = models.TextField(
        null=True, blank=True, verbose_name="Описание идеального типа фигуры"
    )
    body_ideal_file = models.TextField(verbose_name="Файл идеального типа фигуры")

    timezone = models.CharField(
        max_length=64,
        default="Europe/Moscow",
        verbose_name="Часовой пояс",
        help_text="Например, Europe/Moscow",
    )
    utc_offset_minutes = models.IntegerField(verbose_name="Смещение UTC (минуты)")

    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата завершения")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Опрос Personal Plan"
        verbose_name_plural = "Опросы Personal Plan"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "completed_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"Survey for {self.user.username} ({self.gender}, {self.age} y.o.)"

    def clean(self):
        """Минимальная валидация диапазонов и типов."""
        if not (14 <= self.age <= 80):
            raise ValidationError({"age": "Возраст должен быть в диапазоне 14-80"})
        if not (120 <= self.height_cm <= 250):
            raise ValidationError({"height_cm": "Рост должен быть 120-250"})
        if self.utc_offset_minutes is None or not (-14 * 60 <= self.utc_offset_minutes <= 14 * 60):
            raise ValidationError(
                {"utc_offset_minutes": "Смещение UTC должно быть в минутах (-840..840)"}
            )

        if self.body_goals is not None and not isinstance(self.body_goals, list):
            raise ValidationError({"body_goals": "body_goals должен быть списком"})
        if self.health_limitations is not None and not isinstance(self.health_limitations, list):
            raise ValidationError({"health_limitations": "health_limitations должен быть списком"})


class PersonalPlan(models.Model):
    """
    Сгенерированный AI план питания/тренировок (Personal Plan).

    Важно:
    - ai_text может быть большим (TextField) — ок.
    - survey опционален: иногда план может быть сгенерирован без привязки.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="personal_plans", verbose_name="Пользователь"
    )

    survey = models.ForeignKey(
        PersonalPlanSurvey,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_plans",
        verbose_name="Опрос",
    )

    ai_text = models.TextField(verbose_name="Текст плана от AI")
    ai_model = models.CharField(max_length=100, null=True, blank=True, verbose_name="AI модель")
    prompt_version = models.CharField(
        max_length=20, null=True, blank=True, verbose_name="Версия промпта"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="Дата создания"
    )

    class Meta:
        verbose_name = "Personal Plan"
        verbose_name_plural = "Personal Plans"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["survey"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "survey"],
                name="unique_user_survey_plan",
                condition=models.Q(survey__isnull=False),
            )
        ]

    def __str__(self) -> str:
        return f"Plan for {self.user.username} (model: {self.ai_model or 'unknown'})"
