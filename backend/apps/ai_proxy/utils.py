"""
Utility functions for AI Proxy integration.
"""

import base64
import re
from typing import Tuple


DATA_URL_PATTERN = re.compile(r'^data:(?P<content_type>[^;]+);base64,(?P<data>.+)$')


def parse_data_url(data_url: str) -> Tuple[bytes, str]:
    """
    Parse data URL and extract image bytes and content type.

    Args:
        data_url: Image in data URL format (e.g., 'data:image/jpeg;base64,...')

    Returns:
        Tuple of (image_bytes, content_type)

    Raises:
        ValueError: If data URL format is invalid or data cannot be decoded

    Example:
        >>> data_url = "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
        >>> image_bytes, content_type = parse_data_url(data_url)
        >>> print(content_type)
        'image/jpeg'
        >>> print(len(image_bytes))
        12345
    """
    # Validate format
    match = DATA_URL_PATTERN.match(data_url)
    if not match:
        raise ValueError(
            "Invalid data URL format. Expected: data:image/jpeg;base64,..."
        )

    content_type = match.group("content_type")
    b64_data = match.group("data")

    # Validate content type
    allowed_types = ["image/jpeg", "image/jpg", "image/png"]
    if content_type not in allowed_types:
        raise ValueError(
            f"Unsupported content type: {content_type}. "
            f"Allowed types: {', '.join(allowed_types)}"
        )

    # Decode base64
    try:
        image_bytes = base64.b64decode(b64_data, validate=True)
    except Exception as e:
        raise ValueError(f"Failed to decode base64 data: {e}")

    # Validate decoded data
    if not image_bytes:
        raise ValueError("Empty image data after decoding")

    # Validate minimum size (at least 50 bytes for a valid image)
    if len(image_bytes) < 50:
        raise ValueError(
            f"Image data too small: {len(image_bytes)} bytes. "
            "Minimum: 50 bytes"
        )

    return image_bytes, content_type
