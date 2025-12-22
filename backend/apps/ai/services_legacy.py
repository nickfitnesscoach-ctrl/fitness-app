"""
AI Recognition Service - Business Logic Layer.

This module orchestrates food recognition using the AI Proxy service.
The actual HTTP calls are delegated to apps.ai_proxy.
"""

from datetime import date
import logging
import time
from typing import Any, Dict, Optional

from apps.ai_proxy.service import AIProxyRecognitionService
from apps.billing.usage import DailyUsage
from apps.nutrition.models import FoodItem, Meal

logger = logging.getLogger(__name__)


def recognize_and_save_meal(
    user,
    image_file,
    image_data_url: str,
    meal_type: str,
    meal_date: date,
    description: str = "",
    comment: str = "",
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Recognize food from image and create Meal with FoodItems.

    Args:
        user: Django User instance
        image_file: Uploaded image file (ContentFile or UploadedFile)
        image_data_url: Base64 data URL of the image
        meal_type: Type of meal (BREAKFAST, LUNCH, DINNER, SNACK)
        meal_date: Date of the meal
        description: Optional user description
        comment: Optional user comment

    Returns:
        Dict with meal, recognized_items (from DB), recognition_time
        IMPORTANT: Items are returned from DB after refresh_from_db()
        to ensure consistency with async tasks behavior.

    Raises:
        AIProxyTimeoutError: If AI service times out
        Exception: If AI service fails
    """
    from django.db import transaction

    # 1. Create Meal and save photo
    if image_file:
        image_file.seek(0)

    meal = Meal.objects.create(user=user, meal_type=meal_type, date=meal_date, photo=image_file)
    logger.info(f"Created Meal id={meal.id} with photo for user {user.username}")

    # 2. Initialize AI Proxy service and recognize
    ai_service = AIProxyRecognitionService()

    recognition_start = time.time()
    logger.info(f"Starting AI Proxy recognition for user {user.username}")

    result = ai_service.recognize_food(
        image_data_url,
        user_description=description,
        user_comment=comment,
        request_id=request_id,
    )
    recognition_elapsed = time.time() - recognition_start

    logger.info(
        f"AI recognition successful for user {user.username}. "
        f"Found {len(result.get('recognized_items', []))} items, "
        f"recognition_time={recognition_elapsed:.2f}s"
    )

    # 3. Save recognized items to Meal in transaction
    recognized_items = result.get("recognized_items", [])
    with transaction.atomic():
        for item in recognized_items:
            FoodItem.objects.create(
                meal=meal,
                name=item.get("name", "Unknown"),
                grams=item.get("estimated_weight", 100),
                calories=item.get("calories", 0),
                protein=item.get("protein", 0),
                fat=item.get("fat", 0),
                carbohydrates=item.get("carbohydrates", 0),
            )

        # 4. Increment photo usage counter inside transaction
        DailyUsage.objects.increment_photo_ai_requests(user)
        logger.info(f"Incremented photo counter for user {user.username}")

    # RACE CONDITION FIX: Return items from DB
    # This ensures consistency with async tasks behavior
    meal.refresh_from_db()
    db_items = list(meal.items.all())

    items_data = [
        {
            "id": str(item.id),
            "name": item.name,
            "grams": item.grams,
            "calories": float(item.calories),
            "protein": float(item.protein),
            "fat": float(item.fat),
            "carbohydrates": float(item.carbohydrates),
        }
        for item in db_items
    ]

    return {
        "meal": meal,
        "recognized_items": items_data,
        "recognition_time": recognition_elapsed,
    }
