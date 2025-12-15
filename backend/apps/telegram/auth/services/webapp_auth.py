"""
Unified service for Telegram WebApp initData validation.

This service is used across all backend components (DRF auth, views, middleware)
to ensure consistent validation logic.
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Dict, Optional
from urllib.parse import parse_qsl

from django.conf import settings

logger = logging.getLogger(__name__)


class TelegramWebAppAuthService:
    """Service for Telegram WebApp authentication."""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    def validate_init_data(
        self,
        raw_init_data: str,
        *,
        max_age_seconds: int = 86400
    ) -> Optional[Dict[str, str]]:
        """
        Validate initData from Telegram WebApp.

        Args:
            raw_init_data: Query-string from Telegram.WebApp.initData
            max_age_seconds: Maximum age of data (default 24h)

        Returns:
            Dict with parsed data (without hash) or None on error

        Docs: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
        """
        if not raw_init_data or not self.bot_token:
            logger.warning("[WebAppAuth] Missing initData or bot_token")
            return None

        try:
            # 1. Parse query string
            parsed_data = dict(parse_qsl(raw_init_data, keep_blank_values=True))
            received_hash = parsed_data.pop("hash", None)

            if not received_hash:
                logger.warning("[WebAppAuth] No hash in initData")
                return None

            # 2. Check auth_date (TTL)
            if max_age_seconds:
                auth_date = int(parsed_data.get("auth_date", "0"))
                age = time.time() - auth_date

                if age > max_age_seconds:
                    logger.warning(
                        "[WebAppAuth] initData expired (age: %.2f sec, max: %d)",
                        age, max_age_seconds
                    )
                    return None

            # 3. Build data-check-string
            data_check_string = "\n".join(
                f"{key}={value}"
                for key, value in sorted(parsed_data.items())
            )

            # 4. Calculate secret_key (CORRECT FORMULA!)
            secret_key = hmac.new(
                key=b'WebAppData',
                msg=self.bot_token.encode(),
                digestmod=hashlib.sha256
            ).digest()

            # 5. Calculate hash
            calculated_hash = hmac.new(
                key=secret_key,
                msg=data_check_string.encode(),
                digestmod=hashlib.sha256
            ).hexdigest()

            # 6. Compare (constant-time)
            if not hmac.compare_digest(calculated_hash, received_hash):
                logger.warning("[WebAppAuth] Hash mismatch")
                return None

            logger.info("[WebAppAuth] Validation successful")
            return parsed_data

        except Exception as e:
            logger.exception("[WebAppAuth] Validation error: %s", e)
            return None

    def get_user_id_from_init_data(self, parsed_data: Dict[str, str]) -> Optional[int]:
        """Extract Telegram user ID from parsed initData."""
        user_json = parsed_data.get("user")
        if not user_json:
            return None

        try:
            user_data = json.loads(user_json)
            return int(user_data.get("id"))
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error("[WebAppAuth] Failed to parse user: %s", e)
            return None

    def get_user_data_from_init_data(self, parsed_data: Dict[str, str]) -> Optional[dict]:
        """Extract full user data from parsed initData."""
        user_json = parsed_data.get("user")
        if not user_json:
            return None

        try:
            return json.loads(user_json)
        except json.JSONDecodeError as e:
            logger.error("[WebAppAuth] Failed to parse user JSON: %s", e)
            return None


# Singleton instance
_auth_service: Optional[TelegramWebAppAuthService] = None


def get_webapp_auth_service() -> TelegramWebAppAuthService:
    """Get singleton instance of the service."""
    global _auth_service

    if _auth_service is None:
        _auth_service = TelegramWebAppAuthService(settings.TELEGRAM_BOT_TOKEN)

    return _auth_service
