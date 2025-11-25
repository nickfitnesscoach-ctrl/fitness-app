"""
Models for users app.
"""

import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .validators import validate_avatar_file_extension, validate_avatar_file_size


class Profile(models.Model):
    """
    User profile model extending Django's built-in User model.
    Contains additional user information for FoodMind AI.
    """

    GENDER_CHOICES = [
        ('M', 'Мужской'),
        ('F', 'Женский'),
    ]

    ACTIVITY_LEVEL_CHOICES = [
        ('sedentary', 'Сидячий образ жизни'),
        ('lightly_active', 'Легкая активность (1-3 дня/неделю)'),
        ('moderately_active', 'Умеренная активность (3-5 дней/неделю)'),
        ('very_active', 'Высокая активность (6-7 дней/неделю)'),
        ('extra_active', 'Очень высокая активность (2 раза в день)'),
    ]

    GOAL_TYPE_CHOICES = [
        ('weight_loss', 'Похудение'),
        ('maintenance', 'Поддержание веса'),
        ('weight_gain', 'Набор массы'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='Пользователь'
    )

    email_verified = models.BooleanField(
        default=False,
        verbose_name='Email подтвержден',
        help_text='Был ли email адрес подтвержден пользователем'
    )

    full_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Полное имя'
    )

    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        null=True,
        verbose_name='Пол'
    )

    birth_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата рождения'
    )

    height = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Рост (см)',
        help_text='Рост в сантиметрах'
    )

    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Вес (кг)',
        help_text='Вес в килограммах'
    )

    activity_level = models.CharField(
        max_length=20,
        choices=ACTIVITY_LEVEL_CHOICES,
        default='sedentary',
        verbose_name='Уровень активности'
    )

    goal_type = models.CharField(
        max_length=20,
        choices=GOAL_TYPE_CHOICES,
        default='maintenance',
        verbose_name='Цель',
        help_text='Цель по весу: похудение, поддержание или набор массы'
    )

    target_weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Целевой вес (кг)',
        help_text='Желаемый вес в килограммах'
    )

    timezone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Часовой пояс',
        help_text='Часовой пояс пользователя (например, Europe/Moscow, Asia/Yekaterinburg)'
    )

    # Avatar
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        verbose_name='Аватар',
        help_text='Фото профиля пользователя (макс. 5 МБ, форматы: JPG, PNG, WebP)',
        validators=[
            validate_avatar_file_extension,
            validate_avatar_file_size,
        ]
    )

    avatar_version = models.PositiveIntegerField(
        default=0,
        verbose_name='Версия аватара',
        help_text='Версия аватара для cache busting (инкрементируется при каждой загрузке)'
    )

    # Данные из Telegram
    telegram_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name='Telegram ID',
        help_text='ID пользователя в Telegram'
    )

    telegram_username = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Telegram Username',
        help_text='@username пользователя в Telegram'
    )

    # Уровень тренированности
    TRAINING_LEVEL_CHOICES = [
        ('beginner', 'Новичок — не тренируюсь / реже 1 раза в неделю'),
        ('intermediate', 'Средний — 2-3 тренировки в неделю'),
        ('advanced', 'Продвинутый — 4+ тренировки в неделю'),
        ('home', 'Домашний формат — тренируюсь дома'),
    ]

    training_level = models.CharField(
        max_length=20,
        choices=TRAINING_LEVEL_CHOICES,
        blank=True,
        null=True,
        verbose_name='Уровень тренированности'
    )

    # Цели (множественный выбор - JSON)
    goals = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Цели',
        help_text='Список целей: weight_loss, remove_belly, tone_body и т.д.'
    )

    # Ограничения по здоровью (JSON)
    health_restrictions = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Ограничения по здоровью',
        help_text='Список ограничений: back_problems, joint_problems и т.д.'
    )

    # Тип фигуры
    current_body_type = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Текущий тип фигуры',
        help_text='Вариант от 1 до 4'
    )

    ideal_body_type = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Идеальный тип фигуры',
        help_text='Вариант от 1 до 4'
    )

    # AI рекомендации (полный текст от AI)
    ai_recommendations = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='AI рекомендации',
        help_text='Полный JSON с рекомендациями от AI: анализ, цели, изменения, тренировки, питание'
    )

    # Рекомендованные КБЖУ диапазоны от AI
    recommended_calories_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Калории минимум (ккал/день)'
    )

    recommended_calories_max = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Калории максимум (ккал/день)'
    )

    recommended_protein_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Белок минимум (г)'
    )

    recommended_protein_max = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Белок максимум (г)'
    )

    recommended_fat_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Жиры минимум (г)'
    )

    recommended_fat_max = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Жиры максимум (г)'
    )

    recommended_carbs_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Углеводы минимум (г)'
    )

    recommended_carbs_max = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='Углеводы максимум (г)'
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
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'
        ordering = ['-created_at']

    def __str__(self):
        return f"Profile of {self.user.username}"

    @property
    def age(self):
        """Calculate user age from birth_date."""
        if not self.birth_date:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
        )

    @property
    def bmi(self):
        """Calculate Body Mass Index (BMI)."""
        if not self.height or not self.weight:
            return None
        height_m = self.height / 100  # convert cm to meters
        return float(self.weight) / (height_m ** 2)

    @property
    def is_complete(self) -> bool:
        """
        Проверяет, заполнен ли профиль минимально необходимыми данными.

        Минимальные требования для онбординга:
        - пол (gender)
        - дата рождения (birth_date)
        - рост (height)
        - вес (weight)
        - тип цели (goal_type)
        """
        return all([
            bool(self.gender),
            bool(self.birth_date),
            bool(self.height),
            bool(self.weight),
            bool(self.goal_type),
        ])

    def set_avatar(self, new_avatar_file):
        """
        Safely set a new avatar, deleting the old one.

        Args:
            new_avatar_file: The new avatar file to set

        This method:
        1. Safely deletes the old avatar file if it exists
        2. Sets the new avatar
        3. Increments the avatar_version for cache busting
        4. Saves the profile
        """
        # Delete old avatar safely
        if self.avatar:
            old_avatar_path = self.avatar.name
            # Security check: ensure file is within MEDIA_ROOT
            if old_avatar_path and old_avatar_path.startswith('avatars/'):
                try:
                    # Use storage.delete to safely remove the file
                    from django.core.files.storage import default_storage
                    if default_storage.exists(old_avatar_path):
                        default_storage.delete(old_avatar_path)
                except Exception as e:
                    # Log error but don't fail the operation
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to delete old avatar {old_avatar_path}: {e}")

        # Set new avatar
        self.avatar = new_avatar_file

        # Increment version for cache busting
        self.avatar_version += 1

        # Save the profile
        self.save(update_fields=['avatar', 'avatar_version'])


