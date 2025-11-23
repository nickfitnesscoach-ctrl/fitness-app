"""
Throttling (rate limiting) classes for user authentication endpoints.

Protects against brute force attacks and abuse.
"""

from django.core.cache import cache
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, SimpleRateThrottle


class RegisterThrottle(AnonRateThrottle):
    """
    Throttle for registration endpoint.

    Limits: 5 registrations per hour per IP address.
    This prevents automated account creation and spam.
    """
    rate = '5/hour'
    scope = 'register'


class LoginThrottle(SimpleRateThrottle):
    """
    Advanced throttle for login endpoint with progressive rate limiting.

    Base limits: 5 login attempts per 15 minutes per IP address.
    Progressive blocking after failed attempts:
    - 3 failed attempts: 5 minute cooldown
    - 5 failed attempts: 30 minute cooldown
    - 10 failed attempts: 2 hour cooldown

    This prevents brute force password attacks with exponential backoff.

    SECURITY FEATURES:
    - Tracks failed login attempts per IP
    - Exponential backoff after repeated failures
    - Automatic reset after successful login
    - Cache-based tracking (no database overhead)
    """
    scope = 'login'
    rate = '5/15min'

    def get_cache_key(self, request, view):
        """Generate cache key based on IP address."""
        if request.user and request.user.is_authenticated:
            # Authenticated users bypass IP-based throttling
            return None

        # Use IP address for anonymous users
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

    def allow_request(self, request, view):
        """
        Check if request should be allowed.

        Implements progressive rate limiting based on failed login attempts.
        """
        if request.user and request.user.is_authenticated:
            # Authenticated users bypass throttling
            return True

        # Get IP address
        ip_address = self.get_ident(request)
        failed_attempts_key = f'login_failures:{ip_address}'
        lockout_key = f'login_lockout:{ip_address}'

        # Check if IP is currently locked out
        lockout_until = cache.get(lockout_key)
        if lockout_until:
            # IP is locked out
            return False

        # Apply base rate limit
        if not super().allow_request(request, view):
            return False

        # Track failed attempts (done in serializer after validation)
        return True

    @staticmethod
    def record_failed_attempt(ip_address):
        """
        Record a failed login attempt and apply progressive lockout.

        Args:
            ip_address: IP address of the failed attempt

        Returns:
            tuple: (is_locked, lockout_seconds, attempts_count)
        """
        failed_attempts_key = f'login_failures:{ip_address}'
        lockout_key = f'login_lockout:{ip_address}'

        # Increment failure counter
        failures = cache.get(failed_attempts_key, 0) + 1
        cache.set(failed_attempts_key, failures, timeout=3600)  # Track for 1 hour

        # Progressive lockout based on failures
        lockout_duration = 0
        if failures >= 10:
            lockout_duration = 7200  # 2 hours
        elif failures >= 5:
            lockout_duration = 1800  # 30 minutes
        elif failures >= 3:
            lockout_duration = 300  # 5 minutes

        if lockout_duration > 0:
            cache.set(lockout_key, True, timeout=lockout_duration)
            return True, lockout_duration, failures

        return False, 0, failures

    @staticmethod
    def clear_failed_attempts(ip_address):
        """
        Clear failed login attempts after successful login.

        Args:
            ip_address: IP address to clear
        """
        failed_attempts_key = f'login_failures:{ip_address}'
        lockout_key = f'login_lockout:{ip_address}'

        cache.delete(failed_attempts_key)
        cache.delete(lockout_key)


class PasswordChangeThrottle(UserRateThrottle):
    """
    Throttle for password change endpoint.

    Limits: 5 password changes per hour per authenticated user.
    This prevents abuse and potential account takeover attempts.
    """
    rate = '5/hour'
    scope = 'password_change'


class ProfileUpdateThrottle(UserRateThrottle):
    """
    Throttle for profile update endpoint.

    Limits: 30 updates per hour per authenticated user.
    Allows frequent legitimate updates while preventing abuse.
    """
    rate = '30/hour'
    scope = 'profile_update'
