"""
Adapter for converting AI Proxy responses to legacy format.

The AI Proxy returns a different structure than the old OpenRouter integration.
This adapter transforms the response to match the expected format.

AI Proxy response format (new):
{
    "items": [
        {
            "name": "Куриная грудка гриль",
            "grams": 150.0,
            "kcal": 165,
            "protein": 31.0,
            "fat": 3.6,
            "carbs": 0.0
        }
    ],
    "total": {
        "kcal": 165,
        "protein": 31.0,
        "fat": 3.6,
        "carbs": 0.0
    },
    "model_notes": "High protein meal"  # optional
}

Legacy format (old):
{
    "recognized_items": [
        {
            "name": "Куриная грудка гриль",
            "confidence": 0.95,
            "estimated_weight": 150,
            "calories": 165,
            "protein": 31.0,
            "fat": 3.6,
            "carbohydrates": 0.0
        }
    ]
}
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def adapt_ai_proxy_response(ai_proxy_response: Dict) -> Dict:
    """
    Convert AI Proxy response to legacy format.

    Args:
        ai_proxy_response: Response from AI Proxy service

    Returns:
        Dict in legacy format with "recognized_items" key
    
    Note on field mapping:
        AI Proxy Pydantic schema uses aliases for serialization:
        - kcal -> calories (alias)
        - carbohydrates -> carbs (alias)
        So we need to read "calories" and "carbs" from the response.
    """
    items = ai_proxy_response.get("items", [])

    recognized_items = []
    for item in items:
        # AI Proxy returns simple field names
        name = item.get("name", "Unknown")

        # BUG FIX: AI Proxy Pydantic uses alias "calories" for kcal field
        # Accept both "calories" and "kcal" for compatibility
        calories = item.get("calories") or item.get("kcal") or 0
        
        # BUG FIX: AI Proxy Pydantic uses alias "carbs" for carbohydrates field
        # Accept both "carbs" and "carbohydrates" for compatibility
        carbohydrates = item.get("carbs") or item.get("carbohydrates") or 0

        recognized_item = {
            "name": name,
            "confidence": 0.95,  # AI Proxy doesn't return confidence, use default
            "estimated_weight": int(item.get("grams", 0)),
            "calories": calories,
            "protein": item.get("protein", 0.0),
            "fat": item.get("fat", 0.0),
            "carbohydrates": carbohydrates,
        }
        recognized_items.append(recognized_item)

    result = {
        "recognized_items": recognized_items
    }

    # Log detailed info for debugging
    total_calories = sum(item.get('calories', 0) for item in recognized_items)
    logger.info(
        f"Adapted AI Proxy response: {len(recognized_items)} items, "
        f"total calories: {total_calories}"
    )
    
    # Debug log raw items for troubleshooting
    for i, item in enumerate(items):
        logger.debug(
            f"Raw item[{i}]: kcal={item.get('kcal')}, calories={item.get('calories')}, "
            f"carbs={item.get('carbs')}, carbohydrates={item.get('carbohydrates')}"
        )

    return result
