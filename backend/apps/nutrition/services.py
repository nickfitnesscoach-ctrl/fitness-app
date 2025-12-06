"""
Business logic services for nutrition app.
"""

from datetime import date, timedelta
from typing import Dict, Optional

from .models import Meal, DailyGoal


def get_daily_stats(user, target_date: date) -> Dict:
    """
    Get daily nutrition statistics for a user.
    
    Args:
        user: Django User instance
        target_date: Date to get stats for
        
    Returns:
        Dict with daily_goal, total_consumed, progress, meals
    """
    # Get active daily goal
    try:
        daily_goal = DailyGoal.objects.get(user=user, is_active=True)
    except DailyGoal.DoesNotExist:
        daily_goal = None

    # Get all meals for the date
    meals = Meal.objects.filter(user=user, date=target_date).prefetch_related('items')

    # Calculate total consumed
    total_calories = sum(meal.total_calories for meal in meals)
    total_protein = sum(meal.total_protein for meal in meals)
    total_fat = sum(meal.total_fat for meal in meals)
    total_carbs = sum(meal.total_carbohydrates for meal in meals)

    # Calculate progress percentage
    if daily_goal:
        progress = {
            'calories': round((total_calories / daily_goal.calories * 100), 1) if daily_goal.calories else 0,
            'protein': round((float(total_protein) / float(daily_goal.protein) * 100), 1) if daily_goal.protein else 0,
            'fat': round((float(total_fat) / float(daily_goal.fat) * 100), 1) if daily_goal.fat else 0,
            'carbohydrates': round((float(total_carbs) / float(daily_goal.carbohydrates) * 100), 1) if daily_goal.carbohydrates else 0,
        }
    else:
        progress = {
            'calories': 0,
            'protein': 0,
            'fat': 0,
            'carbohydrates': 0,
        }

    return {
        'date': target_date,
        'daily_goal': daily_goal,
        'total_consumed': {
            'calories': float(total_calories),
            'protein': float(total_protein),
            'fat': float(total_fat),
            'carbohydrates': float(total_carbs),
        },
        'progress': progress,
        'meals': meals,
    }


def get_weekly_stats(user, start_date: date) -> Dict:
    """
    Get weekly nutrition statistics for a user.
    
    Args:
        user: Django User instance
        start_date: Start date of the week
        
    Returns:
        Dict with start_date, end_date, daily_data, averages
    """
    end_date = start_date + timedelta(days=6)

    # Get all meals for the week
    meals = Meal.objects.filter(
        user=user,
        date__gte=start_date,
        date__lte=end_date
    ).prefetch_related('items')

    # Initialize daily data
    daily_data = {}
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        daily_data[current_date.isoformat()] = {
            'date': current_date.isoformat(),
            'calories': 0,
            'protein': 0,
            'fat': 0,
            'carbs': 0,
        }

    # Sum up nutrition for each day
    for meal in meals:
        date_key = meal.date.isoformat()
        if date_key in daily_data:
            for item in meal.items.all():
                daily_data[date_key]['calories'] += float(item.calories)
                daily_data[date_key]['protein'] += float(item.protein)
                daily_data[date_key]['fat'] += float(item.fat)
                daily_data[date_key]['carbs'] += float(item.carbohydrates)

    # Calculate averages
    total_calories = sum(day['calories'] for day in daily_data.values())
    total_protein = sum(day['protein'] for day in daily_data.values())
    total_fat = sum(day['fat'] for day in daily_data.values())
    total_carbs = sum(day['carbs'] for day in daily_data.values())

    days_count = 7

    return {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'daily_data': list(daily_data.values()),
        'averages': {
            'calories': round(total_calories / days_count, 1),
            'protein': round(total_protein / days_count, 1),
            'fat': round(total_fat / days_count, 1),
            'carbs': round(total_carbs / days_count, 1),
        }
    }


def create_auto_goal(user) -> DailyGoal:
    """
    Calculate and create a DailyGoal based on user profile.
    
    Args:
        user: Django User instance
        
    Returns:
        Created DailyGoal instance
        
    Raises:
        ValueError: If profile data is incomplete
    """
    goals = DailyGoal.calculate_goals(user)

    daily_goal = DailyGoal.objects.create(
        user=user,
        calories=goals['calories'],
        protein=goals['protein'],
        fat=goals['fat'],
        carbohydrates=goals['carbohydrates'],
        source='AUTO',
        is_active=True
    )

    return daily_goal
