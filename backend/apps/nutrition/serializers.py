# -*- coding: utf-8 -*-
"""
Serializers for nutrition app - meals, food items, daily goals.
"""

from datetime import date
from rest_framework import serializers
from .models import Meal, FoodItem, DailyGoal


class FoodItemSerializer(serializers.ModelSerializer):
    """Serializer for FoodItem model."""

    # Override photo field to return relative URL (not absolute)
    # This prevents Django from returning internal Docker URLs like http://backend:8000/media/...
    photo = serializers.SerializerMethodField()

    class Meta:
        model = FoodItem
        fields = [
            'id', 'name', 'photo', 'grams',
            'calories', 'protein', 'fat', 'carbohydrates',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_photo(self, obj):
        """Return relative URL for photo (not absolute)."""
        if obj.photo:
            # Return only the relative path (e.g., /media/meals/photo.jpg)
            # This works in both local and production environments
            return obj.photo.url
        return None

    def validate_grams(self, value):
        """Validate that grams is positive."""
        if value <= 0:
            # B-007 FIX: Fixed encoding - proper UTF-8 Cyrillic
            raise serializers.ValidationError("Вес должен быть больше 0")
        return value

    def validate_calories(self, value):
        """Validate that calories is non-negative."""
        if value < 0:
            # B-007 FIX: Fixed encoding - proper UTF-8 Cyrillic
            raise serializers.ValidationError("Калории не могут быть отрицательными")
        return value


class NutritionTotalsSerializer(serializers.Serializer):
    """Serializer for nutrition totals (KBJU summary)."""

    calories = serializers.DecimalField(max_digits=7, decimal_places=2)
    protein = serializers.DecimalField(max_digits=6, decimal_places=2)
    fat = serializers.DecimalField(max_digits=6, decimal_places=2)
    carbohydrates = serializers.DecimalField(max_digits=6, decimal_places=2)


class MealSerializer(serializers.ModelSerializer):
    """Serializer for Meal model with nested food items."""

    items = FoodItemSerializer(many=True, read_only=True)
    meal_type_display = serializers.CharField(source='get_meal_type_display', read_only=True)
    total = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Meal
        fields = [
            'id', 'meal_type', 'meal_type_display', 'date',
            'created_at', 'items', 'total', 'photo_url'
        ]
        read_only_fields = ['id', 'created_at']

    def get_total(self, obj):
        """Calculate total nutrition for all items in meal."""
        return {
            'calories': float(obj.total_calories),
            'protein': float(obj.total_protein),
            'fat': float(obj.total_fat),
            'carbohydrates': float(obj.total_carbohydrates),
        }

    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.photo and hasattr(obj.photo, "url"):
            url = obj.photo.url
            if request is not None:
                return request.build_absolute_uri(url)
            return url
        return None

    def validate_date(self, value):
        """Validate that date is not in the future."""
        if value > date.today():
            # B-007 FIX: Fixed encoding - proper UTF-8 Cyrillic
            raise serializers.ValidationError("Дата не может быть в будущем")
        return value


class MealCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a meal (without items)."""

    class Meta:
        model = Meal
        fields = ['id', 'meal_type', 'date', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_date(self, value):
        """Validate that date is not in the future."""
        if value > date.today():
            # B-007 FIX: Fixed encoding - proper UTF-8 Cyrillic
            raise serializers.ValidationError("Дата не может быть в будущем")
        return value

    def create(self, validated_data):
        """Create meal for current user."""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class FoodItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a food item."""

    meal_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = FoodItem
        fields = [
            'id', 'meal_id', 'name', 'photo', 'grams',
            'calories', 'protein', 'fat', 'carbohydrates',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_meal_id(self, value):
        """Validate that meal exists and belongs to current user."""
        request = self.context.get('request')
        try:
            meal = Meal.objects.get(id=value, user=request.user)
        except Meal.DoesNotExist:
            # B-007 FIX: Fixed encoding - proper UTF-8 Cyrillic
            raise serializers.ValidationError("Приём пищи не найден")
        return value

    def create(self, validated_data):
        """Create food item for specified meal."""
        meal_id = validated_data.pop('meal_id')
        meal = Meal.objects.get(id=meal_id)
        validated_data['meal'] = meal
        return super().create(validated_data)


class DailyGoalSerializer(serializers.ModelSerializer):
    """Serializer for DailyGoal model."""

    class Meta:
        model = DailyGoal
        fields = [
            'id', 'calories', 'protein', 'fat', 'carbohydrates',
            'source', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_calories(self, value):
        """Validate that calories is reasonable."""
        if value < 500:
            # B-007 FIX: Fixed encoding - proper UTF-8 Cyrillic
            raise serializers.ValidationError("Минимальная цель калорий: 500 ккал")
        if value > 10000:
            # B-007 FIX: Fixed encoding - proper UTF-8 Cyrillic
            raise serializers.ValidationError("Максимальная цель калорий: 10000 ккал")
        return value

    def create(self, validated_data):
        """Create daily goal for current user."""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated")

        validated_data['user'] = request.user

        # Деактивируем все предыдущие цели при создании новой активной
        if validated_data.get('is_active', True):
            DailyGoal.objects.filter(user=request.user, is_active=True).update(is_active=False)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update daily goal ensuring user ownership."""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated")

        # Verify ownership
        if instance.user != request.user:
            raise serializers.ValidationError("Cannot update goal of another user")

        # Если устанавливаем is_active=True, деактивируем другие цели
        if validated_data.get('is_active', False) and not instance.is_active:
            DailyGoal.objects.filter(
                user=request.user,
                is_active=True
            ).exclude(id=instance.id).update(is_active=False)

        return super().update(instance, validated_data)


class DailyStatsSerializer(serializers.Serializer):
    """Serializer for daily statistics."""

    date = serializers.DateField()
    daily_goal = DailyGoalSerializer(read_only=True)
    total_consumed = NutritionTotalsSerializer(read_only=True)
    progress = serializers.DictField(read_only=True)
    meals = MealSerializer(many=True, read_only=True)


class CalculateGoalsSerializer(serializers.Serializer):
    """Serializer for calculate goals request."""

    calories = serializers.IntegerField(read_only=True)
    protein = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    fat = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    carbohydrates = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
