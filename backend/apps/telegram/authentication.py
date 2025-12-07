"""
Telegram WebApp authentication backend.

Проверяет подпись initData из Telegram Mini App для безопасной аутентификации.
Также поддерживает Browser Debug Mode для локальной разработки.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions

from .models import TelegramUser
from .services.webapp_auth import get_webapp_auth_service
from apps.users.models import Profile

User = get_user_model()

logger = logging.getLogger(__name__)


class DebugModeAuthentication(authentication.BaseAuthentication):
    """
    Authentication backend for Browser Debug Mode.
    
    Allows frontend development without Telegram WebApp.
    Creates/finds a debug user based on X-Debug-User-Id header.
    
    Headers used:
        X-Debug-Mode: "true" (required to activate)
        X-Debug-User-Id: Debug user's telegram_id (default: 999999999)
        X-Telegram-ID: Same as X-Debug-User-Id
        X-Telegram-First-Name: Debug user's first name
        X-Telegram-Username: Debug user's username
    
    Security note:
        This authentication is intended for development only.
        In production, ensure DEBUG_MODE_ENABLED=False or restrict access.
    """
    
    # Default debug user ID
    DEFAULT_DEBUG_USER_ID = 999999999
    
    def authenticate(self, request):
        """
        Authenticate request if X-Debug-Mode header is "true".
        
        Returns:
            tuple: (user, None) if debug mode authentication successful
            None: if X-Debug-Mode is not "true" (allows other auth methods)
        """
        debug_mode = request.META.get('HTTP_X_DEBUG_MODE', '').lower()
        
        if debug_mode != 'true':
            # Not a debug request, allow other auth methods
            return None
        
        # Check if debug mode is allowed
        if not getattr(settings, 'DEBUG_MODE_ENABLED', settings.DEBUG):
            logger.warning("[DebugModeAuth] Debug mode request rejected - not enabled in settings")
            return None
        
        # Get debug user ID from headers
        debug_user_id = request.META.get('HTTP_X_DEBUG_USER_ID')
        if not debug_user_id:
            debug_user_id = request.META.get('HTTP_X_TELEGRAM_ID')
        
        if not debug_user_id:
            debug_user_id = self.DEFAULT_DEBUG_USER_ID
        
        try:
            debug_user_id = int(debug_user_id)
        except (ValueError, TypeError):
            logger.warning("[DebugModeAuth] Invalid debug user ID: %s", debug_user_id)
            debug_user_id = self.DEFAULT_DEBUG_USER_ID
        
        # Build user data from headers
        user_data = {
            'id': debug_user_id,
            'first_name': request.META.get('HTTP_X_TELEGRAM_FIRST_NAME', 'Debug'),
            'username': request.META.get('HTTP_X_TELEGRAM_USERNAME', 'eatfit24_debug'),
            'last_name': request.META.get('HTTP_X_TELEGRAM_LAST_NAME', 'User'),
            'language_code': request.META.get('HTTP_X_TELEGRAM_LANGUAGE_CODE', 'ru'),
            'is_premium': False,
        }
        
        # Get or create debug user
        user = self._get_or_create_debug_user(user_data)
        
        logger.info(
            "[DebugModeAuth] Debug user authenticated: user_id=%s telegram_id=%s username=%s",
            user.id, debug_user_id, user_data['username']
        )
        
        return (user, 'debug')
    
    def authenticate_header(self, request):
        """Return WWW-Authenticate header value for 401 responses."""
        return 'DebugMode realm="api"'
    
    def _get_or_create_debug_user(self, telegram_user_data: dict):
        """Get existing debug user or create new one."""
        telegram_id = telegram_user_data['id']
        
        try:
            telegram_user = TelegramUser.objects.select_related('user').get(
                telegram_id=telegram_id
            )
            user = telegram_user.user
            
            # Update Telegram data
            telegram_user.username = telegram_user_data.get('username', '')
            telegram_user.first_name = telegram_user_data.get('first_name', '')
            telegram_user.last_name = telegram_user_data.get('last_name', '')
            telegram_user.language_code = telegram_user_data.get('language_code', 'ru')
            telegram_user.save()
            
            return user
            
        except TelegramUser.DoesNotExist:
            return self._create_debug_user(telegram_user_data)
    
    def _create_debug_user(self, telegram_user_data: dict):
        """Create new debug user."""
        telegram_id = telegram_user_data['id']
        first_name = telegram_user_data.get('first_name', 'Debug')
        last_name = telegram_user_data.get('last_name', 'User')
        username = telegram_user_data.get('username', 'eatfit24_debug')
        django_username = f"tg_{telegram_id}"
        
        # Check if user exists
        try:
            user = User.objects.get(username=django_username)
        except User.DoesNotExist:
            # Create user
            user = User.objects.create_user(
                username=django_username,
                email=f"tg{telegram_id}@telegram.user",
                first_name=first_name,
                last_name=last_name
            )
            user.set_unusable_password()
            user.save()
        
        # Create TelegramUser record
        TelegramUser.objects.create(
            user=user,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=telegram_user_data.get('language_code', 'ru'),
            is_premium=False
        )
        
        # Ensure profile exists
        try:
            Profile.objects.get_or_create(user=user)
        except Exception as exc:
            logger.exception(
                "[DebugModeAuth] Failed to ensure Profile for debug user %s: %s", user.pk, exc
            )
        
        logger.info(
            "[DebugModeAuth] Created new debug user: user_id=%s telegram_id=%s",
            user.id, telegram_id
        )
        
        return user


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
            init_data = request.data.get('initData') or request.data.get('init_data')

        if not init_data:
            return None

        # Используем ЕДИНЫЙ сервис валидации
        auth_service = get_webapp_auth_service()
        parsed_data = auth_service.validate_init_data(init_data)

        if not parsed_data:
            raise exceptions.AuthenticationFailed('Invalid Telegram initData signature')

        # Получаем user data
        user_data = auth_service.get_user_data_from_init_data(parsed_data)
        if not user_data:
            raise exceptions.AuthenticationFailed('Invalid Telegram user data')

        # Get or create user
        user = self.get_or_create_user(user_data)
        return (user, None)

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
                # Создаем нового User с уникальным email
                user = User.objects.create_user(
                    username=username,
                    email=f"tg{telegram_id}@telegram.user",  # Unique email
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

            # Гарантируем, что у каждого Telegram-пользователя есть профиль
            try:
                Profile.objects.get_or_create(user=user)
            except Exception as exc:
                logger.exception(
                    "[TelegramWebAppAuth] Failed to ensure Profile for user %s: %s", user.pk, exc
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
        init_data = request.META.get('HTTP_X_TELEGRAM_INIT_DATA')

        if not telegram_id:
            # No Telegram headers present, allow other auth methods
            return None

        logger.info("[TelegramHeaderAuth] Processing telegram_id=%s, has_initData=%s",
                   telegram_id, bool(init_data))

        # Validate telegram_id is a valid integer
        try:
            telegram_id = int(telegram_id)
        except (ValueError, TypeError):
            logger.warning("[TelegramHeaderAuth] Invalid telegram_id format: %s", telegram_id)
            raise exceptions.AuthenticationFailed('Invalid Telegram ID format')

        if telegram_id <= 0:
            logger.warning("[TelegramHeaderAuth] Invalid telegram_id value: %s", telegram_id)
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
        logger.info("[TelegramHeaderAuth] Authenticated user_id=%s telegram_id=%s", user.id, telegram_id)

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
            # Create user with unique email to avoid IntegrityError
            user = User.objects.create_user(
                username=django_username,
                email=f"tg{telegram_id}@telegram.user",  # Unique email
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
