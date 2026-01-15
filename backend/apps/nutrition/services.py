"""
Business logic services for nutrition app.
"""

from datetime import date, timedelta
import logging
from typing import Dict, Optional, Tuple

from django.db import models, transaction
from django.utils import timezone

from .models import DailyGoal, Meal

logger = logging.getLogger(__name__)

# Time window for grouping photos into the same meal (in minutes)
DRAFT_WINDOW_MINUTES = 10


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
    # BR-1: Only show meals with at least one SUCCESS photo (exclude FAILED meals with all photos cancelled)
    # N+1 Prevention: Prefetch items and photos
    meals = (
        Meal.objects.filter(user=user, date=target_date)
        .exclude(status="FAILED")
        .prefetch_related("items")
        .prefetch_related("photos")  # Prevent N+1 when serializer accesses photos
    )

    # Calculate total consumed
    total_calories = sum(meal.total_calories for meal in meals)
    total_protein = sum(meal.total_protein for meal in meals)
    total_fat = sum(meal.total_fat for meal in meals)
    total_carbs = sum(meal.total_carbohydrates for meal in meals)

    # Calculate progress percentage
    if daily_goal:
        progress = {
            "calories": round((total_calories / daily_goal.calories * 100), 1)
            if daily_goal.calories
            else 0,
            "protein": round((float(total_protein) / float(daily_goal.protein) * 100), 1)
            if daily_goal.protein
            else 0,
            "fat": round((float(total_fat) / float(daily_goal.fat) * 100), 1)
            if daily_goal.fat
            else 0,
            "carbohydrates": round((float(total_carbs) / float(daily_goal.carbohydrates) * 100), 1)
            if daily_goal.carbohydrates
            else 0,
        }
    else:
        progress = {
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbohydrates": 0,
        }

    return {
        "date": target_date,
        "daily_goal": daily_goal,
        "total_consumed": {
            "calories": float(total_calories),
            "protein": float(total_protein),
            "fat": float(total_fat),
            "carbohydrates": float(total_carbs),
        },
        "progress": progress,
        "meals": meals,
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
        user=user, date__gte=start_date, date__lte=end_date
    ).prefetch_related("items")

    # Initialize daily data
    daily_data = {}
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        daily_data[current_date.isoformat()] = {
            "date": current_date.isoformat(),
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbs": 0,
        }

    # Sum up nutrition for each day
    for meal in meals:
        date_key = meal.date.isoformat()
        if date_key in daily_data:
            for item in meal.items.all():
                daily_data[date_key]["calories"] += float(item.calories)
                daily_data[date_key]["protein"] += float(item.protein)
                daily_data[date_key]["fat"] += float(item.fat)
                daily_data[date_key]["carbs"] += float(item.carbohydrates)

    # Calculate averages
    total_calories = sum(day["calories"] for day in daily_data.values())
    total_protein = sum(day["protein"] for day in daily_data.values())
    total_fat = sum(day["fat"] for day in daily_data.values())
    total_carbs = sum(day["carbs"] for day in daily_data.values())

    days_count = 7

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily_data": list(daily_data.values()),
        "averages": {
            "calories": round(total_calories / days_count, 1),
            "protein": round(total_protein / days_count, 1),
            "fat": round(total_fat / days_count, 1),
            "carbs": round(total_carbs / days_count, 1),
        },
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
        calories=goals["calories"],
        protein=goals["protein"],
        fat=goals["fat"],
        carbohydrates=goals["carbohydrates"],
        source="AUTO",
        is_active=True,
    )

    return daily_goal


