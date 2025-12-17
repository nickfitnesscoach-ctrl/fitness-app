"""
billing/usage.py

Учёт использования (дневные лимиты фото/AI-запросов).

Это "счётчик", который нужен для:
- FREE лимитов (например 3 фото в день)
- контроля нагрузки/стоимости AI
- аналитики

Почему модель здесь (а не в models.py):
- исторически проект импортирует DailyUsage из billing.usage
- так проще не ломать миграции и импорты

Ключевые моменты надёжности:
- запись на день уникальна: (user, date)
- get_today использует get_or_create
- increment делаем через select_for_update внутри транзакции, чтобы не было race condition
"""

from __future__ import annotations

from datetime import date as dt_date

from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone


class DailyUsageManager(models.Manager):
    """Менеджер: удобные методы для работы с дневным использованием."""

    def get_today(self, user):
        """
        Получает или создаёт запись использования на сегодня.

        Возвращает DailyUsage.
        """
        today = timezone.now().date()
        usage, _ = self.get_or_create(
            user=user,
            date=today,
            defaults={"photo_ai_requests": 0},
        )
        return usage

    def increment_photo_ai_requests(self, user, amount: int = 1):
        """
        Увеличивает счётчик photo_ai_requests на today.

        Делается безопасно:
        - транзакция
        - блокировка строки (select_for_update) либо атомарный update

        Возвращает обновлённый DailyUsage.
        """
        if amount <= 0:
            return self.get_today(user)

        today = timezone.now().date()

        with transaction.atomic():
            usage, _ = self.select_for_update().get_or_create(
                user=user,
                date=today,
                defaults={"photo_ai_requests": 0},
            )

            # атомарно + без гонок
            self.filter(pk=usage.pk).update(photo_ai_requests=F("photo_ai_requests") + amount)

            # перечитываем актуальное значение
            usage.refresh_from_db(fields=["photo_ai_requests"])
            return usage

    def reset_today(self, user):
        """
        Обнуляет счётчик на сегодня (полезно для админских операций / тестов).
        """
        today = timezone.now().date()
        usage, _ = self.get_or_create(user=user, date=today, defaults={"photo_ai_requests": 0})
        usage.photo_ai_requests = 0
        usage.save(update_fields=["photo_ai_requests"])
        return usage


class DailyUsage(models.Model):
    """
    Учёт использования в разрезе "пользователь + день".
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_usage",
        verbose_name="Пользователь",
    )
    date = models.DateField("Дата", default=dt_date.today)

    photo_ai_requests = models.PositiveIntegerField(
        "Количество фото-запросов к AI",
        default=0,
        help_text="Сколько раз пользователь отправлял фото на распознавание за день",
    )

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    objects = DailyUsageManager()

    class Meta:
        verbose_name = "Ежедневное использование"
        verbose_name_plural = "Ежедневное использование"
        unique_together = [["user", "date"]]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["-date"]),
        ]

    def __str__(self) -> str:
        username = getattr(self.user, "username", None) or str(self.user_id)
        return f"{username} — {self.date}: {self.photo_ai_requests} фото"

    @property
    def is_today(self) -> bool:
        """True, если запись относится к сегодняшнему дню."""
        return self.date == timezone.now().date()
