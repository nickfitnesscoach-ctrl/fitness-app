"""
Serializers for nutrition app - meals, food items, daily goals.
"""

from datetime import date
from rest_framework import serializers
from .models import Meal, FoodItem, DailyGoal


class FoodItemSerializer(serializers.ModelSerializer):
    """Serializer for FoodItem model."""

    class Meta:
        model = FoodItem
        fields = [
            'id', 'name', 'photo', 'grams',
            'calories', 'protein', 'fat', 'carbohydrates',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_grams(self, value):
        """Validate that grams is positive."""
        if value <= 0:
            raise serializers.ValidationError("5A 4>;65= 1KBL 1>;LH5 0")
        return value

    def validate_calories(self, value):
        """Validate that calories is non-negative."""
        if value < 0:
            raise serializers.ValidationError("0;>@88 =5 <>3CB 1KBL >B@8F0B5;L=K<8")
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

    class Meta:
        model = Meal
        fields = [
            'id', 'meal_type', 'meal_type_display', 'date',
            'created_at', 'items', 'total'
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

    def validate_date(self, value):
        """Validate that date is not in the future."""
        if value > date.today():
            raise serializers.ValidationError("0B0 =5 <>65B 1KBL 2 1C4CI5<")
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
            raise serializers.ValidationError("0B0 =5 <>65B 1KBL 2 1C4CI5<")
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
            raise serializers.ValidationError("@8Q< ?8I8 =5 =0945=")
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
            raise serializers.ValidationError("8=8<0;L=0O F5;L :0;>@89: 500 ::0;")
        if value > 10000:
            raise serializers.ValidationError("0:A8<0;L=0O F5;L :0;>@89: 10000 ::0;")
        return value

    def create(self, validated_data):
        """Create daily goal for current user."""
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


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