class EmailVerificationToken(models.Model):
    """
    Token for email verification.
    Tokens expire after 24 hours.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='email_verification_tokens',
        verbose_name='Пользователь'
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        verbose_name='Токен',
        help_text='Уникальный токен для верификации email'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    expires_at = models.DateTimeField(
        verbose_name='Срок действия',
        help_text='Токен действителен в течение 24 часов'
    )
    is_used = models.BooleanField(
        default=False,
        verbose_name='Использован',
        help_text='Был ли токен использован для верификации'
    )
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата использования'
    )

    class Meta:
        verbose_name = 'Токен верификации email'
        verbose_name_plural = 'Токены верификации email'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user', 'is_used']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"EmailVerificationToken for {self.user.email}"

    def save(self, *args, **kwargs):
        """Generate token and expiration date on creation."""
        if not self.token:
            self.token = self.generate_token()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @staticmethod
    def generate_token():
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)

    @property
    def is_expired(self):
        """Check if token has expired."""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if token is valid (not used and not expired)."""
        return not self.is_used and not self.is_expired

    def mark_as_used(self):
        """Mark token as used."""
        self.is_used = True
        self.used_at = timezone.now()
        self.save(update_fields=['is_used', 'used_at'])


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal to automatically create Profile when User is created.
    """
    if created:
        Profile.objects.create(user=instance)
