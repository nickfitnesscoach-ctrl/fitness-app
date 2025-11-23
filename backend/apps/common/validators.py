"""
Custom validators for FoodMind AI.
"""

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible


@deconstructible
class FileSizeValidator:
    """
    Validator to check if uploaded file size is within acceptable limits.

    Usage:
        photo = models.ImageField(
            upload_to='photos/',
            validators=[FileSizeValidator(max_mb=5)]
        )
    """

    def __init__(self, max_mb=5):
        """
        Initialize validator with max file size in megabytes.

        Args:
            max_mb (int): Maximum file size in megabytes. Default is 5MB.
        """
        self.max_mb = max_mb
        self.max_bytes = max_mb * 1024 * 1024

    def __call__(self, value):
        """
        Validate that file size doesn't exceed maximum.

        Args:
            value: UploadedFile instance

        Raises:
            ValidationError: If file size exceeds maximum
        """
        if value.size > self.max_bytes:
            raise ValidationError(
                f'Размер файла не должен превышать {self.max_mb} MB. '
                f'Текущий размер: {value.size / (1024 * 1024):.2f} MB'
            )

    def __eq__(self, other):
        """Required for migrations."""
        return (
            isinstance(other, FileSizeValidator) and
            self.max_mb == other.max_mb
        )


@deconstructible
class ImageDimensionValidator:
    """
    Validator to check if uploaded image dimensions are within acceptable limits.

    Usage:
        photo = models.ImageField(
            upload_to='photos/',
            validators=[ImageDimensionValidator(max_width=4096, max_height=4096)]
        )
    """

    def __init__(self, max_width=4096, max_height=4096):
        """
        Initialize validator with max dimensions.

        Args:
            max_width (int): Maximum width in pixels
            max_height (int): Maximum height in pixels
        """
        self.max_width = max_width
        self.max_height = max_height

    def __call__(self, value):
        """
        Validate that image dimensions don't exceed maximum.

        Args:
            value: UploadedFile instance (image)

        Raises:
            ValidationError: If dimensions exceed maximum
        """
        try:
            from PIL import Image
            image = Image.open(value)
            width, height = image.size

            if width > self.max_width or height > self.max_height:
                raise ValidationError(
                    f'Размер изображения не должен превышать {self.max_width}x{self.max_height} px. '
                    f'Текущий размер: {width}x{height} px'
                )
        except Exception as e:
            # If we can't open the image, let Django's ImageField handle it
            pass

    def __eq__(self, other):
        """Required for migrations."""
        return (
            isinstance(other, ImageDimensionValidator) and
            self.max_width == other.max_width and
            self.max_height == other.max_height
        )
