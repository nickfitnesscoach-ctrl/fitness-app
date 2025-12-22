"""
utils.py — вспомогательные функции для ai_proxy.

Простыми словами:
- тут только простые утилиты, которые не зависят от Django/ORM
- цель: меньше дублирования кода и меньше “случайных” багов

Правила:
- никаких секретов в логах
- никаких больших данных (байты изображений) в логах
"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple
import uuid


def new_request_id() -> str:
    """
    Генерирует короткий request_id для трассировки запросов через логи.

    Пример:
    - Django → Celery → AI Proxy → обратно

    Это помогает быстро найти все сообщения в логах по одному идентификатору.
    """
    return uuid.uuid4().hex


def join_url(base_url: str, path: str) -> str:
    """
    Склеивает base_url и path без двойных слешей.

    join_url("https://x/api", "/v1/recognize") -> "https://x/api/v1/recognize"
    """
    base = (base_url or "").rstrip("/")
    p = path if (path or "").startswith("/") else f"/{path}"
    return f"{base}{p}"


def safe_json_loads(raw_text: str, *, max_preview: int = 300) -> Tuple[Dict[str, Any], str]:
    """
    Безопасно парсит JSON строку.

    Возвращает:
    - dict (если удалось и это объект)
    - preview текста (если не удалось/не dict), чтобы логировать кратко

    Почему это важно:
    - иногда сервис отвечает не JSON (html, plain text)
    - мы не хотим, чтобы это падало исключением и ломало пайплайн
    """
    text = (raw_text or "").strip()
    if not text:
        return {}, ""

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}, text[:max_preview]

    if isinstance(parsed, dict):
        return parsed, ""
    # Если пришёл список/число/строка — считаем это ошибкой формата
    return {}, text[:max_preview]


def clip_dict(d: Dict[str, Any], *, max_keys: int = 20) -> Dict[str, Any]:
    """
    Урезает словарь для безопасного логирования.

    Пример: если AI Proxy вернул огромный payload, мы не хотим забивать логи.
    """
    if not isinstance(d, dict):
        return {}
    keys = list(d.keys())[:max_keys]
    return {k: d.get(k) for k in keys}