def get_or_create_draft_meal(
    user, meal_type: str, meal_date: date, meal_id: Optional[int] = None
) -> Tuple[Meal, bool]:
    """
    Find an existing draft meal or create a new one for photo grouping.

    Grouping rules:
    1. If meal_id is provided and valid, use that meal
    2. Otherwise, look for a draft/processing meal with:
       - Same user, meal_type, date
       - Created within last DRAFT_WINDOW_MINUTES (10 min)
    3. If not found, create a new draft meal

    Args:
        user: Django User instance
        meal_type: Type of meal (BREAKFAST, LUNCH, DINNER, SNACK)
        meal_date: Date of the meal
        meal_id: Optional existing meal ID to attach to

    Returns:
        Tuple of (Meal, created) where created is True if new meal was made
    """
    with transaction.atomic():
        # Case 1: meal_id provided - verify ownership and use it
        if meal_id:
            meal = Meal.objects.select_for_update().filter(id=meal_id, user=user).first()
            if meal:
                logger.info(
                    "[MealService] Using existing meal_id=%s for user_id=%s", meal_id, user.id
                )
                return meal, False
            else:
                logger.warning(
                    "[MealService] meal_id=%s not found or not owned by user_id=%s, creating new",
                    meal_id,
                    user.id,
                )

        # Case 2: Look for existing draft meal within time window
        cutoff = timezone.now() - timedelta(minutes=DRAFT_WINDOW_MINUTES)

        existing_meal = (
            Meal.objects.select_for_update()
            .filter(
                user=user,
                meal_type=meal_type,
                date=meal_date,
                status__in=["DRAFT", "PROCESSING"],
                created_at__gte=cutoff,
            )
            .order_by("-created_at")
            .first()
        )

        if existing_meal:
            logger.info(
                "[MealService] Found existing draft meal_id=%s for user_id=%s (type=%s, date=%s)",
                existing_meal.id,
                user.id,
                meal_type,
                meal_date,
            )
            return existing_meal, False

        # Case 3: Create new draft meal
        new_meal = Meal.objects.create(
            user=user, meal_type=meal_type, date=meal_date, status="DRAFT"
        )
        logger.info(
            "[MealService] Created new draft meal_id=%s for user_id=%s (type=%s, date=%s)",
            new_meal.id,
            user.id,
            meal_type,
            meal_date,
        )
        return new_meal, True


def finalize_meal_if_complete(meal: Meal) -> None:
    """
    Check if all photos are processed and finalize meal status.

    Called after each photo is processed to update meal status:
    - If any photo is still PENDING/PROCESSING → do nothing
    - If all photos are FAILED → delete orphan meal
    - If at least one photo SUCCESS → set meal to COMPLETE

    Args:
        meal: Meal instance to check
    """
    with transaction.atomic():
        # Reload meal with lock
        meal = Meal.objects.select_for_update().get(id=meal.id)

        photos = meal.photos.all()
        if not photos.exists():
            # No photos at all - shouldn't happen, but handle gracefully
            logger.warning("[MealService] Meal %s has no photos, deleting orphan", meal.id)
            meal.delete()
            return

        # Check if any photos are still processing
        pending_or_processing = photos.filter(status__in=["PENDING", "PROCESSING"]).exists()
        if pending_or_processing:
            # Still processing
            if meal.status != "PROCESSING":
                meal.status = "PROCESSING"
                meal.save(update_fields=["status"])
            return

        # All photos are in terminal states (SUCCESS, FAILED, or CANCELLED)
        successful_photos = photos.filter(status="SUCCESS").exists()

        if successful_photos:
            # At least one success - mark meal as complete
            if meal.status != "COMPLETE":
                meal.status = "COMPLETE"
                meal.save(update_fields=["status"])
                logger.info("[MealService] Finalized meal_id=%s as COMPLETE", meal.id)
        else:
            # All photos failed or were cancelled
            if meal.status != "FAILED":
                meal.status = "FAILED"
                meal.save(update_fields=["status"])
                logger.info(
                    "[MealService] Finalized meal_id=%s as FAILED (all photos failed/cancelled)",
                    meal.id,
                )


def cleanup_orphan_meals(user, older_than_minutes: int = 30) -> int:
    """
    Clean up draft meals that have been stuck without photos.

    This is a maintenance function to clean up meals that:
    - Are in DRAFT status
    - Have no photos
    - Are older than specified minutes

    Args:
        user: Django User instance (or None for all users)
        older_than_minutes: Only clean up meals older than this

    Returns:
        Number of meals deleted
    """
    cutoff = timezone.now() - timedelta(minutes=older_than_minutes)

    queryset = (
        Meal.objects.filter(status="DRAFT", created_at__lt=cutoff)
        .annotate(photo_count=models.Count("photos"))
        .filter(photo_count=0)
    )

    if user:
        queryset = queryset.filter(user=user)

    count = queryset.count()
    if count > 0:
        queryset.delete()
        logger.info("[MealService] Cleaned up %s orphan draft meals", count)

    return count
