"""
serializers.py — валидация входа для AI распознавания еды.

Простыми словами:
- клиент присылает фото (файл) или data_url (base64)
- мы проверяем, что это реальное изображение, не слишком большое
- дополнительно принимаем:
  - meal_type (тип приёма пищи) — можно не передавать, тогда будет SNACK
  - date (дата) — можно не передавать, тогда сегодня
- на выходе отдаём нормализованную картинку (bytes + mime), чтобы дальше
  views/tasks не ковыряли сырые данные.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import re
from typing import Any, Dict, Optional

from django.utils import timezone
from rest_framework import serializers

# Meal_type из модели (не импортируем модель, чтобы не тянуть ORM сюда)
MEAL_TYPE_CHOICES = ("BREAKFAST", "LUNCH", "DINNER", "SNACK")

# Безопасные лимиты (анти-DoS). Поднято до 15MB для больших Android JPEG.
MAX_IMAGE_BYTES = 15 * 1024 * 1024

# HEIC/HEIF добавлены — normalize_image() конвертирует их в JPEG
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}

# MIME типы, для которых byte sniffing надёжен
# HEIC не включён — для него доверяем MIME (ftyp сигнатура ненадёжна)
BYTE_SNIFF_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

DATA_URL_RE = re.compile(r"^data:(?P<mime>[-\w.+/]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$")


@dataclass(frozen=True)
class NormalizedImage:
    """
    Нормализованное изображение:
    - bytes_data: байты файла
    - mime_type: image/jpeg | image/png | image/webp
    """

    bytes_data: bytes
    mime_type: str


def _detect_mime_from_bytes(data: bytes) -> Optional[str]:
    """Определяем тип картинки по сигнатуре (не доверяем расширению/контент-тайпу клиента)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and b"WEBP" in data[8:16]:
        return "image/webp"
    return None


def _decode_data_url(data_url: str) -> NormalizedImage:
    """data_url(base64) → bytes + mime с проверками размера и типа."""
    m = DATA_URL_RE.match((data_url or "").strip())
    if not m:
        raise serializers.ValidationError("Неверный формат data_url (ожидается base64 data URL)")

    mime = m.group("mime").lower().strip()
    b64_data = m.group("data").strip()

    if mime not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError(f"Неподдерживаемый тип изображения: {mime}")

    # грубая защита до декодирования
    if len(b64_data) > int(MAX_IMAGE_BYTES * 1.4):
        raise serializers.ValidationError("Изображение слишком большое")

    try:
        raw = base64.b64decode(b64_data, validate=True)
    except (binascii.Error, ValueError):
        raise serializers.ValidationError("Некорректный base64 в data_url")

    if not raw:
        raise serializers.ValidationError("Пустое изображение")

    if len(raw) > MAX_IMAGE_BYTES:
        raise serializers.ValidationError("Изображение слишком большое")

    detected = _detect_mime_from_bytes(raw)

    # Для HEIC/HEIF: доверяем MIME (byte sniffing ненадёжен для ftyp)
    # normalize_image() сам решит: конвертировать или controlled error
    if mime in ("image/heic", "image/heif"):
        return NormalizedImage(bytes_data=raw, mime_type=mime)

    # Для jpeg/png/webp: проверяем содержимое
    if detected is None:
        raise serializers.ValidationError("Файл не похож на изображение (jpeg/png/webp)")

    if detected != mime:
        raise serializers.ValidationError("Тип изображения не совпадает с содержимым файла")

    return NormalizedImage(bytes_data=raw, mime_type=mime)


def _normalize_uploaded_file(file_obj) -> NormalizedImage:
    """
    multipart файл → bytes + mime с лимитами.
    Важно: читаем файл только после проверки size.
    """
    size = getattr(file_obj, "size", None)
    if size is None:
        raise serializers.ValidationError("Не удалось определить размер файла")
    if size <= 0:
        raise serializers.ValidationError("Пустой файл")
    if size > MAX_IMAGE_BYTES:
        raise serializers.ValidationError("Файл изображения слишком большой")

    raw = file_obj.read()
    if not raw:
        raise serializers.ValidationError("Пустой файл")
    if len(raw) > MAX_IMAGE_BYTES:
        raise serializers.ValidationError("Файл изображения слишком большой")

    detected = _detect_mime_from_bytes(raw)

    # Для HEIC/HEIF: пытаемся определить по MIME заголовка (если есть)
    # или просто пропускаем (normalize_image разберётся)
    content_type = getattr(file_obj, "content_type", None)
    if content_type:
        ct_lower = content_type.lower().split(";")[0].strip()
        if ct_lower in ("image/heic", "image/heif"):
            return NormalizedImage(bytes_data=raw, mime_type=ct_lower)

    if detected is None:
        raise serializers.ValidationError("Файл не похож на изображение (jpeg/png/webp)")
    if detected not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError("Неподдерживаемый тип изображения")

    return NormalizedImage(bytes_data=raw, mime_type=detected)


class AIRecognizeRequestSerializer(serializers.Serializer):
    """
    Вход для POST /api/v1/ai/recognize/

    Можно отправить:
    - image (multipart file) — РЕКОМЕНДУЕМЫЙ ПРОД-ПУТЬ
      или
    - data_url (base64) — ТОЛЬКО ДЛЯ ТЕСТОВ/АДМИНКИ

    ℹ️ data_url предназначен ТОЛЬКО для тестов, админских сценариев и ручной отладки
    (Postman/Swagger). Прод-клиенты (Mini App, мобильные) НЕ ДОЛЖНЫ отправлять
    base64. В проде используется ТОЛЬКО multipart/form-data (binary upload).

    Дополнительно:
    - meal_type: BREAKFAST/LUNCH/DINNER/SNACK (если нет → SNACK)
    - date: дата приёма пищи (если нет → сегодня)
    - user_comment: короткая подсказка для AI (опционально)
    """

    image = serializers.ImageField(required=False, allow_null=True)
    # ⚠️ data_url: ТОЛЬКО для тестов/админки. В проде base64 запрещён!
    data_url = serializers.CharField(
        required=False,
        allow_blank=False,
        trim_whitespace=True,
        help_text="Только для тестов/админа. В проде base64 запрещён.",
    )

    meal_type = serializers.ChoiceField(choices=MEAL_TYPE_CHOICES, required=False)
    date = serializers.DateField(required=False)

    user_comment = serializers.CharField(
        required=False, allow_blank=True, max_length=500, trim_whitespace=True
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        image = attrs.get("image")
        data_url = attrs.get("data_url")

        if not image and not data_url:
            raise serializers.ValidationError("Нужно передать либо image, либо data_url")
        if image and data_url:
            raise serializers.ValidationError(
                "Нужно передать только одно: либо image, либо data_url"
            )

        # meal_type/date — чтобы создать Meal без падений
        attrs["meal_type"] = attrs.get("meal_type") or "SNACK"
        attrs["date"] = attrs.get("date") or timezone.localdate()

        # Нормализация изображения (bytes + mime)
        if image:
            attrs["normalized_image"] = _normalize_uploaded_file(image)
            attrs["source_type"] = "file"
        else:
            attrs["normalized_image"] = _decode_data_url(data_url or "")
            attrs["source_type"] = "data_url"

        return attrs
