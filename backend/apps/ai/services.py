"""
AI Recognition Service using OpenRouter.
"""

import json
import logging
import time
from datetime import date
from typing import Dict, Optional, Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from openai import OpenAI, AuthenticationError

from apps.nutrition.models import Meal, FoodItem
from apps.billing.usage import DailyUsage
from apps.ai_proxy.service import AIProxyRecognitionService

logger = logging.getLogger(__name__)


class AIRecognitionService:
    """Service for recognizing food items from images using OpenRouter AI."""

    def __init__(self):
        """Initialize OpenRouter client with comprehensive API key validation."""
        api_key = settings.OPENROUTER_API_KEY

        # Validate API key exists
        if not api_key or api_key == "":
            raise ImproperlyConfigured(
                "OPENROUTER_API_KEY is not set in settings. "
                "Get your API key from: https://openrouter.ai/keys"
            )

        # Validate API key format
        # OpenRouter keys follow pattern: sk-or-v1-xxxxx (at least 32 chars total)
        if not api_key.startswith("sk-or-v1-"):
            raise ImproperlyConfigured(
                "Invalid OPENROUTER_API_KEY format. "
                "Key must start with 'sk-or-v1-'. "
                "Check your API key at https://openrouter.ai/keys"
            )

        if len(api_key) < 32:
            raise ImproperlyConfigured(
                "OPENROUTER_API_KEY appears to be invalid (too short). "
                "Valid keys are at least 32 characters long."
            )

        # Check for placeholder/example keys
        placeholder_patterns = [
            "sk-or-v1-your",
            "sk-or-v1-example",
            "sk-or-v1-test",
            "sk-or-v1-xxx",
        ]
        if any(api_key.startswith(pattern) for pattern in placeholder_patterns):
            raise ImproperlyConfigured(
                "OPENROUTER_API_KEY appears to be a placeholder value. "
                "Replace it with your actual API key from https://openrouter.ai/keys"
            )

        # Initialize OpenAI client
        try:
            self.client = OpenAI(
                base_url=settings.OPENROUTER_BASE_URL,
                api_key=api_key,
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter client: {e}")
            raise ImproperlyConfigured(
                f"Failed to initialize OpenRouter client: {e}"
            )

        self.model = settings.OPENROUTER_MODEL
        self.max_retries = settings.AI_MAX_RETRIES

        logger.info(
            f"OpenRouter client initialized successfully. Model: {self.model}, "
            f"Key prefix: {api_key[:15]}..."
        )

    def recognize_food(self, image_data_url: str, user_description: str = "") -> Dict:
        """
        Recognize food items from image using AI.

        Args:
            image_data_url: Image in data URL format (data:image/jpeg;base64,...)
            user_description: Optional user-provided description

        Returns:
            Dict with recognized_items list

        Raises:
            ValueError: If JSON is invalid after max retries
            Exception: If API call fails
        """
        # Truncate image data for logging
        image_preview = image_data_url[:50] + "..." if len(image_data_url) > 50 else image_data_url
        logger.debug(f"Starting food recognition. Image: {image_preview}, Description: '{user_description}'")

        prompt = self._get_recognition_prompt(user_description)

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"AI Recognition attempt {attempt}/{self.max_retries}")

                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                        "X-Title": settings.OPENROUTER_SITE_NAME,
                    },
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": image_data_url
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4000,  # Increased for longer responses with description
                )

                response_text = completion.choices[0].message.content
                logger.debug(f"AI Response length: {len(response_text)} chars")

                # Log response preview (first 200 chars) at INFO level
                response_preview = response_text[:200] + "..." if len(response_text) > 200 else response_text
                logger.info(f"AI Response preview: {response_preview}")

                # Full response only at DEBUG level
                logger.debug(f"Full AI Response (attempt {attempt}): {response_text}")

                # Try to parse JSON
                try:
                    # Clean response text (remove markdown code blocks if present)
                    cleaned_text = self._clean_json_response(response_text)
                    result = json.loads(cleaned_text)

                    # Validate structure
                    if not self._validate_response_structure(result):
                        logger.warning(f"Invalid response structure (attempt {attempt})")
                        if attempt == self.max_retries:
                            raise ValueError("Invalid response structure after max retries")
                        continue

                    logger.info(f"Successfully parsed JSON on attempt {attempt}. Items found: {len(result.get('recognized_items', []))}")
                    return result

                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error (attempt {attempt}/{self.max_retries}): {str(e)[:100]}")
                    if attempt == self.max_retries:
                        logger.error(f"Failed to parse JSON after {self.max_retries} attempts. Last error: {e}")
                        raise ValueError(f"Invalid JSON after {self.max_retries} attempts: {e}")
                    continue

            except AuthenticationError as e:
                # Don't retry on authentication errors - API key is invalid
                logger.error(
                    f"OpenRouter authentication failed. "
                    f"API key prefix: {settings.OPENROUTER_API_KEY[:15]}..., "
                    f"Error: {str(e)}"
                )
                raise ImproperlyConfigured(
                    "OpenRouter API authentication failed. "
                    "Please check your OPENROUTER_API_KEY. "
                    f"Error: {e}"
                )

            except Exception as e:
                error_type = type(e).__name__
                logger.error(
                    f"AI Recognition error (attempt {attempt}/{self.max_retries}): "
                    f"{error_type}: {str(e)[:200]}"
                )
                if attempt == self.max_retries:
                    logger.error(f"AI Recognition failed after {self.max_retries} attempts. Final error: {e}")
                    raise
                continue

        raise ValueError("Failed to get valid response after max retries")

    def _get_recognition_prompt(self, user_description: str = "") -> str:
        """Get the prompt for food recognition."""
        base_prompt = """Проанализируй это изображение еды и верни результат СТРОГО в формате JSON без дополнительного текста.

ВАЖНЫЕ ТРЕБОВАНИЯ:
1. Возвращай только валидный JSON, без ```json``` блоков или других символов
2. Определяй только ГОТОВЫЕ БЛЮДА (сэндвич, салат, суп, каша и т.д.), а НЕ отдельные ингредиенты
3. Если видишь сэндвич - указывай "Сэндвич с [основной начинкой]", а не хлеб + мясо + овощи отдельно
4. Если видишь салат - указывай "Салат [тип]" или "Цезарь салат", а не каждый овощ отдельно
5. Если видишь готовое горячее блюдо - указывай название блюда, а не каждый компонент
6. Вес в граммах (1-2000г) для всего блюда целиком
7. Калории на порцию (0-2000 ккал) для всего блюда
8. БЖУ в граммах (0-500г каждый) для всего блюда
9. Confidence от 0.0 до 1.0
10. Названия на русском языке
11. Используй реалистичные пищевые значения для размера порции

Focus on accuracy and realistic portion sizes.

ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ:
- Сэндвич с ветчиной (а не: хлеб + ветчина + салат отдельно)
- Цезарь салат (а не: листья салата + курица + сыр отдельно)
- Борщ с мясом (а не: свекла + капуста + мясо отдельно)"""

        if user_description:
            base_prompt += f"""

ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ ОТ ПОЛЬЗОВАТЕЛЯ:
{user_description}

ВАЖНО:
- Если пользователь упоминает ингредиенты/добавки которых НЕТ на фото (например: "сахар", "масло", "соль", "чай", "напитки"), ОБЯЗАТЕЛЬНО добавь их как отдельные блюда в recognized_items
- Если пользователь указывает количество (например: "3 сэндвича"), учти это в весе и калориях
- Если пользователь указывает способ приготовления (например: "на молоке 2.5%"), учти это в КБЖУ
- Возвращай ВСЁ: что видишь на фото + что указал пользователь в описании

Примеры:
- Пользователь: "3 сэндвича, овсянка на молоке 2.5%, 1 ч.л. сахара, чай"
  → Верни: Сэндвич (указав вес/калории для 3 шт), Овсянка на молоке 2.5%, Сахар (1 ч.л.), Чай
- Пользователь: "каша с маслом и мёдом"
  → Верни: Каша, Масло, Мёд (если их не видно на фото, но они упомянуты)"""

        base_prompt += """

Формат ответа:
{
  "recognized_items": [
    {
      "name": "Название готового блюда",
      "confidence": 0.95,
      "estimated_weight": 150,
      "calories": 165,
      "protein": 31.0,
      "fat": 3.6,
      "carbohydrates": 0.0
    }
  ]
}

Если на изображении нет еды, верни: {"recognized_items": []}"""

        return base_prompt

    def _clean_json_response(self, text: str) -> str:
        """Clean JSON response from markdown or extra text."""
        text = text.strip()

        # Check for empty or "..." response
        if not text or text == "...":
            logger.error("AI returned empty or '...' response")
            raise ValueError("AI returned empty response")

        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]  # Remove ```json
        elif text.startswith("```"):
            text = text[3:]  # Remove ```

        if text.endswith("```"):
            text = text[:-3]

        # Find JSON object boundaries
        start = text.find("{")
        end = text.rfind("}") + 1

        if start == -1 or end <= start:
            logger.error(f"No valid JSON boundaries found in response: {text[:100]}...")
            raise ValueError("No valid JSON object found in response")

        text = text[start:end]

        logger.debug(f"Cleaned JSON (first 200 chars): {text[:200]}...")
        return text.strip()

    def _validate_response_structure(self, data: Dict) -> bool:
        """Validate that response has correct structure."""
        if not isinstance(data, dict):
            return False

        if "recognized_items" not in data:
            return False

        items = data["recognized_items"]
        if not isinstance(items, list):
            return False

        # Validate each item
        required_fields = ["name", "confidence", "estimated_weight", "calories", "protein", "fat", "carbohydrates"]

        for item in items:
            if not isinstance(item, dict):
                return False

            for field in required_fields:
                if field not in item:
                    return False

            # Type validation
            if not isinstance(item["name"], str):
                return False
            if not isinstance(item["estimated_weight"], int):
                return False
            if not (0.0 <= item["confidence"] <= 1.0):
                return False

        return True


