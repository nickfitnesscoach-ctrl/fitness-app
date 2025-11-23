"""
Email verification service for FoodMind AI.
Handles creation and sending of email verification tokens.
"""

import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import EmailVerificationToken

logger = logging.getLogger(__name__)


class EmailVerificationService:
    """
    Service for managing email verification process.
    """

    @staticmethod
    def create_verification_token(user):
        """
        Create a new email verification token for user.

        Args:
            user: User instance

        Returns:
            EmailVerificationToken instance
        """
        # Invalidate any existing unused tokens for this user
        EmailVerificationToken.objects.filter(
            user=user,
            is_used=False
        ).update(is_used=True)

        # Create new token
        token = EmailVerificationToken.objects.create(user=user)

        logger.info(f"Created verification token for user: {user.email}")

        return token

    @staticmethod
    def send_verification_email(user):
        """
        Send verification email to user.

        Args:
            user: User instance

        Raises:
            Exception: If email sending fails
        """
        # Create verification token
        token = EmailVerificationService.create_verification_token(user)

        # Build verification URL
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        verification_url = f"{frontend_url}/verify-email?token={token.token}"

        # Alternative: API verification URL
        api_url = getattr(settings, 'API_BASE_URL', 'http://localhost:8000')
        api_verification_url = f"{api_url}/api/v1/users/auth/verify-email/?token={token.token}"

        # Prepare email context
        context = {
            'user': user,
            'username': user.username,
            'verification_url': verification_url,
            'api_verification_url': api_verification_url,
            'token': token.token,
            'expires_hours': 24,
        }

        # Render email templates
        try:
            # HTML version (if template exists)
            html_message = render_to_string(
                'users/emails/verify_email.html',
                context
            )
        except Exception:
            # Fallback to plain text if HTML template doesn't exist
            html_message = None

        # Plain text version
        try:
            plain_message = render_to_string(
                'users/emails/verify_email.txt',
                context
            )
        except Exception:
            # Fallback plain text message
            plain_message = f"""
Здравствуйте, {user.username}!

Спасибо за регистрацию в FoodMind AI!

Пожалуйста, подтвердите ваш email адрес, перейдя по ссылке:
{api_verification_url}

Или используйте этот токен: {token.token}

Ссылка действительна в течение 24 часов.

Если вы не регистрировались на FoodMind AI, просто проигнорируйте это письмо.

---
С уважением,
Команда FoodMind AI
            """.strip()

        # Send email
        try:
            send_mail(
                subject='Подтвердите ваш email - FoodMind AI',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(f"Verification email sent to: {user.email}")

            return token

        except Exception as e:
            logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
            raise

    @staticmethod
    def verify_token(token_string):
        """
        Verify email token and mark email as verified.

        Args:
            token_string: Token string to verify

        Returns:
            tuple: (success: bool, message: str, user: User or None)
        """
        try:
            token = EmailVerificationToken.objects.get(token=token_string)

            # Check if token is valid
            if not token.is_valid:
                if token.is_used:
                    return False, "Этот токен уже был использован", None
                elif token.is_expired:
                    return False, "Срок действия токена истек", None
                else:
                    return False, "Неверный токен", None

            # Mark email as verified
            user = token.user
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])

            # Mark token as used
            token.mark_as_used()

            logger.info(f"Email verified for user: {user.email}")

            return True, "Email успешно подтвержден", user

        except EmailVerificationToken.DoesNotExist:
            logger.warning(f"Invalid verification token attempted: {token_string}")
            return False, "Неверный токен верификации", None

        except Exception as e:
            logger.error(f"Error verifying token {token_string}: {str(e)}")
            return False, f"Ошибка верификации: {str(e)}", None

    @staticmethod
    def cleanup_expired_tokens():
        """
        Delete expired verification tokens.
        Should be run periodically (e.g., daily via cron).

        Returns:
            int: Number of deleted tokens
        """
        from django.utils import timezone

        expired_tokens = EmailVerificationToken.objects.filter(
            expires_at__lt=timezone.now()
        )

        count = expired_tokens.count()
        expired_tokens.delete()

        logger.info(f"Cleaned up {count} expired verification tokens")

        return count
