"""
AI Recognition Service using AI Proxy.

This service replaces the old OpenRouter-based recognition.
It decodes data URL images and sends them as multipart/form-data to AI Proxy.
"""

import logging
from typing import Dict, Optional

from .client import AIProxyClient
from .adapter import adapt_ai_proxy_response
from .exceptions import AIProxyError, AIProxyValidationError
from .utils import parse_data_url

logger = logging.getLogger(__name__)


class AIProxyRecognitionService:
    """
    Service for recognizing food items using AI Proxy.

    This service:
    1. Decodes data URL to image bytes
    2. Sends image bytes via multipart/form-data to AI Proxy
    3. Adapts response to legacy format
    """

    def __init__(self):
        """Initialize AI Proxy client."""
        self.client = AIProxyClient()

    def recognize_food(
        self,
        image_data_url: str,
        user_description: str = "",
        user_comment: str = "",
    ) -> Dict:
        """
        Recognize food items from base64 image.

        Args:
            image_data_url: Image in data URL format (data:image/jpeg;base64,...)
            user_description: Optional description (legacy field)
            user_comment: Optional user comment (new field for AI Proxy)

        Returns:
            Dict in legacy format with "recognized_items" key

        Raises:
            AIProxyError: If AI Proxy call fails
            AIProxyValidationError: If data URL format is invalid
        """
        # Merge description and comment (prioritize comment)
        final_comment = user_comment or user_description or ""

        try:
            # Parse data URL to bytes
            logger.debug("Parsing data URL to image bytes")
            image_bytes, content_type = parse_data_url(image_data_url)

            logger.info(
                f"Parsed data URL: size={len(image_bytes)/1024:.1f}KB, "
                f"content_type={content_type}"
            )

        except ValueError as e:
            # Wrap ValueError in AIProxyValidationError for consistent error handling
            logger.error(f"Invalid data URL format: {e}")
            raise AIProxyValidationError(f"Invalid image data URL: {e}")

        try:
            # Call AI Proxy with image bytes via multipart/form-data
            logger.info("Calling AI Proxy with image bytes")
            ai_proxy_response = self.client.recognize_food(
                image_bytes=image_bytes,
                content_type=content_type,
                user_comment=final_comment,
                locale="ru",
            )

            # Adapt response to legacy format
            result = adapt_ai_proxy_response(ai_proxy_response)

            logger.info(
                f"AI Proxy recognition successful. "
                f"Items: {len(result.get('recognized_items', []))}"
            )

            return result

        except AIProxyError as e:
            logger.error(f"AI Proxy error: {e}")
            raise
