"""
Telegram WebApp authentication backend.

Проверяет подпись initData из Telegram Mini App для безопасной аутентификации.
"""

import hmac
import hashlib
import logging
import json
from urllib.parse import parse_qsl
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions

from .models import TelegramUser
from apps.users.models import Profile

User = get_user_model()

logger = logging.getLogger(__name__)


class TelegramWebAppAuthentication(authentication.BaseAuthentication):
    """
    Аутентификация через Telegram Mini App initData.

    Проверяет подпись данных от Telegram WebApp API.
    Docs: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """

    def authenticate(self, request):
        """
        Аутентифицирует пользователя по Telegram initData.

        Ищет initData в заголовке X-Telegram-Init-Data или в теле запроса.
        """
        # Получаем initData из заголовка или тела запроса
        init_data = request.META.get('HTTP_X_TELEGRAM_INIT_DATA')

        if not init_data and request.method in ['POST', 'PUT', 'PATCH']:
            init_data = request.data.get('initData')

        if not init_data:
            return None

        # Валидация подписи
        if not self.validate_init_data(init_data):
            raise exceptions.AuthenticationFailed('Invalid Telegram initData signature')

        # Парсинг данных пользователя
        user_data = self.parse_init_data(init_data)

        if not user_data:
            raise exceptions.AuthenticationFailed('Invalid Telegram user data')

        # Получение или создание пользователя
        user = self.get_or_create_user(user_data)

        return (user, None)

    def validate_init_data(self, init_data: str) -> bool:
        """
        Проверяет подпись initData от Telegram.

        Args:
            init_data: Строка initData из Telegram.WebApp.initData

        Returns:
            True если подпись валидна, False иначе
        """
        try:
            parsed_data = dict(parse_qsl(init_data))

            # Получаем hash из данных
            received_hash = parsed_data.pop('hash', None)
            if not received_hash:
                return False

            # Проверяем время (данные не старше 24 часов)
            auth_date = parsed_data.get('auth_date')
            if auth_date:
                auth_timestamp = int(auth_date)
                now_timestamp = int(datetime.now().timestamp())

                # Данные действительны 24 часа
                if now_timestamp - auth_timestamp > 86400:
                    return False

            # Формируем data-check-string
            data_check_arr = [f"{k}={v}" for k, v in sorted(parsed_data.items())]
            data_check_string = '\n'.join(data_check_arr)

            # Вычисляем secret_key
            bot_token = settings.TELEGRAM_BOT_TOKEN
            secret_key = hmac.new(
                b'WebAppData',
                bot_token.encode(),
                hashlib.sha256
            ).digest()

            # Вычисляем hash
            calculated_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()

            # Сравниваем хеши (constant-time comparison для безопасности)
            return hmac.compare_digest(calculated_hash, received_hash)

        except Exception as e:
            print(f"Telegram auth validation error: {e}")
            return False

    def parse_init_data(self, init_data: str) -> dict:
        """
        Парсит initData и извлекает данные пользователя.

        Args:
            init_data: Строка initData из Telegram

        Returns:
            Словарь с данными пользователя или None
        """
        try:
            parsed = dict(parse_qsl(init_data))
            user_json = parsed.get('user', '{}')
            user_data = json.loads(user_json)
            return user_data
        except Exception as e:
            print(f"Error parsing initData: {e}")
            return None

    def get_or_create_user(self, telegram_user_data: dict):
        """
        Получает существующего или создает нового пользователя.

        Args:
            telegram_user_data: Данные из Telegram WebApp
            {
                "id": 123456789,
                "first_name": "John",
                "last_name": "Doe",
                "username": "johndoe",
                "language_code": "ru",
                "is_premium": true
            }

        Returns:
            Django User instance
        """
        telegram_id = telegram_user_data.get('id')

        if not telegram_id:
            raise exceptions.AuthenticationFailed('Telegram ID is required')

        try:
            # Ищем существующего пользователя Telegram
            telegram_user = TelegramUser.objects.select_related('user').get(
                telegram_id=telegram_id
            )
            user = telegram_user.user

            # Обновляем данные
            telegram_user.username = telegram_user_data.get('username', '')
            telegram_user.first_name = telegram_user_data.get('first_name', '')
            telegram_user.last_name = telegram_user_data.get('last_name', '')
            telegram_user.language_code = telegram_user_data.get('language_code', 'ru')
            telegram_user.is_premium = telegram_user_data.get('is_premium', False)
            telegram_user.save()

        except TelegramUser.DoesNotExist:
            # Создаем нового пользователя
            username = f"tg_{telegram_id}"
            first_name = telegram_user_data.get('first_name', 'User')
            last_name = telegram_user_data.get('last_name', '')

            # Проверяем, существует ли User с таким username
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                # Создаем нового User без email (не нужен для Telegram)
                user = User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )

            telegram_user = TelegramUser.objects.create(
                user=user,
                telegram_id=telegram_id,
                username=telegram_user_data.get('username', ''),
                first_name=first_name,
                last_name=last_name,
                language_code=telegram_user_data.get('language_code', 'ru'),
                is_premium=telegram_user_data.get('is_premium', False)
            )

        return user