def recognize_and_save_meal(
    user,
    image_file,
    image_data_url: str,
    meal_type: str,
    meal_date: date,
    description: str = "",
    comment: str = ""
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
        Dict with meal_id, recognized_items, recognition_time
        
    Raises:
        AIProxyTimeoutError: If AI service times out
        Exception: If AI service fails
    """
    # 1. Create Meal and save photo
    if image_file:
        image_file.seek(0)
    
    meal = Meal.objects.create(
        user=user,
        meal_type=meal_type,
        date=meal_date,
        photo=image_file
    )
    logger.info(f"Created Meal id={meal.id} with photo for user {user.username}")

    # 2. Initialize AI Proxy service and recognize
    ai_service = AIProxyRecognitionService()
    
    recognition_start = time.time()
    logger.info(f"Starting AI Proxy recognition for user {user.username}")
    
    result = ai_service.recognize_food(
        image_data_url,
        user_description=description,
        user_comment=comment
    )
    recognition_elapsed = time.time() - recognition_start

    logger.info(
        f"AI recognition successful for user {user.username}. "
        f"Found {len(result.get('recognized_items', []))} items, "
        f"recognition_time={recognition_elapsed:.2f}s"
    )

    # 3. Save recognized items to Meal
    recognized_items = result.get('recognized_items', [])
    for item in recognized_items:
        FoodItem.objects.create(
            meal=meal,
            name=item.get('name', 'Unknown'),
            grams=item.get('estimated_weight', 100),
            calories=item.get('calories', 0),
            protein=item.get('protein', 0),
            fat=item.get('fat', 0),
            carbohydrates=item.get('carbohydrates', 0)
        )

    # 4. Increment photo usage counter
    DailyUsage.objects.increment_photo_requests(user)
    logger.info(f"Incremented photo counter for user {user.username}")

    return {
        'meal': meal,
        'recognized_items': recognized_items,
        'recognition_time': recognition_elapsed,
    }
