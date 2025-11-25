"""
Email validation utilities for FoodMind AI.
Validates email domains and prevents disposable email addresses.
Also includes avatar file validation.
"""

import os
import logging
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# List of known disposable email domains
# Source: https://github.com/disposable-email-domains/disposable-email-domains
DISPOSABLE_EMAIL_DOMAINS = {
    '10minutemail.com', '10minutemail.net', '10minutemail.org',
    '20minutemail.com', '30minutemail.com', '60minutemail.com',
    'guerrillamail.com', 'guerrillamail.net', 'guerrillamail.org',
    'tempmail.com', 'temp-mail.org', 'temp-mail.io',
    'throwaway.email', 'trashmail.com', 'mailinator.com',
    'maildrop.cc', 'getnada.com', 'yopmail.com',
    'fakeinbox.com', 'sharklasers.com', 'spam4.me',
    'mintemail.com', 'mytemp.email', 'tempr.email',
    'mohmal.com', 'emailondeck.com', 'getairmail.com',
    'dispostable.com', 'throam.com', 'jetable.org',
    'mailnesia.com', 'mailnator.com', 'mailcatch.com',
    'mailforspam.com', 'binkmail.com', 'spamgourmet.com',
    'mailexpire.com', 'tempomail.fr', 'incognitomail.com',
    'anonbox.net', 'anonymbox.com', 'airmail.cc',
    'harakirimail.com', 'mt2015.com', 'mt2014.com',
    'yopmail.fr', 'yopmail.net', 'cool.fr.nf',
    'jetable.fr.nf', 'nospam.ze.tc', 'nomail.xl.cx',
    'mega.zik.dj', 'speed.1s.fr', 'courriel.fr.nf',
    'moncourrier.fr.nf', 'monemail.fr.nf', 'monmail.fr.nf',
    'burnermail.io', 'emailna.co', 'inboxkitten.com',
}


def validate_email_domain(email):
    """
    Validate that email domain exists and is not a disposable email service.

    Args:
        email: Email address to validate

    Raises:
        ValidationError: If email domain is invalid or disposable
    """
    if not email:
        raise ValidationError("Email адрес обязателен")

    # First, validate basic email format
    email_validator = EmailValidator()
    try:
        email_validator(email)
    except ValidationError:
        raise ValidationError("Некорректный формат email адреса")

    # Extract domain
    try:
        domain = email.split('@')[1].lower()
    except (IndexError, AttributeError):
        raise ValidationError("Некорректный формат email адреса")

    # Check if domain is in disposable list
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        logger.warning(f"Attempted registration with disposable email: {email}")
        raise ValidationError(
            "Использование временных email адресов не разрешено. "
            "Пожалуйста, используйте постоянный email адрес."
        )

    # Check for suspicious patterns
    suspicious_patterns = [
        'temp', 'trash', 'fake', 'spam', 'throw', 'dispos',
        'guerrilla', 'mailinator', 'yopmail', 'minute'
    ]

    for pattern in suspicious_patterns:
        if pattern in domain:
            logger.warning(f"Suspicious email domain detected: {domain}")
            raise ValidationError(
                "Этот email адрес выглядит подозрительно. "
                "Пожалуйста, используйте надежный email сервис."
            )

    # Validate DNS MX records (optional - can be slow)
    # Uncomment if you want to check MX records
    # This requires dnspython: pip install dnspython
    """
    try:
        import dns.resolver
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            if not mx_records:
                raise ValidationError("Email домен не имеет почтовых серверов (MX записей)")
        except dns.resolver.NXDOMAIN:
            raise ValidationError("Email домен не существует")
        except dns.resolver.NoAnswer:
            raise ValidationError("Email домен не имеет почтовых серверов (MX записей)")
        except dns.resolver.Timeout:
            logger.warning(f"DNS timeout for domain: {domain}")
            # Don't fail on timeout, just log
        except Exception as e:
            logger.error(f"DNS validation error for domain {domain}: {str(e)}")
            # Don't fail on other DNS errors
    except ImportError:
        # dnspython not installed, skip MX validation
        pass
    """

    return email


def validate_email_not_exists(email):
    """
    Validate that email is not already registered.

    Args:
        email: Email address to validate

    Raises:
        ValidationError: If email is already registered
    """
    from django.contrib.auth.models import User

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError(
            "Пользователь с таким email уже зарегистрирован. "
            "Попробуйте войти или восстановить пароль."
        )

    return email


def is_email_verified(user):
    """
    Check if user's email is verified.

    Args:
        user: User instance

    Returns:
        bool: True if email is verified, False otherwise
    """
    try:
        return user.profile.email_verified
    except Exception:
        return False


def mark_email_as_verified(user):
    """
    Mark user's email as verified.

    Args:
        user: User instance
    """
    try:
        profile = user.profile
        profile.email_verified = True
        profile.save(update_fields=['email_verified'])
        logger.info(f"Email verified for user: {user.email}")
    except Exception as e:
        logger.error(f"Failed to mark email as verified for user {user.email}: {str(e)}")
        raise


# ============================================================
# Avatar File Validators
# ============================================================

# Avatar validation settings
AVATAR_MAX_SIZE_MB = 5
AVATAR_MAX_SIZE_BYTES = AVATAR_MAX_SIZE_MB * 1024 * 1024
AVATAR_ALLOWED_TYPES = ('image/jpeg', 'image/png', 'image/webp')
AVATAR_ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


def validate_avatar_file_extension(value):
    """
    Validate that the uploaded file has an allowed extension.

    Args:
        value: FieldFile object (e.g., from ImageField)

    Raises:
        ValidationError: If file extension is not allowed
    """
    if not value:
        return

    ext = os.path.splitext(value.name)[1].lower()
    if ext not in AVATAR_ALLOWED_EXTENSIONS:
        raise ValidationError(
            _(f'Неверный формат файла. Разрешены только: {", ".join(AVATAR_ALLOWED_EXTENSIONS)}'),
            code='invalid_extension'
        )


def validate_avatar_file_size(value):
    """
    Validate that the uploaded file size does not exceed the limit.

    Args:
        value: FieldFile object (e.g., from ImageField)

    Raises:
        ValidationError: If file size exceeds maximum allowed size
    """
    if not value:
        return

    if value.size > AVATAR_MAX_SIZE_BYTES:
        raise ValidationError(
            _(f'Размер файла превышает {AVATAR_MAX_SIZE_MB} МБ. '
              f'Текущий размер: {value.size / (1024 * 1024):.1f} МБ'),
            code='file_too_large'
        )


def validate_avatar_mime_type(file):
    """
    Validate that the uploaded file has an allowed MIME type.

    Args:
        file: InMemoryUploadedFile or TemporaryUploadedFile

    Raises:
        ValidationError: If MIME type is not allowed
    """
    if not file:
        return

    content_type = getattr(file, 'content_type', None)
    if content_type and content_type not in AVATAR_ALLOWED_TYPES:
        raise ValidationError(
            _(f'Неверный формат файла. Разрешены только: JPEG, PNG, WebP'),
            code='invalid_mime_type'
        )
