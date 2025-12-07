"""
Celery tasks for async AI processing.

These tasks handle AI recognition in the background,
allowing the API to return immediately with a task ID.
"""

import logging
import time
from celery import shared_task
from django.db import transaction

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
        dict with full recognition results for frontend polling.
        IMPORTANT: Items are returned from DB after refresh_from_db()
        to prevent race condition where items are not yet visible.
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
            # Create FoodItems in transaction to ensure atomicity
            with transaction.atomic():
                for item_data in recognized_items:
                    FoodItem.objects.create(
                        meal=meal,
                        name=item_data.get('name', 'Unknown'),
                        grams=item_data.get('estimated_weight', 100),
                        calories=item_data.get('calories', 0),
                        protein=item_data.get('protein', 0),
                        fat=item_data.get('fat', 0),
                        carbohydrates=item_data.get('carbohydrates', 0),
                    )
                
                # Increment usage counter inside transaction
                DailyUsage.objects.increment_photo_requests(user)
            
            # RACE CONDITION FIX: Refresh from DB to get actual saved items
            # This guarantees task result contains items that are really in the database
            meal.refresh_from_db()
            db_items = list(meal.items.all())
            
            # Build result from DB items (not from AI response)
            food_items_data = [
                {
                    'id': item.id,
                    'name': item.name,
                    'grams': item.grams,
                    'calories': item.calories,
                    'protein': float(item.protein),
                    'fat': float(item.fat),
                    'carbohydrates': float(item.carbohydrates),
                    'confidence': 0.9,  # Default confidence
                }
                for item in db_items
            ]
            
            # Calculate totals from DB items
            total_calories = sum(item.calories for item in db_items)
            total_protein = sum(float(item.protein) for item in db_items)
            total_fat = sum(float(item.fat) for item in db_items)
            total_carbs = sum(float(item.carbohydrates) for item in db_items)
            
            logger.info(
                f"[Task {task_id}] Recognition complete for meal {meal_id}. "
                f"Created {len(db_items)} food items in {recognition_time:.2f}s"
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
            # B-001 FIX: НЕ удаляем meal - он уже создан с фото и может быть виден пользователю
            # Пользователь увидит пустой приём пищи и сможет добавить items вручную
            # Cleanup stale meals task уберёт старые пустые meals позже
            error_msg = result.get('error', 'No food items recognized')
            logger.warning(f"[Task {task_id}] No items recognized for meal {meal_id}: {error_msg}. Meal kept for manual entry.")
            
            # Increment usage counter even for empty results (user made an attempt)
            DailyUsage.objects.increment_photo_requests(user)
            
            return {
                'success': True,  # Changed to True - meal exists, just empty
                'meal_id': str(meal_id),
                'recognized_items': [],
                'totals': {
                    'calories': 0,
                    'protein': 0,
                    'fat': 0,
                    'carbohydrates': 0,
                },
                'recognition_time': round(recognition_time, 2),
                'message': 'Не удалось распознать еду автоматически. Вы можете добавить блюда вручную.',
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
