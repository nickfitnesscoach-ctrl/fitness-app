"""
Views for users app.
"""

from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.common.audit import SecurityAuditLogger

from .models import Profile, EmailVerificationToken
from .validators import mark_email_as_verified
from .serializers import (
    ChangePasswordSerializer,
    ProfileSerializer,
    TokenSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from .throttles import (
    RegisterThrottle,
    LoginThrottle,
    PasswordChangeThrottle,
    ProfileUpdateThrottle,
)


@extend_schema(tags=['Authentication'])
@extend_schema_view(
    post=extend_schema(
        summary="Регистрация нового пользователя",
        description="Создание нового пользователя с email и паролем. После успешной регистрации возвращаются JWT токены.",
        request=UserRegistrationSerializer,
        responses={
            201: TokenSerializer,
            400: {"description": "Ошибка валидации данных"}
        }
    )
)
class RegisterView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    POST /api/v1/users/auth/register/
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    throttle_classes = [RegisterThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # SECURITY: Log successful registration
        SecurityAuditLogger.log_registration(user, request)

        # Send verification email
        try:
            from .services import EmailVerificationService
            EmailVerificationService.send_verification_email(user)
        except Exception as e:
            # Log error but don't fail registration
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send verification email to {user.email}: {str(e)}")

        # Generate JWT tokens
        tokens = TokenSerializer.get_tokens_for_user(user)

        # Add verification status to response
        response_data = {
            **tokens,
            'email_verified': False,
            'message': 'Регистрация успешна! Проверьте ваш email для подтверждения адреса.'
        }

        return Response(
            response_data,
            status=status.HTTP_201_CREATED
        )


@extend_schema(tags=['Authentication'])
@extend_schema_view(
    post=extend_schema(
        summary="Вход пользователя",
        description="""
        Аутентификация пользователя по email и паролю. Возвращает JWT токены.

        **Защита от брутфорса:**
        - Базовый лимит: 5 попыток в 15 минут
        - Прогрессивная блокировка:
          - 3 неудачные попытки → 5 минут ожидания
          - 5 неудачных попыток → 30 минут ожидания
          - 10 неудачных попыток → 2 часа ожидания
        """,
        request=UserLoginSerializer,
        responses={
            200: TokenSerializer,
            400: {"description": "Неверные учетные данные"},
            429: {"description": "Слишком много попыток входа. Попробуйте позже."}
        }
    )
)
class LoginView(APIView):
    """
    API endpoint for user login with progressive rate limiting.

    POST /api/v1/users/auth/login/

    SECURITY FEATURES:
    - Progressive rate limiting (exponential backoff)
    - Failed attempt tracking per IP
    - Automatic lockout after repeated failures
    - Audit logging of all login attempts
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        ip_address = self.get_client_ip(request)

        # Validate and handle login failures
        if not serializer.is_valid():
            # SECURITY: Record failed login attempt
            email = request.data.get('email', 'unknown')

            # Track failed attempt for progressive rate limiting
            is_locked, lockout_seconds, attempts = LoginThrottle.record_failed_attempt(ip_address)

            # SECURITY: Log failed login attempt with details
            SecurityAuditLogger.log_login_failure(
                email,
                request,
                reason=f'invalid_credentials (attempt {attempts})'
            )

            # Return user-friendly error message
            error_response = serializer.errors

            if is_locked:
                lockout_minutes = lockout_seconds // 60
                error_response['detail'] = (
                    f"Слишком много неудачных попыток входа ({attempts} попыток). "
                    f"Аккаунт заблокирован на {lockout_minutes} минут."
                )
                return Response(error_response, status=status.HTTP_429_TOO_MANY_REQUESTS)

            return Response(error_response, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = serializer.validated_data['user']

            # SECURITY: Clear failed attempts after successful login
            LoginThrottle.clear_failed_attempts(ip_address)

            # SECURITY: Log successful login
            SecurityAuditLogger.log_login_success(user, request, method='password')

            # Generate JWT tokens
            tokens = TokenSerializer.get_tokens_for_user(user)

            return Response(tokens, status=status.HTTP_200_OK)

        except Exception as e:
            # SECURITY: Log unexpected login error
            email = request.data.get('email', 'unknown')
            SecurityAuditLogger.log_login_failure(email, request, reason=f'exception: {str(e)}')
            raise


@extend_schema(tags=['Authentication'])
class CustomTokenRefreshView(TokenRefreshView):
    """
    API endpoint for refreshing JWT access token.
    POST /api/v1/users/auth/refresh/

    Takes refresh token and returns new access token.
    """
    pass


@extend_schema(tags=['Profile'])
@extend_schema_view(
    get=extend_schema(
        summary="Получить профиль текущего пользователя",
        description="Возвращает информацию о профиле авторизованного пользователя.",
        responses={200: UserSerializer}
    ),
    put=extend_schema(
        summary="Обновить профиль полностью",
        description="Полное обновление профиля пользователя.",
        request=ProfileSerializer,
        responses={200: UserSerializer}
    ),
    patch=extend_schema(
        summary="Частично обновить профиль",
        description="Частичное обновление полей профиля пользователя.",
        request=ProfileSerializer,
        responses={200: UserSerializer}
    )
)
class ProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for viewing and updating user profile.
    GET/PUT/PATCH /api/v1/users/profile/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    throttle_classes = [ProfileUpdateThrottle]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        import logging
        logger = logging.getLogger(__name__)

        partial = kwargs.pop('partial', False)
        user = self.get_object()

        # DEBUG: Log incoming request data
        logger.info(f"[ProfileView] PATCH /api/v1/users/profile/ - User: {user.id}, Data: {request.data}")

        # Update username if provided
        if 'username' in request.data:
            user.username = request.data['username']
            user.save()

        # Update profile data (all other fields)
        profile = user.profile
        profile_serializer = ProfileSerializer(
            profile,
            data=request.data,
            partial=partial
        )

        # DEBUG: Log validation result
        if not profile_serializer.is_valid():
            logger.error(f"[ProfileView] Validation failed: {profile_serializer.errors}")

        profile_serializer.is_valid(raise_exception=True)
        profile_serializer.save()

        # DEBUG: Log successful save
        logger.info(f"[ProfileView] Profile updated successfully for user {user.id}")

        # Return updated user with profile
        user_serializer = self.get_serializer(user)
        return Response(user_serializer.data)


@extend_schema(tags=['Profile'])
@extend_schema_view(
    post=extend_schema(
        summary="Изменить пароль",
        description="Изменение пароля авторизованного пользователя.",
        request=ChangePasswordSerializer,
        responses={
            200: {"description": "Пароль успешно изменен"},
            400: {"description": "Ошибка валидации"}
        }
    )
)
class ChangePasswordView(APIView):
    """
    API endpoint for changing user password.
    POST /api/v1/users/profile/change-password/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordChangeThrottle]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )

        try:
            serializer.is_valid(raise_exception=True)

            # Change password
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()

            # SECURITY: Log successful password change
            SecurityAuditLogger.log_password_change(user, request, success=True)

            return Response(
                {"detail": "Пароль успешно изменен."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            # SECURITY: Log failed password change
            SecurityAuditLogger.log_password_change(request.user, request, success=False)
            raise


@extend_schema(tags=['Profile'])
@extend_schema_view(
    delete=extend_schema(
        summary="Удалить аккаунт",
        description="Удаление аккаунта текущего пользователя.",
        responses={
            204: {"description": "Аккаунт успешно удален"},
            401: {"description": "Не авторизован"}
        }
    )
)
class DeleteAccountView(APIView):
    """
    API endpoint for deleting user account.
    DELETE /api/v1/users/profile/delete/
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user

        # SECURITY: Log account deletion before deleting
        SecurityAuditLogger.log_account_deletion(user, request)

        user.delete()

        return Response(
            {"detail": "Аккаунт успешно удален."},
            status=status.HTTP_204_NO_CONTENT
        )


@extend_schema(tags=['Email Verification'])
@extend_schema_view(
    get=extend_schema(
        summary="Подтвердить email",
        description="Подтверждение email адреса по токену из письма. Токен действителен 24 часа.",
        parameters=[
            {
                'name': 'token',
                'in': 'query',
                'description': 'Токен верификации из email',
                'required': True,
                'schema': {'type': 'string'}
            }
        ],
        responses={
            200: {"description": "Email успешно подтвержден"},
            400: {"description": "Неверный или истекший токен"}
        }
    )
)
class VerifyEmailView(APIView):
    """
    API endpoint for email verification.
    GET /api/v1/users/auth/verify-email/?token=<token>
    """
    permission_classes = [AllowAny]

    def get(self, request):
        token_string = request.query_params.get('token')

        if not token_string:
            return Response(
                {"error": "Токен верификации не предоставлен"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Find token
            token = EmailVerificationToken.objects.get(token=token_string)

            # Check if token is valid
            if not token.is_valid:
                if token.is_used:
                    return Response(
                        {"error": "Этот токен уже был использован"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                elif token.is_expired:
                    return Response(
                        {"error": "Срок действия токена истек. Запросите новое письмо с подтверждением."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Mark email as verified
            user = token.user
            mark_email_as_verified(user)

            # Mark token as used
            token.mark_as_used()

            # SECURITY: Log email verification
            SecurityAuditLogger.log_email_verification(user, request, success=True)

            return Response(
                {
                    "detail": "Email успешно подтвержден!",
                    "email": user.email,
                    "username": user.username
                },
                status=status.HTTP_200_OK
            )

        except EmailVerificationToken.DoesNotExist:
            # SECURITY: Log failed verification attempt
            SecurityAuditLogger.log_email_verification_failure(
                token_string,
                request,
                reason='invalid_token'
            )

            return Response(
                {"error": "Неверный токен верификации"},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            # SECURITY: Log unexpected error
            SecurityAuditLogger.log_email_verification_failure(
                token_string,
                request,
                reason=str(e)
            )
            raise


@extend_schema(tags=['Email Verification'])
@extend_schema_view(
    post=extend_schema(
        summary="Повторно отправить письмо с подтверждением",
        description="Отправка нового письма с подтверждением email. Доступно только авторизованным пользователям с неподтвержденным email.",
        responses={
            200: {"description": "Письмо отправлено"},
            400: {"description": "Email уже подтвержден или ошибка отправки"}
        }
    )
)
class ResendVerificationEmailView(APIView):
    """
    API endpoint for resending verification email.
    POST /api/v1/users/auth/resend-verification/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Check if email is already verified
        if user.profile.email_verified:
            return Response(
                {"detail": "Ваш email уже подтвержден"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Import here to avoid circular dependency
        from .services import EmailVerificationService

        try:
            # Create and send new verification token
            EmailVerificationService.send_verification_email(user)

            # SECURITY: Log verification email resend
            SecurityAuditLogger.log_verification_email_resend(user, request)

            return Response(
                {
                    "detail": "Письмо с подтверждением отправлено на ваш email",
                    "email": user.email
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            # SECURITY: Log failed email send
            SecurityAuditLogger.log_verification_email_failure(
                user,
                request,
                reason=str(e)
            )

            return Response(
                {"error": "Не удалось отправить письмо. Попробуйте позже."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=['Profile'])
@extend_schema_view(
    post=extend_schema(
        summary="Загрузить/обновить аватар профиля",
        description="""
        Загрузка или обновление аватара текущего пользователя.

        **Ограничения:**
        - Максимальный размер файла: 5 МБ
        - Допустимые форматы: JPEG, PNG, WebP
        - Content-Type: multipart/form-data
        - Поле файла: avatar

        Возвращает обновлённый профиль пользователя с URL аватара.
        """,
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'avatar': {
                        'type': 'string',
                        'format': 'binary',
                        'description': 'Файл изображения (JPG, PNG, WebP)'
                    }
                }
            }
        },
        responses={
            200: UserSerializer,
            400: {"description": "Неверный формат файла или слишком большой размер"},
            401: {"description": "Не авторизован"}
        }
    )
)
class UploadAvatarView(APIView):
    """
    API endpoint for uploading/updating user avatar.
    POST /api/v1/users/profile/avatar/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProfileUpdateThrottle]

    def post(self, request):
        import logging
        from django.core.exceptions import ValidationError as DjangoValidationError
        from .validators import (
            convert_heic_to_jpeg,
            is_heic_file,
            validate_avatar_file_extension,
            validate_avatar_file_size,
            validate_avatar_mime_type,
        )

        logger = logging.getLogger(__name__)

        # Get uploaded file
        avatar_file = request.FILES.get('avatar')

        if not avatar_file:
            return Response(
                {
                    "code": "avatar_missing",
                    "detail": "Файл аватара не предоставлен. Используйте поле 'avatar' в multipart/form-data.",
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate using centralized validators
        try:
            # Convert HEIC/HEIF from iOS to JPEG for cross-platform support
            if is_heic_file(avatar_file):
                logger.info(
                    "Converting HEIC avatar for user %s (name=%s, type=%s)",
                    request.user.id,
                    avatar_file.name,
                    getattr(avatar_file, 'content_type', 'unknown'),
                )
                avatar_file = convert_heic_to_jpeg(avatar_file)

            # Validate MIME type first (from uploaded file)
            validate_avatar_mime_type(avatar_file)

            # Validate file size
            validate_avatar_file_size(avatar_file)

            # Validate file extension
            validate_avatar_file_extension(avatar_file)

        except DjangoValidationError as e:
            # Return validation error message
            return Response(
                {
                    "code": getattr(e, 'code', 'invalid_avatar'),
                    "detail": str(e.message) if hasattr(e, 'message') else str(e),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get user profile
        user = request.user
        profile = user.profile

        try:
            # Use the safe set_avatar method which:
            # 1. Deletes old avatar safely
            # 2. Sets new avatar
            # 3. Increments avatar_version
            # 4. Saves profile
            profile.set_avatar(avatar_file)

            logger.info(f"Avatar uploaded successfully for user {user.id}, version {profile.avatar_version}")

        except Exception as e:
            logger.error(f"Failed to upload avatar for user {user.id}: {str(e)}")
            return Response(
                {"code": "avatar_upload_failed", "detail": "Не удалось загрузить аватар. Попробуйте позже."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Return updated user with profile (including avatar_url with version)
        user_serializer = UserSerializer(user, context={'request': request})
        return Response(user_serializer.data, status=status.HTTP_200_OK)
