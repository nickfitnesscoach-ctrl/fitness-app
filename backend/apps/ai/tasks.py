"""
Celery tasks for async AI processing.

These tasks handle AI recognition in the background,
allowing the API to return immediately with a task ID.
"""

import logging
import time
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='apps.ai.tasks.recognize_food_async',
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
)
def recognize_food_async(
    self,
    meal_id: str,
    image_data_url: str,
    user_id: int,
    description: str = "",
    comment: str = ""
):
    """
    Async task for AI food recognition.
    
    Args:
        meal_id: UUID of the created Meal
        image_data_url: Base64 data URL of the image
        user_id: User ID for usage tracking
        description: Optional user description
        comment: Optional user comment
        
    Returns:
        dict with full recognition results for frontend polling
    """
    from apps.nutrition.models import Meal, FoodItem
    from apps.ai_proxy.service import AIProxyRecognitionService
    from apps.billing.usage import DailyUsage
    from django.contrib.auth.models import User
    
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting AI recognition for meal {meal_id}")
    
    recognition_start = time.time()
    
    try:
        meal = Meal.objects.get(id=meal_id)
        user = User.objects.get(id=user_id)
        
        # Call AI Proxy service
        ai_service = AIProxyRecognitionService()
        result = ai_service.recognize_food(
            image_data_url,
            user_description=description,
            user_comment=comment
        )
        
        recognition_time = time.time() - recognition_start
        recognized_items = result.get('recognized_items', [])
        
        if recognized_items:
            # Create FoodItems for each recognized item
            food_items_data = []
            for item_data in recognized_items:
                food_item = FoodItem.objects.create(
                    meal=meal,
                    name=item_data.get('name', 'Unknown'),
                    grams=item_data.get('estimated_weight', 100),
                    calories=item_data.get('calories', 0),
                    protein=item_data.get('protein', 0),
                    fat=item_data.get('fat', 0),
                    carbohydrates=item_data.get('carbohydrates', 0),
                )
                food_items_data.append({
                    'id': str(food_item.id),
                    'name': food_item.name,
                    'grams': food_item.grams,
                    'calories': food_item.calories,
                    'protein': float(food_item.protein),
                    'fat': float(food_item.fat),
                    'carbohydrates': float(food_item.carbohydrates),
                    'confidence': item_data.get('confidence', 0.9),
                })
            
            # Increment usage counter
            DailyUsage.objects.increment_photo_requests(user)
            
            # Calculate meal totals
            total_calories = sum(item.calories for item in meal.items.all())
            total_protein = sum(float(item.protein) for item in meal.items.all())
            total_fat = sum(float(item.fat) for item in meal.items.all())
            total_carbs = sum(float(item.carbohydrates) for item in meal.items.all())
            
            logger.info(
                f"[Task {task_id}] Recognition complete for meal {meal_id}. "
                f"Created {len(food_items_data)} food items in {recognition_time:.2f}s"
            )
            
            return {
                'success': True,
                'meal_id': str(meal_id),
                'recognized_items': food_items_data,
                'totals': {
                    'calories': total_calories,
                    'protein': round(total_protein, 1),
                    'fat': round(total_fat, 1),
                    'carbohydrates': round(total_carbs, 1),
                },
                'recognition_time': round(recognition_time, 2),
            }
        else:
            error_msg = result.get('error', 'No food items recognized')
            logger.warning(f"[Task {task_id}] No items recognized for meal {meal_id}: {error_msg}")
            
            # Delete empty meal
            meal.delete()
            
            return {
                'success': False,
                'meal_id': str(meal_id),
                'error': error_msg,
                'recognition_time': round(recognition_time, 2),
            }
            
    except Meal.DoesNotExist:
        logger.error(f"[Task {task_id}] Meal {meal_id} not found")
        return {
            'success': False,
            'meal_id': str(meal_id),
            'error': 'Meal not found',
        }
    except Exception as e:
        logger.error(f"[Task {task_id}] Error processing meal {meal_id}: {str(e)}", exc_info=True)
        # Re-raise to trigger Celery retry
        raise


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
