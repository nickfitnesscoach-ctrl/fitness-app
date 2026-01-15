"""
Models for nutrition tracking - meals, food items, and daily goals.
"""

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.common.storage import upload_to_food_photos, upload_to_meal_photos
from apps.common.validators import FileSizeValidator, ImageDimensionValidator


class Meal(models.Model):
    """
    Represents a meal (breakfast, lunch, dinner, snack).

    Each meal belongs to a user and contains multiple food items.
    Supports multiple photos via MealPhoto model (one Meal → many photos).
    """

    MEAL_TYPE_CHOICES = [
        ("BREAKFAST", "Завтрак"),
        ("LUNCH", "Обед"),
        ("DINNER", "Ужин"),
        ("SNACK", "Перекус"),
    ]

    STATUS_CHOICES = [
        ("DRAFT", "Черновик"),  # Accepting new photos
        ("PROCESSING", "Обработка"),  # AI processing in progress
        ("COMPLETE", "Готово"),  # All photos processed
        ("FAILED", "Ошибка"),  # All photos failed
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meals",
        verbose_name="Пользователь",
    )
    meal_type = models.CharField(
        max_length=10, choices=MEAL_TYPE_CHOICES, verbose_name="Тип приёма пищи"
    )
    date = models.DateField(verbose_name="Дата")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="DRAFT", verbose_name="Статус"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    # DEPRECATED: Use MealPhoto model instead. Kept for backward compatibility.
    photo = models.ImageField(
        upload_to=upload_to_meal_photos,
        blank=True,
        null=True,
        verbose_name="Фотография приёма пищи (устаревшее)",
        validators=[
            FileSizeValidator(max_mb=10),
            ImageDimensionValidator(max_width=4096, max_height=4096),
        ],
    )

    class Meta:
        db_table = "nutrition_meals"
        verbose_name = "Приём пищи"
        verbose_name_plural = "Приёмы пищи"
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["date"]),
            # Index for draft meal lookup (grouping photos within time window)
            models.Index(fields=["user", "meal_type", "date", "status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_meal_type_display()} - {self.date} ({self.user.username})"

    @property
    def total_calories(self):
        """Calculate total calories for this meal."""
        return sum(item.calories for item in self.items.all())

    @property
    def total_protein(self):
        """Calculate total protein for this meal."""
        return sum(item.protein for item in self.items.all())

    @property
    def total_fat(self):
        """Calculate total fat for this meal."""
        return sum(item.fat for item in self.items.all())

    @property
    def total_carbohydrates(self):
        """Calculate total carbohydrates for this meal."""
        return sum(item.carbohydrates for item in self.items.all())


class FoodItem(models.Model):
    """
    Represents a food item within a meal.

    Contains nutrition information (KBJU) and optional photo.
    """

    meal = models.ForeignKey(
        Meal, on_delete=models.CASCADE, related_name="items", verbose_name="Приём пищи"
    )
    name = models.CharField(max_length=255, verbose_name="Название блюда")
    photo = models.ImageField(
        upload_to=upload_to_food_photos,
        blank=True,
        null=True,
        verbose_name="Фотография",
        validators=[
            FileSizeValidator(max_mb=10),  # Max 10MB per photo
            ImageDimensionValidator(max_width=4096, max_height=4096),  # Max 4K resolution
        ],
    )
    grams = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], verbose_name="Вес (граммы)"
    )
    calories = models.DecimalField(
        max_digits=7, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Калории"
    )
    protein = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Белки (г)"
    )
    fat = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Жиры (г)"
    )
    carbohydrates = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Углеводы (г)",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        db_table = "nutrition_food_items"
        verbose_name = "Блюдо"
        verbose_name_plural = "Блюда"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.name} ({self.grams}г)"

    @property
    def user(self):
        """Get user from parent meal."""
        return self.meal.user


