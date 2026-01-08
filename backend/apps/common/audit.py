"""
Security audit logging for FoodMind AI.

Provides centralized logging of security-related events for monitoring,
incident response, and compliance.
"""

import ipaddress
import logging
from typing import Optional, Dict, Any

from django.conf import settings

logger = logging.getLogger('security')


def _is_ip_in_trusted_proxies(ip_str: str) -> bool:
    """
    Check if IP address is in trusted proxy list.

    Supports both individual IPs and CIDR ranges (e.g., 172.24.0.0/16).

    Args:
        ip_str: IP address to check (e.g., "172.24.0.1")

    Returns:
        bool: True if IP is trusted, False otherwise
    """
    try:
        client_ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # Invalid IP format
        return False

    trusted_proxies = getattr(settings, "TRUSTED_PROXIES", [])

    for proxy_entry in trusted_proxies:
        proxy_entry = proxy_entry.strip()
        if not proxy_entry:
            continue

        try:
            # Try as CIDR network (e.g., 172.24.0.0/16)
            if "/" in proxy_entry:
                network = ipaddress.ip_network(proxy_entry, strict=False)
                if client_ip in network:
                    return True
            else:
                # Try as single IP
                proxy_ip = ipaddress.ip_address(proxy_entry)
                if client_ip == proxy_ip:
                    return True
        except ValueError:
            # Invalid proxy entry, skip it
            logger.warning(f"Invalid TRUSTED_PROXIES entry: {proxy_entry}")
            continue

    return False


def get_client_ip(request) -> str:
    """
    Get real client IP address from request with XFF protection.

    Security model:
    - By default: NEVER trust X-Forwarded-For (prevents IP spoofing)
    - If TRUSTED_PROXIES_ENABLED=true: trust XFF ONLY from verified proxies
    - Always falls back to REMOTE_ADDR if XFF is not trusted

    Configuration (settings.py):
        TRUSTED_PROXIES_ENABLED = True/False
        TRUSTED_PROXIES = ["172.24.0.0/16", "10.0.0.1"]

    Used by:
    - Security audit logs (login, payment, suspicious activity)
    - Rate limiting (throttles)

    Args:
        request: Django/DRF request object

    Returns:
        str: Client IP address (either from XFF if trusted, or REMOTE_ADDR)
    """
    remote_addr = request.META.get('REMOTE_ADDR', 'unknown')

    # Secure default: don't trust XFF unless explicitly enabled
    trusted_proxies_enabled = getattr(settings, "TRUSTED_PROXIES_ENABLED", False)

    if not trusted_proxies_enabled:
        # Security: XFF trust disabled, always use REMOTE_ADDR
        return remote_addr

    # Check if request came through trusted proxy
    if not _is_ip_in_trusted_proxies(remote_addr):
        # Request did NOT come from trusted proxy → don't trust XFF
        # This prevents external clients from spoofing X-Forwarded-For
        return remote_addr

    # Request came from trusted proxy → parse XFF
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

    if not x_forwarded_for:
        # No XFF header even though proxy is trusted → use REMOTE_ADDR
        return remote_addr

    # Parse XFF: take leftmost public IP (real client IP)
    # Format: "client_ip, proxy1_ip, proxy2_ip"
    xff_ips = [ip.strip() for ip in x_forwarded_for.split(',') if ip.strip()]

    if not xff_ips:
        # Empty XFF → fallback to REMOTE_ADDR
        return remote_addr

    # Return first (leftmost) IP in chain = real client IP
    # Note: We already verified that REMOTE_ADDR is trusted proxy,
    # so we can trust the leftmost IP in XFF
    return xff_ips[0]


def get_user_agent(request) -> str:
    """
    Get user agent string from request.

    Args:
        request: Django/DRF request object

    Returns:
        str: User agent string
    """
    return request.META.get('HTTP_USER_AGENT', 'unknown')


