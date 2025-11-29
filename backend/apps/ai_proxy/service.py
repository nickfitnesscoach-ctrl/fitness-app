"""
AI Recognition Service using AI Proxy.

This service replaces the old OpenRouter-based recognition.
It uploads images to a temporary CDN and sends the URL to AI Proxy.
"""

import logging
import base64
import tempfile
import os
from typing import Dict, Optional
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

from .client import AIProxyClient
from .adapter import adapt_ai_proxy_response
from .exceptions import AIProxyError

logger = logging.getLogger(__name__)


class AIProxyRecognitionService:
    """
    Service for recognizing food items using AI Proxy.

    This service:
    1. Converts base64 image to file
    2. Uploads to CDN or generates public URL
    3. Calls AI Proxy with image URL
    4. Adapts response to legacy format
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
            ValueError: If image format is invalid
        """
        # Merge description and comment (prioritize comment)
        final_comment = user_comment or user_description or ""

        # Extract base64 data
        image_url = self._convert_base64_to_url(image_data_url)

        try:
            # Call AI Proxy
            logger.info(f"Calling AI Proxy with image URL: {image_url[:80]}...")
            ai_proxy_response = self.client.recognize_food(
                image_url=image_url,
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

    def _convert_base64_to_url(self, image_data_url: str) -> str:
        """
        Convert base64 data URL to publicly accessible URL.

        For now, we just pass the data URL directly to AI Proxy.
        AI Proxy can handle data URLs.

        Args:
            image_data_url: Image in data URL format

        Returns:
            Public URL or data URL
        """
        # AI Proxy accepts data URLs directly, so we can just return it
        # In future, we could upload to CDN here if needed
        return image_data_url