class MealPhoto(models.Model):
    """
    Photo attached to a meal with its individual AI recognition results.

    Multiple photos can belong to one meal, enabling multi-photo meal logging.
    Each photo stores its own AI recognition data separately.
    """

    STATUS_CHOICES = [
        ("PENDING", "Ожидание"),
        ("PROCESSING", "Обработка"),
        ("SUCCESS", "Успешно"),
        ("FAILED", "Ошибка"),
        ("CANCELLED", "Отменено"),
    ]

    meal = models.ForeignKey(
        Meal, on_delete=models.CASCADE, related_name="photos", verbose_name="Приём пищи"
    )
    image = models.ImageField(
        upload_to=upload_to_meal_photos,
        verbose_name="Фотография",
        validators=[
            FileSizeValidator(max_mb=10),
            ImageDimensionValidator(max_width=4096, max_height=4096),
        ],
    )
    recognized_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Результат распознавания",
        help_text="Per-photo AI recognition result (items, totals, meta)",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="PENDING", verbose_name="Статус обработки"
    )
    error_message = models.TextField(blank=True, null=True, verbose_name="Сообщение об ошибке")
    error_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Код ошибки",
        help_text="Структурированный код ошибки: UPSTREAM_TIMEOUT, INVALID_IMAGE, RATE_LIMIT, etc.",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        db_table = "nutrition_meal_photos"
        verbose_name = "Фото приёма пищи"
        verbose_name_plural = "Фото приёмов пищи"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["meal", "status"]),
        ]

    def __str__(self):
        return f"Photo for {self.meal} ({self.get_status_display()})"

    @property
    def user(self):
        """Get user from parent meal."""
        return self.meal.user


