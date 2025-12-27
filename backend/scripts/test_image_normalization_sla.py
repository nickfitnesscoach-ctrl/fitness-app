"""
Тестовый скрипт для проверки нормализации изображений (HARD SLA).

Проверяет:
- Large JPEG (10MB+): должен нормализоваться, action=ok
- PNG RGBA: должен конвертироваться в JPEG, action=ok
- HEIC: action=ok если декодер доступен, иначе action=reject
- Битые байты: action=reject
- Small JPEG: action=ok, reason=already_ok
"""

import os
import sys
from io import BytesIO

# Add backend to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Minimal Django config
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
import django

django.setup()

from PIL import Image
from apps.ai_proxy.utils import normalize_image, HEIF_SUPPORTED


def create_test_image(format: str = "JPEG", size: tuple = (2000, 1000), mode: str = "RGB") -> bytes:
    """Создаёт тестовое изображение."""
    buf = BytesIO()
    img = Image.new(mode, size, color=(255, 0, 0))
    if format == "JPEG" and mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")
    img.save(buf, format=format, quality=95)
    return buf.getvalue()


def test_large_jpeg():
    """Large JPEG (>1024px) → должен нормализоваться."""
    large_jpeg = create_test_image(format="JPEG", size=(4000, 3000))
    print(f"Large JPEG: {len(large_jpeg)} bytes")

    norm_bytes, content_type, metrics = normalize_image(large_jpeg, "image/jpeg")

    assert metrics["action"] == "ok", f"Expected action=ok, got {metrics['action']}"
    assert metrics["reason"] == "ok", f"Expected reason=ok, got {metrics['reason']}"
    assert content_type == "image/jpeg"
    assert metrics["normalized_longest_side"] <= 1024
    print(
        f"✓ Large JPEG: {metrics['original_longest_side']}px → {metrics['normalized_longest_side']}px, action={metrics['action']}"
    )


def test_small_jpeg():
    """Small JPEG (<=1024px, <=512KB) → should pass through as already_ok."""
    small_jpeg = create_test_image(format="JPEG", size=(500, 300))
    print(f"Small JPEG: {len(small_jpeg)} bytes")

    norm_bytes, content_type, metrics = normalize_image(small_jpeg, "image/jpeg")

    assert metrics["action"] == "ok", f"Expected action=ok, got {metrics['action']}"
    assert metrics["reason"] == "already_ok", f"Expected reason=already_ok, got {metrics['reason']}"
    assert content_type == "image/jpeg"
    print(
        f"✓ Small JPEG: {metrics['original_longest_side']}px, action={metrics['action']}, reason={metrics['reason']}"
    )


def test_png_rgba():
    """PNG with alpha → должен конвертироваться в JPEG RGB."""
    png_rgba = create_test_image(format="PNG", size=(800, 600), mode="RGBA")
    print(f"PNG RGBA: {len(png_rgba)} bytes")

    norm_bytes, content_type, metrics = normalize_image(png_rgba, "image/png")

    assert metrics["action"] == "ok", f"Expected action=ok, got {metrics['action']}"
    assert content_type == "image/jpeg"
    assert metrics["normalized"]

    # Verify it's valid JPEG
    with Image.open(BytesIO(norm_bytes)) as img:
        assert img.format == "JPEG"
        assert img.mode == "RGB"

    print(f"✓ PNG RGBA: Converted to JPEG RGB, action={metrics['action']}")


def test_heic():
    """HEIC → action=ok if decoder available, else action=reject."""
    dummy_heic = b"fake heic content that cannot be decoded"

    norm_bytes, content_type, metrics = normalize_image(dummy_heic, "image/heic")

    if HEIF_SUPPORTED:
        # With real HEIC decoder, this would fail because bytes are fake
        assert metrics["action"] == "reject", (
            f"Expected reject for fake HEIC, got {metrics['action']}"
        )
        assert metrics["reason"] == "decode_failed"
        print(f"✓ HEIC (fake bytes, HEIF supported): action=reject, reason=decode_failed")
    else:
        assert metrics["action"] == "reject"
        assert metrics["reason"] == "unsupported_format"
        print(f"✓ HEIC (no decoder): action=reject, reason=unsupported_format")


def test_corrupted_bytes():
    """Corrupted bytes → action=reject."""
    corrupted = b"definitely not an image"

    norm_bytes, content_type, metrics = normalize_image(corrupted, "image/jpeg")

    assert metrics["action"] == "reject", f"Expected action=reject, got {metrics['action']}"
    assert metrics["reason"] == "decode_failed"
    print(f"✓ Corrupted bytes: action=reject, reason=decode_failed")


def test_empty_bytes():
    """Empty bytes → action=reject."""
    norm_bytes, content_type, metrics = normalize_image(b"", "image/jpeg")

    assert metrics["action"] == "reject"
    assert metrics["reason"] == "decode_failed"
    print(f"✓ Empty bytes: action=reject")


def main():
    print("=" * 60)
    print("Image Normalization Tests (HARD SLA)")
    print("=" * 60)
    print(f"HEIF_SUPPORTED = {HEIF_SUPPORTED}")
    print()

    test_large_jpeg()
    test_small_jpeg()
    test_png_rgba()
    test_heic()
    test_corrupted_bytes()
    test_empty_bytes()

    print()
    print("=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
