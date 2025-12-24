"""
adapter.py — нормализация ответа AI Proxy (FastAPI) в формат, удобный для Django.

Простыми словами:
- AI Proxy может возвращать поля в своём “API-формате”:
  food_name_ru, portion_weight_g, protein_g, carbs_g и т.д.
- А Django хранит FoodItem в другом формате:
  name, grams, protein, fat, carbohydrates

Этот файл делает “переводчик” между форматами.

Гарантии:
- grams всегда >= 1 (иначе упадёт валидатор FoodItem)
- все числа будут >= 0
- алиасы полей поддерживаются (на случай небольших изменений в прокси)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        v = float(value)
        if v < 0:
            return default
        return v
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 1) -> int:
    try:
        if value is None:
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


# P2-2: Используем общую функцию из common module
from apps.common.nutrition_utils import clamp_grams as _clamp_grams


def _pick_name(item: Dict[str, Any]) -> str:
    """
    AI Proxy отдаёт food_name_ru/food_name_en. Мы берём RU приоритетно.
    """
    name = item.get("food_name_ru") or item.get("name") or item.get("title")
    if not name:
        name = item.get("food_name_en") or "Unknown"
    return str(name).strip() or "Unknown"


def _normalize_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    name = _pick_name(raw)

    # Вес
    grams = raw.get("portion_weight_g")
    if grams is None:
        grams = raw.get("weight_g")
    if grams is None:
        grams = raw.get("grams")
    grams_i = _clamp_grams(_to_int(grams, 1))

    # Калории
    calories = raw.get("calories")
    if calories is None:
        calories = raw.get("kcal")
    calories_f = _to_float(calories, 0.0)

    # Макросы: в прокси поля *_g
    protein = raw.get("protein_g")
    if protein is None:
        protein = raw.get("protein")
    protein_f = _to_float(protein, 0.0)

    fat = raw.get("fat_g")
    if fat is None:
        fat = raw.get("fat")
    fat_f = _to_float(fat, 0.0)

    carbs = raw.get("carbs_g")
    if carbs is None:
        carbs = raw.get("carbohydrates")
    if carbs is None:
        carbs = raw.get("carbs")
    carbs_f = _to_float(carbs, 0.0)

    # confidence в твоём FastAPI ответе сейчас не видно — но оставим поддержку на будущее
    conf = raw.get("confidence")
    conf_f: Optional[float] = None
    if conf is not None:
        c = _to_float(conf, 0.0)
        # если вдруг проценты 0..100
        if c > 1.0:
            c = c / 100.0
        if c < 0:
            c = 0.0
        if c > 1:
            c = 1.0
        conf_f = float(c)

    return {
        "name": name,
        "grams": int(grams_i),
        "calories": float(calories_f),
        "protein": float(protein_f),
        "fat": float(fat_f),
        "carbohydrates": float(carbs_f),
        "confidence": conf_f,
    }


def _normalize_total(raw_total: Any) -> Dict[str, float]:
    """
    total из AI Proxy:
    {
      "calories": int,
      "protein_g": float,
      "fat_g": float,
      "carbs_g": float
    }
    """
    if not isinstance(raw_total, dict):
        return {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbohydrates": 0.0}

    calories = _to_float(raw_total.get("calories"), 0.0)
    protein = _to_float(raw_total.get("protein_g") or raw_total.get("protein"), 0.0)
    fat = _to_float(raw_total.get("fat_g") or raw_total.get("fat"), 0.0)
    carbs = _to_float(
        raw_total.get("carbs_g") or raw_total.get("carbohydrates") or raw_total.get("carbs"),
        0.0,
    )

    return {
        "calories": float(calories),
        "protein": float(protein),
        "fat": float(fat),
        "carbohydrates": float(carbs),
    }


def compute_totals_from_items(items: List[Dict[str, Any]]) -> Dict[str, float]:
    total_calories = 0.0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0

    for it in items:
        total_calories += _to_float(it.get("calories"), 0.0)
        total_protein += _to_float(it.get("protein"), 0.0)
        total_fat += _to_float(it.get("fat"), 0.0)
        total_carbs += _to_float(it.get("carbohydrates"), 0.0)

    return {
        "calories": float(total_calories),
        "protein": float(total_protein),
        "fat": float(total_fat),
        "carbohydrates": float(total_carbs),
    }


def normalize_proxy_response(raw: Any, *, request_id: str = "") -> Dict[str, Any]:
    """
    Приводит сырой ответ AI Proxy к стабильному формату:

    {
      "items": [ {name, grams, calories, protein, fat, carbohydrates, confidence} ],
      "totals": {calories, protein, fat, carbohydrates},
      "meta": {...}
    }
    """
    if not isinstance(raw, dict):
        return {
            "items": [],
            "totals": {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbohydrates": 0.0},
            "meta": {"request_id": request_id, "warning": "non-object-json"},
        }

    raw_items = raw.get("items") or []
    if not isinstance(raw_items, list):
        raw_items = []

    items: List[Dict[str, Any]] = []
    for it in raw_items:
        if isinstance(it, dict):
            items.append(_normalize_item(it))

    # totals: берём из raw["total"], иначе считаем сами
    totals = _normalize_total(raw.get("total"))
    if totals == {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbohydrates": 0.0} and items:
        totals = compute_totals_from_items(items)

    meta: Dict[str, Any] = {
        "request_id": request_id,
        "model_notes": raw.get("model_notes"),
    }
    meta = {k: v for k, v in meta.items() if v is not None}

    return {"items": items, "totals": totals, "meta": meta}
