"""
Celery tasks for async AI processing.

These tasks handle AI recognition in the background,
allowing the API to return immediately with a task ID.
"""

import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def recognize_food_async(self, meal_id: str, image_data: bytes, user_id: int):
    """
    Async task for AI food recognition.
    
    Args:
        meal_id: UUID of the created Meal
        image_data: Image bytes to process
        user_id: User ID for usage tracking
        
    Returns:
        dict with recognition results
    """
    from apps.nutrition.models import Meal, FoodItem
    from apps.ai_proxy.service import AIProxyRecognitionService
    from apps.billing.usage import DailyUsage
    from django.contrib.auth.models import User
    
    logger.info(f"[Task {self.request.id}] Starting AI recognition for meal {meal_id}")
    
    try:
        meal = Meal.objects.get(id=meal_id)
        user = User.objects.get(id=user_id)
        
        # Call AI service
        ai_service = AIProxyRecognitionService()
        result = ai_service.recognize_food(image_data)
        
        if result.get('success') and result.get('food_items'):
            # Create FoodItems
            food_items_created = []
            for item_data in result['food_items']:
                food_item = FoodItem.objects.create(
                    meal=meal,
                    name=item_data.get('name', 'Unknown'),
                    calories=item_data.get('calories', 0),
                    protein=item_data.get('protein', 0),
                    fat=item_data.get('fat', 0),
                    carbohydrates=item_data.get('carbs', 0),
                    weight_grams=item_data.get('weight', 100),
                )
                food_items_created.append(food_item.id)
            
            # Increment usage
            DailyUsage.objects.increment_photo_request(user)
            
            logger.info(
                f"[Task {self.request.id}] Recognition complete for meal {meal_id}. "
                f"Created {len(food_items_created)} food items."
            )
            
            return {
                'success': True,
                'meal_id': str(meal_id),
                'food_items_count': len(food_items_created),
                'food_item_ids': [str(fid) for fid in food_items_created],
            }
        else:
            error_msg = result.get('error', 'Unknown AI error')
            logger.error(f"[Task {self.request.id}] AI recognition failed: {error_msg}")
            
            # Mark meal as failed
            meal.delete()
            
            return {
                'success': False,
                'error': error_msg,
            }
            
    except Meal.DoesNotExist:
        logger.error(f"[Task {self.request.id}] Meal {meal_id} not found")
        return {'success': False, 'error': 'Meal not found'}
    except Exception as e:
        logger.error(f"[Task {self.request.id}] Error: {str(e)}", exc_info=True)
        raise  # Will trigger retry


@shared_task(bind=True)
def cleanup_stale_meals(self, hours: int = 24):
    """
    Cleanup meals that were created but never got food items.
    These are likely failed async tasks.
    
    Args:
        hours: Delete meals older than this with no food items
    """
    from apps.nutrition.models import Meal
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(hours=hours)
    
    stale_meals = Meal.objects.filter(
        created_at__lt=cutoff,
        items__isnull=True
    )
    
    count = stale_meals.count()
    stale_meals.delete()
    
    logger.info(f"[Task {self.request.id}] Cleaned up {count} stale meals")
    
    return {'deleted_count': count}
