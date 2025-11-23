"""
Telegram integration models.
"""

from django.contrib.auth.models import User
from django.db import models


class TelegramUser(models.Model):
    """
    Связь между Django User и Telegram аккаунтом.

    Хранит данные пользователя из Telegram и результаты лид-магнита (AI теста).
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='telegram_profile',
        verbose_name='Пользователь Django'
    )

    telegram_id = models.BigIntegerField(
        unique=True,
        db_index=True,
        verbose_name='Telegram ID',
        help_text='Уникальный ID пользователя в Telegram'
    )

    username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Telegram Username',
        help_text='@username пользователя (может отсутствовать)'
    )

    first_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Имя'
    )

    last_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Фамилия'
    )

    language_code = models.CharField(
        max_length=10,
        default='ru',
        verbose_name='Язык',
        help_text='Код языка пользователя (ru, en, etc.)'
    )

    is_premium = models.BooleanField(
        default=False,
        verbose_name='Telegram Premium',
        help_text='Является ли пользователь подписчиком Telegram Premium'
    )

    # Данные из лид-магнита (AI тест)
    ai_test_completed = models.BooleanField(
        default=False,
        verbose_name='AI тест пройден',
        help_text='Прошел ли пользователь лид-магнит тест'
    )

    ai_test_answers = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Ответы AI теста',
        help_text='JSON с ответами пользователя из лид-магнита'
    )

    # Статус клиента
    is_client = models.BooleanField(
        default=False,
        verbose_name='Клиент',
        help_text='Является ли пользователь клиентом (добавлен в список клиентов)'
    )

    # Рекомендованные значения КБЖУ из теста
    recommended_calories = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='Рекомендованные калории',
        help_text='Калории в день (расчет из AI теста)'
    )

    recommended_protein = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Рекомендованные белки (г)',
        help_text='Белки в граммах (расчет из AI теста)'
    )

    recommended_fat = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Рекомендованные жиры (г)',
        help_text='Жиры в граммах (расчет из AI теста)'
    )

    recommended_carbs = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Рекомендованные углеводы (г)',
        help_text='Углеводы в граммах (расчет из AI теста)'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Telegram пользователь'
        verbose_name_plural = 'Telegram пользователи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['telegram_id']),
            models.Index(fields=['ai_test_completed']),
            models.Index(fields=['is_client']),
        ]

    def __str__(self):
        return f"@{self.username or self.telegram_id} ({self.user.username})"

    @property
    def display_name(self):
        """Полное имя для отображения."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        return f"User {self.telegram_id}"
