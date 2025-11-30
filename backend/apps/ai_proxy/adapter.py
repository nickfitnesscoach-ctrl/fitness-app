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
    """
    items = ai_proxy_response.get("items", [])

    recognized_items = []
    for item in items:
        # AI Proxy returns simple field names
        name = item.get("name", "Unknown")

        recognized_item = {
            "name": name,
            "confidence": 0.95,  # AI Proxy doesn't return confidence, use default
            "estimated_weight": int(item.get("grams", 0)),
            "calories": item.get("kcal", 0),
            "protein": item.get("protein", 0.0),
            "fat": item.get("fat", 0.0),
            "carbohydrates": item.get("carbs", 0.0),
        }
        recognized_items.append(recognized_item)

    result = {
        "recognized_items": recognized_items
    }

    logger.debug(
        f"Adapted AI Proxy response: {len(recognized_items)} items, "
        f"total calories: {sum(item.get('calories', 0) for item in recognized_items)}"
    )

    return result
