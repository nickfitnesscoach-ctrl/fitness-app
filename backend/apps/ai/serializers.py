"""
Serializers for AI app.
"""

import base64
import binascii
from rest_framework import serializers


class RecognizedItemSerializer(serializers.Serializer):
    """Serializer for a single recognized food item."""
    name = serializers.CharField(help_text="Название блюда")
    confidence = serializers.FloatField(help_text="Уровень уверенности (0.0-1.0)")
    estimated_weight = serializers.IntegerField(help_text="Предполагаемый вес в граммах")
    calories = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Калории"
    )
    proteins = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Белки (г)",
        source='protein'
    )
    fats = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Жиры (г)",
        source='fat'
    )
    carbs = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Углеводы (г)",
        source='carbohydrates'
    )


class AIRecognitionRequestSerializer(serializers.Serializer):
    """Serializer for AI recognition request."""
    image = serializers.CharField(
        write_only=True,
        help_text="Изображение в формате Base64 (data:image/jpeg;base64,...)"
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=500,
        help_text="Дополнительное описание блюд, до 500 символов (например: '3 сэндвича, овсянка на молоке 2.5%, 1 ч.л. сахара')"
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=500,
        help_text="Комментарий пользователя о блюде (передается в AI Proxy как user_comment)"
    )
    date = serializers.DateField(
        required=False,
        help_text="Дата приёма пищи (опционально, по умолчанию текущая дата)"
    )

    def validate_image(self, value):
        """
        Validate Base64 image format with comprehensive security checks.

        SECURITY CHECKS:
        - Base64 format validation
        - File size limits (10MB max)
        - Image dimension limits (4096x4096 max)
        - Decompression bomb prevention
        - File magic bytes verification (prevents fake extensions)
        - Image format verification via PIL
        - Malicious content detection
        """
        if not value:
            raise serializers.ValidationError("Изображение обязательно")

        # Check if it's a data URL
        if value.startswith('data:image'):
            try:
                # Extract base64 part after comma
                header, encoded = value.split(',', 1)

                # Validate image format in header
                if 'image/jpeg' not in header and 'image/jpg' not in header and 'image/png' not in header:
                    raise serializers.ValidationError(
                        "Поддерживаются только форматы JPEG, JPG и PNG"
                    )

                # SECURITY: Check Base64 string size BEFORE decoding
                # Max 14MB base64 encoded = ~10MB decoded
                max_base64_size = 14 * 1024 * 1024  # 14MB
                if len(encoded) > max_base64_size:
                    raise serializers.ValidationError(
                        f"Размер изображения превышает {max_base64_size // (1024 * 1024)}MB"
                    )

                # Try to decode base64
                try:
                    decoded = base64.b64decode(encoded, validate=True)
                except (binascii.Error, ValueError):
                    raise serializers.ValidationError("Некорректный формат Base64")

                # SECURITY: Validate decoded size
                decoded_size_mb = len(decoded) / (1024 * 1024)
                max_decoded_size_mb = 10
                if decoded_size_mb > max_decoded_size_mb:
                    raise serializers.ValidationError(
                        f"Размер декодированного изображения превышает {max_decoded_size_mb}MB "
                        f"(текущий: {decoded_size_mb:.2f}MB)"
                    )

                # SECURITY: Verify file magic bytes (file signature)
                # This prevents disguised files (e.g., .exe renamed to .jpg)
                self._validate_file_magic_bytes(decoded)

                # SECURITY: Validate actual image content and dimensions
                try:
                    from PIL import Image
                    import io

                    # Open image with PIL (will fail if not a valid image)
                    image = Image.open(io.BytesIO(decoded))

                    # SECURITY: Verify image to prevent PIL vulnerabilities
                    # This loads the entire image and checks for corruption
                    try:
                        image.verify()
                        # Re-open after verify (verify closes the image)
                        image = Image.open(io.BytesIO(decoded))
                    except Exception:
                        raise serializers.ValidationError(
                            "Изображение повреждено или содержит недопустимый контент"
                        )

                    # Check image dimensions (prevent decompression bombs)
                    width, height = image.size
                    max_dimension = 4096  # 4K max per side
                    if width > max_dimension or height > max_dimension:
                        raise serializers.ValidationError(
                            f"Размер изображения не должен превышать {max_dimension}x{max_dimension} px. "
                            f"Текущий размер: {width}x{height} px"
                        )

                    # SECURITY: Check minimum dimensions (too small = suspicious)
                    min_dimension = 10
                    if width < min_dimension or height < min_dimension:
                        raise serializers.ValidationError(
                            f"Изображение слишком маленькое: {width}x{height} px. "
                            f"Минимум: {min_dimension}x{min_dimension} px"
                        )

                    # Check total pixel count (prevent decompression bombs)
                    max_pixels = 4096 * 4096  # 16 megapixels max
                    total_pixels = width * height
                    if total_pixels > max_pixels:
                        raise serializers.ValidationError(
                            f"Изображение содержит слишком много пикселей. "
                            f"Максимум: {max_pixels:,}, текущее: {total_pixels:,}"
                        )

                    # SECURITY: Verify format matches header AND magic bytes
                    if image.format not in ['JPEG', 'PNG']:
                        raise serializers.ValidationError(
                            f"Неверный формат изображения: {image.format}. "
                            "Поддерживаются только JPEG и PNG"
                        )

                    # SECURITY: Check for suspicious image modes
                    # Normal modes: RGB, RGBA, L (grayscale), P (palette)
                    allowed_modes = ['RGB', 'RGBA', 'L', 'P', '1']
                    if image.mode not in allowed_modes:
                        raise serializers.ValidationError(
                            f"Недопустимый режим изображения: {image.mode}"
                        )

                except Exception as e:
                    if isinstance(e, serializers.ValidationError):
                        raise
                    raise serializers.ValidationError(f"Некорректное изображение: {str(e)}")

                return value

            except ValueError:
                raise serializers.ValidationError(
                    "Неверный формат изображения. Ожидается: data:image/jpeg;base64,..."
                )
        else:
            # Try to decode as plain base64
            try:
                # SECURITY: Check size before decoding
                max_base64_size = 14 * 1024 * 1024  # 14MB
                if len(value) > max_base64_size:
                    raise serializers.ValidationError(
                        f"Размер изображения превышает {max_base64_size // (1024 * 1024)}MB"
                    )

                decoded = base64.b64decode(value, validate=True)

                # SECURITY: Validate decoded size
                decoded_size_mb = len(decoded) / (1024 * 1024)
                if decoded_size_mb > 10:
                    raise serializers.ValidationError(
                        f"Размер декодированного изображения превышает 10MB "
                        f"(текущий: {decoded_size_mb:.2f}MB)"
                    )

                # SECURITY: Verify file magic bytes
                self._validate_file_magic_bytes(decoded)

                # Add data URL prefix for consistency
                return f"data:image/jpeg;base64,{value}"
            except (binascii.Error, ValueError) as e:
                if isinstance(e, serializers.ValidationError):
                    raise
                raise serializers.ValidationError(
                    "Некорректный формат Base64. Используйте формат: data:image/jpeg;base64,..."
                )

    def _validate_file_magic_bytes(self, file_data):
        """
        Validate file magic bytes (file signature) to ensure it's actually an image.

        SECURITY: Prevents file extension spoofing (e.g., malware.exe renamed to image.jpg)

        Args:
            file_data: Decoded binary file data

        Raises:
            ValidationError: If file magic bytes don't match JPEG or PNG
        """
        if len(file_data) < 12:
            raise serializers.ValidationError("Файл слишком маленький для изображения")

        # JPEG magic bytes: FF D8 FF
        jpeg_magic = b'\xff\xd8\xff'

        # PNG magic bytes: 89 50 4E 47 0D 0A 1A 0A
        png_magic = b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'

        # Check magic bytes
        if not (file_data.startswith(jpeg_magic) or file_data.startswith(png_magic)):
            raise serializers.ValidationError(
                "Файл не является изображением JPEG или PNG. "
                "Проверка magic bytes не пройдена."
            )


