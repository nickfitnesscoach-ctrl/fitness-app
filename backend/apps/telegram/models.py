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


class PersonalPlanSurvey(models.Model):
    """
    Ответы пользователя на опрос Personal Plan (лид-магнит бота).

    Хранит данные, которые раньше находились в bot.SurveyAnswer.
    """

    GENDER_CHOICES = [
        ('male', 'Мужской'),
        ('female', 'Женский'),
    ]

    ACTIVITY_CHOICES = [
        ('sedentary', 'Сидячий образ жизни'),
        ('light', 'Легкая активность'),
        ('moderate', 'Умеренная активность'),
        ('active', 'Активный образ жизни'),
        ('very_active', 'Очень активный образ жизни'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='personal_plan_surveys',
        verbose_name='Пользователь'
    )

    # Демографические данные
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        verbose_name='Пол'
    )

    age = models.PositiveSmallIntegerField(
        verbose_name='Возраст',
        help_text='Возраст в годах (14-80)'
    )

    height_cm = models.PositiveSmallIntegerField(
        verbose_name='Рост (см)',
        help_text='Рост в сантиметрах (120-250)'
    )

    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Вес (кг)',
        help_text='Вес в килограммах (30-300)'
    )

    target_weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Целевой вес (кг)',
        help_text='Желаемый вес в килограммах'
    )

    activity = models.CharField(
        max_length=20,
        choices=ACTIVITY_CHOICES,
        verbose_name='Уровень активности'
    )

    # Дополнительные параметры
    training_level = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        verbose_name='Уровень тренированности',
        help_text='Например: beginner, intermediate, advanced, home'
    )

    body_goals = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Цели по телу',
        help_text='Список целей: weight_loss, remove_belly, tone_body и т.д.'
    )

    health_limitations = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Ограничения по здоровью',
        help_text='Список ограничений: back_problems, joint_problems и т.д.'
    )

    # Типы фигуры (текущий и идеальный)
    body_now_id = models.PositiveSmallIntegerField(
        verbose_name='ID текущего типа фигуры'
    )

    body_now_label = models.TextField(
        null=True,
        blank=True,
        verbose_name='Описание текущего типа фигуры'
    )

    body_now_file = models.TextField(
        verbose_name='Файл с текущим типом фигуры',
        help_text='Путь к файлу/изображению текущего типа фигуры'
    )

    body_ideal_id = models.PositiveSmallIntegerField(
        verbose_name='ID идеального типа фигуры'
    )

    body_ideal_label = models.TextField(
        null=True,
        blank=True,
        verbose_name='Описание идеального типа фигуры'
    )

    body_ideal_file = models.TextField(
        verbose_name='Файл с идеальным типом фигуры',
        help_text='Путь к файлу/изображению идеального типа фигуры'
    )

    # Часовой пояс
    timezone = models.CharField(
        max_length=64,
        default='Europe/Moscow',
        verbose_name='Часовой пояс',
        help_text='Часовой пояс пользователя (например, Europe/Moscow)'
    )

    utc_offset_minutes = models.IntegerField(
        verbose_name='Смещение UTC (минуты)',
        help_text='Смещение часового пояса от UTC в минутах'
    )

    # Метаданные
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата завершения',
        help_text='Когда пользователь завершил опрос'
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
        verbose_name = 'Опрос Personal Plan'
        verbose_name_plural = 'Опросы Personal Plan'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'completed_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Survey for {self.user.username} ({self.gender}, {self.age} y.o.)"


class PersonalPlan(models.Model):
    """
    AI-генерированные планы питания и тренировок (Personal Plan).

    Хранит данные, которые раньше находились в bot.Plan.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='personal_plans',
        verbose_name='Пользователь'
    )

    survey = models.ForeignKey(
        PersonalPlanSurvey,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='generated_plans',
        verbose_name='Опрос',
        help_text='Опрос, на основе которого был сгенерирован план'
    )

    # AI ответ
    ai_text = models.TextField(
        verbose_name='Текст плана от AI',
        help_text='Полный текст плана питания и тренировок от AI'
    )

    ai_model = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name='AI модель',
        help_text='Модель AI, которая сгенерировала план (например, meta-llama/llama-3.1-70b-instruct)'
    )

    prompt_version = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='Версия промпта',
        help_text='Версия промпта, использованного для генерации (например, v1.0)'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Personal Plan'
        verbose_name_plural = 'Personal Plans'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['survey']),
        ]

    def __str__(self):
        return f"Plan for {self.user.username} (model: {self.ai_model or 'unknown'})"