class DailyGoal(models.Model):
    """
    Daily nutrition goals (KBJU targets) for a user.

    Can be automatically calculated using Harris-Benedict formula
    or manually set by the user.
    """

    SOURCE_CHOICES = [
        ("AUTO", "Автоматический расчет"),
        ("MANUAL", "Ручной ввод"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_goals",
        verbose_name="Пользователь",
    )
    calories = models.PositiveIntegerField(
        validators=[MinValueValidator(500)], verbose_name="Калории (цель)"
    )
    protein = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Белки (г, цель)",
    )
    fat = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Жиры (г, цель)",
    )
    carbohydrates = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Углеводы (г, цель)",
    )
    source = models.CharField(
        max_length=10, choices=SOURCE_CHOICES, default="AUTO", verbose_name="Источник"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        db_table = "nutrition_daily_goals"
        verbose_name = "Дневная цель"
        verbose_name_plural = "Дневные цели"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        status = "Активна" if self.is_active else "Неактивна"
        return f"Цель {self.user.username} - {self.calories} ккал ({status})"

    def save(self, *args, **kwargs):
        """Ensure only one active goal per user."""
        from django.db import transaction

        with transaction.atomic():
            if self.is_active:
                # Use select_for_update to prevent race conditions
                DailyGoal.objects.select_for_update().filter(
                    user=self.user, is_active=True
                ).exclude(pk=self.pk).update(is_active=False)
            super().save(*args, **kwargs)

    @classmethod
    def calculate_goals(cls, user):
        """
        Calculate daily nutrition goals using Mifflin-St Jeor formula.

        Formula:
        1. BMR (Basal Metabolic Rate):
           - BMR = 10 × weight_kg + 6.25 × height_cm - 5 × age + gender_factor
           - Men: gender_factor = +5
           - Women: gender_factor = -161

        2. TDEE (Total Daily Energy Expenditure) = BMR × activity_multiplier:
           - sedentary: 1.2
           - lightly_active: 1.375
           - moderately_active: 1.55
           - very_active: 1.725
           - extra_active: 1.9

        3. Goal adjustment:
           - weight_loss: TDEE × 0.8 (-20%)
           - maintenance: TDEE (no adjustment)
           - weight_gain: TDEE × 1.2 (+20%)

        4. Macros distribution:
           - Protein: 30% of calories (1g = 4 kcal)
           - Fat: 25% of calories (1g = 9 kcal)
           - Carbs: 45% of calories (1g = 4 kcal)

        Returns:
            dict with calories, protein, fat, carbohydrates
        """
        profile = user.profile

        # Validate required profile data
        if not all([profile.gender, profile.birth_date, profile.height, profile.weight]):
            raise ValueError("Необходимо заполнить профиль: пол, дата рождения, рост, вес")

        age = profile.age
        if age is None:
            raise ValueError("Не удалось рассчитать возраст")

        weight = float(profile.weight)
        height = profile.height

        # Validate ranges for realistic BMR calculation
        if not (10 <= age <= 120):
            raise ValueError("Возраст должен быть от 10 до 120 лет")
        if not (20 <= weight <= 500):
            raise ValueError("Вес должен быть от 20 до 500 кг")
        if not (50 <= height <= 250):
            raise ValueError("Рост должен быть от 50 до 250 см")

        # Calculate BMR using Mifflin-St Jeor formula
        bmr = 10 * weight + 6.25 * height - 5 * age
        if profile.gender == "M":
            bmr += 5
        else:  # 'F'
            bmr -= 161

        # Apply activity multiplier
        activity_multipliers = {
            "sedentary": 1.2,
            "lightly_active": 1.375,
            "moderately_active": 1.55,
            "very_active": 1.725,
            "extra_active": 1.9,
        }
        multiplier = activity_multipliers.get(profile.activity_level, 1.2)
        tdee = bmr * multiplier

        # Apply goal_type adjustment
        if profile.goal_type == "weight_loss":
            tdee = tdee * 0.8  # -20% for weight loss
        elif profile.goal_type == "weight_gain":
            tdee = tdee * 1.2  # +20% for weight gain
        # else: maintenance - no adjustment

        # Calculate macros
        calories = int(tdee)
        protein = (calories * 0.30) / 4  # 30% of calories, 1g = 4 kcal
        fat = (calories * 0.25) / 9  # 25% of calories, 1g = 9 kcal
        carbs = (calories * 0.45) / 4  # 45% of calories, 1g = 4 kcal

        return {
            "calories": calories,
            "protein": round(protein, 2),
            "fat": round(fat, 2),
            "carbohydrates": round(carbs, 2),
        }


class CancelEvent(models.Model):
    """
    Audit log for cancel requests from frontend.

    Tracks every cancel button press, even if there are no active tasks to cancel.
    Ensures idempotency via unique client_cancel_id.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cancel_events",
        verbose_name="Пользователь",
    )
    client_cancel_id = models.UUIDField(
        unique=True,
        db_index=True,
        verbose_name="Идентификатор отмены (клиент)",
        help_text="UUID генерируется на фронте для идемпотентности",
    )
    run_id = models.IntegerField(
        blank=True, null=True, verbose_name="Run ID", help_text="Frontend run identifier"
    )
    meal = models.ForeignKey(
        Meal,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="cancel_events",
        verbose_name="Приём пищи",
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Полный payload запроса",
        help_text="Сохраняет весь запрос для аудита: task_ids, meal_photo_ids, reason, etc.",
    )
    cancelled_tasks = models.IntegerField(
        default=0, verbose_name="Отменено задач", help_text="Количество отозванных Celery tasks"
    )
    updated_photos = models.IntegerField(
        default=0,
        verbose_name="Обновлено фото",
        help_text="Количество MealPhoto обновлённых в CANCELLED",
    )
    noop = models.BooleanField(
        default=False,
        verbose_name="Noop",
        help_text="True если отменять было нечего (ранний cancel)",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        db_table = "nutrition_cancel_events"
        verbose_name = "Событие отмены"
        verbose_name_plural = "События отмены"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["client_cancel_id"]),
        ]

    def __str__(self):
        noop_str = " (noop)" if self.noop else ""
        return f"Cancel by {self.user.username} - run_id={self.run_id}{noop_str} ({self.created_at})"
