"""
AI Proxy Client for EatFit24.

This module provides a synchronous HTTP client for interacting with the EatFit24 AI Proxy service.
The AI Proxy is an internal service that wraps OpenRouter API calls for food recognition.

Security:
- API key authentication (X-API-Key header)
- Internal service (Tailscale VPN only)
- 30 second timeout for AI processing

Usage:
    from apps.ai_proxy.client import AIProxyClient
    from apps.ai_proxy.utils import parse_data_url

    client = AIProxyClient()

    # Parse data URL to bytes
    image_bytes, content_type = parse_data_url(data_url)

    # Send file via multipart/form-data
    result = client.recognize_food(
        image_bytes=image_bytes,
        content_type=content_type,
        user_comment="Grilled chicken with rice",
        locale="ru"
    )
"""

import logging
from typing import Dict, Optional

import httpx
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .exceptions import (
    AIProxyAuthenticationError,
    AIProxyServerError,
    AIProxyTimeoutError,
    AIProxyValidationError,
)

logger = logging.getLogger(__name__)


class AIProxyClient:
    """
    Synchronous HTTP client for EatFit24 AI Proxy service.

    This client handles:
    - API key authentication
    - Request timeout (30s)
    - Error handling (401, 422, 500, timeout)
    - Response validation
    - Logging

    Raises:
        AIProxyAuthenticationError: Invalid or missing API key (401)
        AIProxyValidationError: Invalid request body (422)
        AIProxyServerError: AI service error (500)
        AIProxyTimeoutError: Request timeout (>30s)
    """

    def __init__(self):
        """
        Initialize AI Proxy client with settings validation.

        Raises:
            ImproperlyConfigured: If required settings are missing
        """
        # Validate settings
        self.api_url = getattr(settings, "AI_PROXY_URL", None)
        self.api_key = getattr(settings, "AI_PROXY_SECRET", None)

        if not self.api_url:
            raise ImproperlyConfigured(
                "AI_PROXY_URL is not set in settings. "
                "Add it to your .env file (e.g., AI_PROXY_URL=http://100.84.210.65:8001)"
            )

        if not self.api_key:
            raise ImproperlyConfigured(
                "AI_PROXY_SECRET is not set in settings. "
                "Add it to your .env file (e.g., AI_PROXY_SECRET=your-secret-key)"
            )

        # Remove trailing slash from URL
        self.api_url = self.api_url.rstrip("/")

        # Initialize HTTP client with timeout
        # AI Proxy uses 60s timeout for OpenRouter calls
        self.timeout = 60.0  # 60 seconds
        self.client = httpx.Client(timeout=self.timeout)

        logger.info(
            f"AI Proxy client initialized. URL: {self.api_url}, "
            f"Key prefix: {self.api_key[:8]}..., Timeout: {self.timeout}s"
        )

    def recognize_food(
        self,
        image_bytes: bytes,
        content_type: str,
        user_comment: Optional[str] = None,
        locale: str = "ru",
    ) -> Dict:
        """
        Recognize food items from image bytes via multipart/form-data.

        Args:
            image_bytes: Raw image bytes (JPEG or PNG)
            content_type: MIME type of the image (e.g., 'image/jpeg', 'image/png')
            user_comment: Optional user comment about the food
            locale: Language code (default: "ru")

        Returns:
            Dict with structure (as returned by AI Proxy):
            {
                "items": [
                    {
                        "name": "Куриная грудка гриль",
                        "grams": 150.0,
                        "kcal": 165,
                        "protein": 31.0,
                        "fat": 3.6,
                        "carbs": 0.0
                    }
                ],
                "total": {
                    "kcal": 165,
                    "protein": 31.0,
                    "fat": 3.6,
                    "carbs": 0.0
                },
                "model_notes": "High protein meal, low fat"  # optional
            }

        Raises:
            AIProxyAuthenticationError: Invalid API key (401)
            AIProxyValidationError: Invalid request (422)
            AIProxyServerError: AI service error (500)
            AIProxyTimeoutError: Request timeout
        """
        endpoint = f"{self.api_url}/api/v1/ai/recognize-food"

        # Prepare headers (no Content-Type, httpx will set it for multipart)
        headers = {
            "X-API-Key": self.api_key,
        }

        # Prepare multipart files
        files = {
            "image": ("image", image_bytes, content_type or "application/octet-stream")
        }

        # Prepare form data
        data = {
            "locale": locale or "ru",
        }

        if user_comment:
            data["user_comment"] = user_comment

        # Log request (log size and type, not the actual bytes)
        image_size_kb = len(image_bytes) / 1024
        logger.info(
            f"AI Proxy request: image_size={image_size_kb:.1f}KB, "
            f"content_type={content_type}, comment={user_comment!r}, locale={locale}"
        )

        try:
            # Make HTTP POST request with multipart/form-data
            response = self.client.post(
                endpoint,
                headers=headers,
                files=files,
                data=data,
            )

            # Handle different status codes
            if response.status_code == 200:
                result = response.json()

                items_count = len(result.get("items", []))
                total_calories = result.get("total", {}).get("kcal", 0)

                logger.info(
                    f"AI Proxy success: {items_count} items found, "
                    f"total {total_calories} kcal"
                )

                return result

            elif response.status_code == 401:
                error_detail = response.json().get("detail", "Invalid or missing API key")
                logger.error(
                    f"AI Proxy authentication failed: {error_detail}. "
                    f"Key prefix: {self.api_key[:8]}..."
                )
                raise AIProxyAuthenticationError(
                    f"AI Proxy authentication failed: {error_detail}"
                )

            elif response.status_code == 422:
                error_detail = response.json().get("detail", "Validation error")
                logger.error(f"AI Proxy validation error: {error_detail}")
                raise AIProxyValidationError(
                    f"AI Proxy validation error: {error_detail}"
                )

            elif response.status_code == 500:
                error_detail = response.json().get("detail", "Internal server error")
                logger.error(f"AI Proxy server error: {error_detail}")
                raise AIProxyServerError(
                    f"AI Proxy server error: {error_detail}"
                )

            else:
                # Unexpected status code
                logger.error(
                    f"AI Proxy unexpected status {response.status_code}: {response.text[:200]}"
                )
                raise AIProxyServerError(
                    f"AI Proxy returned unexpected status {response.status_code}"
                )

        except httpx.TimeoutException as e:
            logger.error(f"AI Proxy timeout after {self.timeout}s: {e}")
            raise AIProxyTimeoutError(
                f"AI Proxy request timed out after {self.timeout} seconds"
            )

        except httpx.HTTPError as e:
            # Network errors, connection errors, etc.
            logger.error(f"AI Proxy HTTP error: {type(e).__name__}: {e}")
            raise AIProxyServerError(
                f"AI Proxy connection error: {type(e).__name__}: {e}"
            )

    def __del__(self):
        """Close HTTP client on cleanup."""
        try:
            self.client.close()
        except Exception:
            pass