class SecurityAuditLogger:
    """
    Centralized security event logging.

    Logs all security-relevant events with consistent format including:
    - Event type
    - User identification
    - IP address
    - User agent
    - Timestamp (automatic via logging)
    - Additional context
    """

    @staticmethod
    def log_login_success(user, request, method: str = 'password'):
        """
        Log successful login attempt.

        Args:
            user: Authenticated user object
            request: Django/DRF request object
            method: Authentication method (password, token, etc.)
        """
        logger.info(
            f"LOGIN_SUCCESS: user={user.email} (id={user.id}) "
            f"ip={get_client_ip(request)} method={method} "
            f"user_agent={get_user_agent(request)}"
        )

    @staticmethod
    def log_login_failure(email: str, request, reason: str = 'invalid_credentials'):
        """
        Log failed login attempt.

        Args:
            email: Email address used in login attempt
            request: Django/DRF request object
            reason: Failure reason (invalid_credentials, account_disabled, etc.)
        """
        logger.warning(
            f"LOGIN_FAILURE: email={email} ip={get_client_ip(request)} "
            f"reason={reason} user_agent={get_user_agent(request)}"
        )

    @staticmethod
    def log_logout(user, request):
        """
        Log user logout.

        Args:
            user: User object
            request: Django/DRF request object
        """
        logger.info(
            f"LOGOUT: user={user.email} (id={user.id}) "
            f"ip={get_client_ip(request)}"
        )

    @staticmethod
    def log_registration(user, request):
        """
        Log new user registration.

        Args:
            user: Newly created user object
            request: Django/DRF request object
        """
        logger.info(
            f"REGISTRATION: user={user.email} (id={user.id}) "
            f"ip={get_client_ip(request)} user_agent={get_user_agent(request)}"
        )

    @staticmethod
    def log_password_change(user, request, success: bool = True):
        """
        Log password change attempt.

        Args:
            user: User object
            request: Django/DRF request object
            success: Whether password change succeeded
        """
        status = "SUCCESS" if success else "FAILURE"
        log_func = logger.info if success else logger.warning

        log_func(
            f"PASSWORD_CHANGE_{status}: user={user.email} (id={user.id}) "
            f"ip={get_client_ip(request)}"
        )

    @staticmethod
    def log_account_deletion(user, request):
        """
        Log account deletion.

        Args:
            user: User object being deleted
            request: Django/DRF request object
        """
        logger.warning(
            f"ACCOUNT_DELETION: user={user.email} (id={user.id}) "
            f"ip={get_client_ip(request)}"
        )

    @staticmethod
    def log_permission_denied(user, request, resource: str, action: str):
        """
        Log unauthorized access attempt.

        Args:
            user: User object (or None for anonymous)
            request: Django/DRF request object
            resource: Resource being accessed
            action: Action being attempted
        """
        user_id = f"{user.email} (id={user.id})" if user and user.is_authenticated else "anonymous"
        logger.warning(
            f"PERMISSION_DENIED: user={user_id} "
            f"ip={get_client_ip(request)} resource={resource} action={action}"
        )

    @staticmethod
    def log_email_verification(user, request, success: bool = True):
        """
        Log email verification attempt.

        Args:
            user: User object
            request: Django/DRF request object
            success: Whether verification succeeded
        """
        status = "SUCCESS" if success else "FAILURE"
        log_func = logger.info if success else logger.warning

        log_func(
            f"EMAIL_VERIFICATION_{status}: user={user.email} (id={user.id}) "
            f"ip={get_client_ip(request)}"
        )

    @staticmethod
    def log_email_verification_failure(token, request, reason: str):
        """
        Log failed email verification attempt.

        Args:
            token: Token string that was used
            request: Django/DRF request object
            reason: Reason for failure
        """
        logger.warning(
            f"EMAIL_VERIFICATION_FAILURE: token={token[:16]}... "
            f"ip={get_client_ip(request)} reason={reason}"
        )

    @staticmethod
    def log_verification_email_resend(user, request):
        """
        Log verification email resend request.

        Args:
            user: User object
            request: Django/DRF request object
        """
        logger.info(
            f"VERIFICATION_EMAIL_RESEND: user={user.email} (id={user.id}) "
            f"ip={get_client_ip(request)}"
        )

    @staticmethod
    def log_verification_email_failure(user, request, reason: str):
        """
        Log failed verification email send.

        Args:
            user: User object
            request: Django/DRF request object
            reason: Reason for failure
        """
        logger.error(
            f"VERIFICATION_EMAIL_FAILURE: user={user.email} (id={user.id}) "
            f"ip={get_client_ip(request)} reason={reason}"
        )

    @staticmethod
    def log_suspicious_activity(
        user,
        request,
        activity_type: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Log suspicious activity.

        Args:
            user: User object (or None)
            request: Django/DRF request object
            activity_type: Type of suspicious activity
            details: Additional context (will be logged as key=value pairs)
        """
        user_id = f"{user.email} (id={user.id})" if user and user.is_authenticated else "anonymous"
        details_str = " ".join(f"{k}={v}" for k, v in (details or {}).items())

        logger.warning(
            f"SUSPICIOUS_ACTIVITY: user={user_id} "
            f"ip={get_client_ip(request)} type={activity_type} {details_str}"
        )

    @staticmethod
    def log_rate_limit_exceeded(request, endpoint: str, limit: str):
        """
        Log rate limit violation.

        Args:
            request: Django/DRF request object
            endpoint: Endpoint being rate limited
            limit: Rate limit that was exceeded
        """
        user_id = "anonymous"
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = f"{request.user.email} (id={request.user.id})"

        logger.warning(
            f"RATE_LIMIT_EXCEEDED: user={user_id} "
            f"ip={get_client_ip(request)} endpoint={endpoint} limit={limit}"
        )

    @staticmethod
    def log_payment_created(user, amount: float, plan: str, request):
        """
        Log payment creation.

        Args:
            user: User object
            amount: Payment amount
            plan: Subscription plan
            request: Django/DRF request object
        """
        logger.info(
            f"PAYMENT_CREATED: user={user.email} (id={user.id}) "
            f"amount={amount} plan={plan} ip={get_client_ip(request)}"
        )

    @staticmethod
    def log_payment_success(user, payment_id: str, amount: float, plan: str):
        """
        Log successful payment.

        Args:
            user: User object
            payment_id: Payment ID
            amount: Payment amount
            plan: Subscription plan
        """
        logger.info(
            f"PAYMENT_SUCCESS: user={user.email} (id={user.id}) "
            f"payment_id={payment_id} amount={amount} plan={plan}"
        )

    @staticmethod
    def log_payment_failure(user, payment_id: str, amount: float, reason: str):
        """
        Log failed payment.

        Args:
            user: User object
            payment_id: Payment ID
            amount: Payment amount
            reason: Failure reason
        """
        logger.warning(
            f"PAYMENT_FAILURE: user={user.email} (id={user.id}) "
            f"payment_id={payment_id} amount={amount} reason={reason}"
        )

    @staticmethod
    def log_subscription_change(
        user,
        old_plan: Optional[str],
        new_plan: str,
        request
    ):
        """
        Log subscription plan change.

        Args:
            user: User object
            old_plan: Previous plan name (None for new subscription)
            new_plan: New plan name
            request: Django/DRF request object
        """
        change_type = "UPGRADE" if old_plan else "NEW"
        logger.info(
            f"SUBSCRIPTION_{change_type}: user={user.email} (id={user.id}) "
            f"old_plan={old_plan or 'none'} new_plan={new_plan} "
            f"ip={get_client_ip(request)}"
        )

    @staticmethod
    def log_api_error(
        request,
        error_type: str,
        error_message: str,
        endpoint: str
    ):
        """
        Log API error.

        Args:
            request: Django/DRF request object
            error_type: Error type
            error_message: Error message
            endpoint: API endpoint
        """
        user_id = "anonymous"
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = f"{request.user.email} (id={request.user.id})"

        logger.error(
            f"API_ERROR: user={user_id} ip={get_client_ip(request)} "
            f"endpoint={endpoint} error_type={error_type} message={error_message}"
        )
