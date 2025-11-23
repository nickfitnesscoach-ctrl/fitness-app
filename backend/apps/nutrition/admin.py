"""
Admin configuration for nutrition app.
"""

from django.contrib import admin
from .models import Meal, FoodItem, DailyGoal


class FoodItemInline(admin.TabularInline):
    """Inline admin for food items within meal."""
    model = FoodItem
    extra = 1
    fields = ['name', 'grams', 'calories', 'protein', 'fat', 'carbohydrates', 'photo']
    readonly_fields = []


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    """Admin for Meal model."""

    list_display = [
        'id', 'user', 'meal_type', 'date',
        'total_calories', 'total_protein', 'total_fat', 'total_carbohydrates',
        'created_at'
    ]
    list_filter = ['meal_type', 'date', 'created_at']
    search_fields = ['user__username', 'user__email']
    date_hierarchy = 'date'
    inlines = [FoodItemInline]
    readonly_fields = ['created_at', 'total_calories', 'total_protein', 'total_fat', 'total_carbohydrates']

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'meal_type', 'date')
        }),
        ('Итоги КБЖУ', {
            'fields': ('total_calories', 'total_protein', 'total_fat', 'total_carbohydrates'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def total_calories(self, obj):
        """Display total calories."""
        return f"{obj.total_calories:.2f} ккал"
    total_calories.short_description = 'Калории (всего)'

    def total_protein(self, obj):
        """Display total protein."""
        return f"{obj.total_protein:.2f} г"
    total_protein.short_description = 'Белки (всего)'

    def total_fat(self, obj):
        """Display total fat."""
        return f"{obj.total_fat:.2f} г"
    total_fat.short_description = 'Жиры (всего)'

    def total_carbohydrates(self, obj):
        """Display total carbohydrates."""
        return f"{obj.total_carbohydrates:.2f} г"
    total_carbohydrates.short_description = 'Углеводы (всего)'


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    """Admin for FoodItem model."""

    list_display = [
        'id', 'name', 'get_user', 'get_meal_type', 'get_meal_date',
        'grams', 'calories', 'protein', 'fat', 'carbohydrates',
        'created_at'
    ]
    list_filter = ['meal__meal_type', 'meal__date', 'created_at']
    search_fields = ['name', 'meal__user__username', 'meal__user__email']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('meal', 'name', 'photo', 'grams')
        }),
        ('КБЖУ', {
            'fields': ('calories', 'protein', 'fat', 'carbohydrates')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_user(self, obj):
        """Get username from meal."""
        return obj.meal.user.username
    get_user.short_description = 'Пользователь'
    get_user.admin_order_field = 'meal__user__username'

    def get_meal_type(self, obj):
        """Get meal type display."""
        return obj.meal.get_meal_type_display()
    get_meal_type.short_description = 'Тип приёма'
    get_meal_type.admin_order_field = 'meal__meal_type'

    def get_meal_date(self, obj):
        """Get meal date."""
        return obj.meal.date
    get_meal_date.short_description = 'Дата приёма'
    get_meal_date.admin_order_field = 'meal__date'


@admin.register(DailyGoal)
class DailyGoalAdmin(admin.ModelAdmin):
    """Admin for DailyGoal model."""

    list_display = [
        'id', 'user', 'calories', 'protein', 'fat', 'carbohydrates',
        'source', 'is_active', 'created_at'
    ]
    list_filter = ['source', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__email']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Пользователь', {
            'fields': ('user', 'is_active', 'source')
        }),
        ('Дневная цель КБЖУ', {
            'fields': ('calories', 'protein', 'fat', 'carbohydrates')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['activate_goals', 'deactivate_goals']

    def activate_goals(self, request, queryset):
        """Activate selected goals (only one per user will remain active)."""
        for goal in queryset:
            goal.is_active = True
            goal.save()  # save() method handles deactivating other goals
        self.message_user(request, f"Активировано целей: {queryset.count()}")
    activate_goals.short_description = "Активировать выбранные цели"

    def deactivate_goals(self, request, queryset):
        """Deactivate selected goals."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Деактивировано целей: {updated}")
    deactivate_goals.short_description = "Деактивировать выбранные цели"
