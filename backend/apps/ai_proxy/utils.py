"""
utils.py — вспомогательные функции для ai_proxy.

Простыми словами:
- тут только простые утилиты, которые не зависят от Django/ORM
- цель: меньше дублирования кода и меньше “случайных” багов

Правила:
- никаких секретов в логах
- никаких больших данных (байты изображений) в логах
"""

from io import BytesIO
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple
import uuid

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:
    HEIF_SUPPORTED = False

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Нормализация изображения для Vision API (HARD SLA)
# ---------------------------------------------------------------------------
# Инварианты:
# - Все изображения в Vision: JPEG, longest_side <=1024px, quality=85
# - Нормализация выполняется ровно 1 раз, до base64 и до ретраев
# - action="ok" → можно отправлять в Vision
# - action="reject" → ЗАПРЕЩЕНО отправлять, service возвращает controlled error
# ---------------------------------------------------------------------------

# Performance guard: максимальное время обработки (ms)
NORMALIZATION_TIMEOUT_MS = 800


def normalize_image(
    image_bytes: bytes,
    content_type: Optional[str] = None,
    max_side: int = 1024,
    quality: int = 85,
    max_fallback_size: int = 512 * 1024,
) -> Tuple[bytes, str, Dict[str, Any]]:
    """
    Нормализует изображение перед отправкой в Vision API.

    HARD SLA:
    - Все изображения в Vision MUST быть JPEG, <=1024px longest side
    - action="ok" → можно отправлять
    - action="reject" → ЗАПРЕЩЕНО отправлять

    Fallback (action="ok", reason="already_ok") разрешён ТОЛЬКО если:
    - content_type == image/jpeg
    - longest side <= 1024px
    - size <= 512KB

    Во всех остальных случаях при ошибке → action="reject".
    """
    start_time = time.perf_counter()

    # Нормализуем content_type: lowercase, обрезаем после `;`
    ct_raw = (content_type or "unknown").lower().split(";")[0].strip()

    # Базовые метрики
    metrics: Dict[str, Any] = {
        "action": "reject",  # По умолчанию reject — безопаснее
        "reason": "unknown",
        "normalized": False,
        "content_type_in": ct_raw,
        "content_type_out": "image/jpeg",
        "original_size_bytes": len(image_bytes or b""),
        "normalized_size_bytes": 0,
        "original_px": "0x0",
        "normalized_px": "0x0",
        "original_longest_side": 0,
        "normalized_longest_side": 0,  # 0 при reject
        "processing_ms": 0,
    }

    def _finish_reject(reason: str) -> Tuple[bytes, str, Dict[str, Any]]:
        """Финализирует reject и возвращает ПУСТЫЕ байты."""
        metrics["action"] = "reject"
        metrics["reason"] = reason
        metrics["normalized_longest_side"] = 0  # При reject всегда 0
        metrics["processing_ms"] = int((time.perf_counter() - start_time) * 1000)
        return b"", "image/jpeg", metrics  # Пустые байты!

    # Пустые байты → reject
    if not image_bytes:
        return _finish_reject("decode_failed")

    is_jpeg = ct_raw in ("image/jpeg", "image/jpg")
    is_heic = ct_raw in ("image/heic", "image/heif")

    # HEIC без поддержки → reject сразу
    if is_heic and not HEIF_SUPPORTED:
        return _finish_reject("unsupported_format")

    # Попытка открыть изображение для проверки/нормализации
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            w, h = img.size
            longest = max(w, h)
            metrics["original_px"] = f"{w}x{h}"
            metrics["original_longest_side"] = longest

            # Проверяем fallback условия (ТОЛЬКО для JPEG)
            if (
                is_jpeg
                and longest <= max_side
                and metrics["original_size_bytes"] <= max_fallback_size
            ):
                # Оригинал уже соответствует SLA
                metrics["action"] = "ok"
                metrics["reason"] = "already_ok"
                metrics["normalized_size_bytes"] = metrics["original_size_bytes"]
                metrics["normalized_px"] = metrics["original_px"]
                metrics["normalized_longest_side"] = longest
                metrics["processing_ms"] = int((time.perf_counter() - start_time) * 1000)
                return image_bytes, "image/jpeg", metrics

            # Нормализация требуется
            # 1. EXIF Rotate
            img = ImageOps.exif_transpose(img)

            # 2. RGB (drop alpha)
            if img.mode in ("RGBA", "P", "LA", "L"):
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # 3. Resize если нужно
            curr_w, curr_h = img.size
            if max(curr_w, curr_h) > max_side:
                if curr_w > curr_h:
                    new_w = max_side
                    new_h = int(curr_h * (max_side / curr_w))
                else:
                    new_h = max_side
                    new_w = int(curr_w * (max_side / curr_h))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # 4. Save as JPEG
            out_buf = BytesIO()
            img.save(out_buf, format="JPEG", quality=quality, optimize=True)
            normalized_data = out_buf.getvalue()

            # Обновляем метрики
            final_w, final_h = img.size
            metrics["normalized"] = True
            metrics["normalized_size_bytes"] = len(normalized_data)
            metrics["normalized_px"] = f"{final_w}x{final_h}"
            metrics["normalized_longest_side"] = max(final_w, final_h)

            # Финализируем метрики и возвращаем нормализованные данные
            metrics["action"] = "ok"
            metrics["reason"] = "ok"
            metrics["processing_ms"] = int((time.perf_counter() - start_time) * 1000)

            # Performance guard
            if metrics["processing_ms"] > NORMALIZATION_TIMEOUT_MS:
                metrics["action"] = "reject"
                metrics["reason"] = "too_slow"
                metrics["normalized_longest_side"] = 0
                return b"", "image/jpeg", metrics  # Пустые байты!

            return normalized_data, "image/jpeg", metrics

    except Exception as e:
        logger.warning("Image normalization failed: %s", type(e).__name__)
        # Ошибка декодирования → reject (fallback запрещён при неизвестных размерах)
        return _finish_reject("decode_failed")