class AIRecognitionResponseSerializer(serializers.Serializer):
    """Serializer for AI recognition response."""

    def to_representation(self, instance):
        """
        Format response to match frontend expectations.

        Frontend expects:
        {
          "recognized_items": [...],
          "total_calories": number,
          "total_protein": number,
          "total_fat": number,
          "total_carbohydrates": number
        }

        Also maps backend field names to frontend:
        - estimated_weight -> grams
        """
        items = instance.get("recognized_items", [])

        # Map field names for frontend compatibility
        mapped_items = []
        for item in items:
            mapped_item = {
                "name": item.get("name", ""),
                "grams": item.get("estimated_weight", 0),  # Map estimated_weight -> grams
                "calories": item.get("calories", 0),
                "protein": item.get("protein", 0),
                "fat": item.get("fat", 0),
                "carbohydrates": item.get("carbohydrates", 0),
            }
            mapped_items.append(mapped_item)

        # Calculate totals
        total_calories = sum(item.get("calories", 0) for item in items)
        total_protein = sum(item.get("protein", 0) for item in items)
        total_fat = sum(item.get("fat", 0) for item in items)
        total_carbs = sum(item.get("carbohydrates", 0) for item in items)

        return {
            "recognized_items": mapped_items,
            "total_calories": round(total_calories, 1),
            "total_protein": round(total_protein, 1),
            "total_fat": round(total_fat, 1),
            "total_carbohydrates": round(total_carbs, 1)
        }