class TelegramHeaderAuthentication(authentication.BaseAuthentication):
    """
    Authentication backend for Telegram Mini App via Nginx proxy headers.

    Authenticates users by X-Telegram-ID header passed from Nginx.
    Creates new user automatically if not exists (auto-registration).

    Headers used:
        X-Telegram-ID: Telegram user ID (required)
        X-Telegram-First-Name: User's first name (optional)
        X-Telegram-Username: Telegram username (optional)
        X-Telegram-Last-Name: User's last name (optional)
        X-Telegram-Language-Code: User's language (optional)

    Security note:
        This authentication trusts headers from Nginx.
        Nginx should only set these headers from validated Telegram initData.
    """

    def authenticate(self, request):
        """
        Authenticate request using Telegram headers from Nginx.

        Returns:
            tuple: (user, None) if authentication successful
            None: if no Telegram headers present (allows other auth methods)

        Raises:
            AuthenticationFailed: if telegram_id is invalid
        """
        telegram_id = request.META.get('HTTP_X_TELEGRAM_ID')

        if not telegram_id:
            return None

        # Validate telegram_id is a valid integer
        try:
            telegram_id = int(telegram_id)
        except (ValueError, TypeError):
            raise exceptions.AuthenticationFailed('Invalid Telegram ID format')

        if telegram_id <= 0:
            raise exceptions.AuthenticationFailed('Invalid Telegram ID value')

        # Build user data from headers
        user_data = {
            'id': telegram_id,
            'first_name': request.META.get('HTTP_X_TELEGRAM_FIRST_NAME', 'User'),
            'username': request.META.get('HTTP_X_TELEGRAM_USERNAME', ''),
            'last_name': request.META.get('HTTP_X_TELEGRAM_LAST_NAME', ''),
            'language_code': request.META.get('HTTP_X_TELEGRAM_LANGUAGE_CODE', 'ru'),
        }

        # Get or create user using TelegramUser model
        user = self._get_or_create_user(user_data)

        return (user, None)

    def authenticate_header(self, request):
        """Return WWW-Authenticate header value for 401 responses."""
        return 'TelegramHeader realm="api"'

    def _get_or_create_user(self, telegram_user_data: dict):
        """Get existing user or create new one by Telegram ID."""
        telegram_id = telegram_user_data['id']

        try:
            telegram_user = TelegramUser.objects.select_related('user').get(
                telegram_id=telegram_id
            )
            user = telegram_user.user

            # Update Telegram data on each login
            telegram_user.username = telegram_user_data.get('username', '')
            telegram_user.first_name = telegram_user_data.get('first_name', '')
            telegram_user.last_name = telegram_user_data.get('last_name', '')
            telegram_user.language_code = telegram_user_data.get('language_code', 'ru')
            telegram_user.save()

            return user

        except TelegramUser.DoesNotExist:
            return self._create_telegram_user(telegram_user_data)

    def _create_telegram_user(self, telegram_user_data: dict):
        """Create new Django User from Telegram header data."""
        telegram_id = telegram_user_data['id']
        first_name = telegram_user_data.get('first_name', 'User')
        last_name = telegram_user_data.get('last_name', '')
        django_username = f"tg_{telegram_id}"

        # Check if user exists
        try:
            user = User.objects.get(username=django_username)
        except User.DoesNotExist:
            user = User.objects.create_user(
                username=django_username,
                first_name=first_name,
                last_name=last_name
            )
            user.set_unusable_password()
            user.save()

        # Create TelegramUser record
        TelegramUser.objects.create(
            user=user,
            telegram_id=telegram_id,
            username=telegram_user_data.get('username', ''),
            first_name=first_name,
            last_name=last_name,
            language_code=telegram_user_data.get('language_code', 'ru'),
            is_premium=telegram_user_data.get('is_premium', False)
        )

        # Гарантируем, что у каждого Telegram-пользователя есть профиль
        try:
            Profile.objects.get_or_create(user=user)
        except Exception as exc:
            logger.exception(
                "Failed to ensure Profile for telegram user %s: %s", user.pk, exc
            )

        return user
