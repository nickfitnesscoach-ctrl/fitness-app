"""
Throttling (rate limiting) classes for billing and webhook endpoints.

Protects against DoS attacks and webhook flooding.
"""

from rest_framework.throttling import AnonRateThrottle


class WebhookThrottle(AnonRateThrottle):
    """
    Throttle for webhook endpoints.

    Limits: 100 webhook calls per hour per IP address.
    This prevents webhook flooding and DoS attacks while allowing
    legitimate payment processing bursts.

    YooKassa typically sends 1-3 webhooks per payment (waiting_for_capture,
    succeeded, or canceled), so 100/hour allows ~30 payments/hour which is
    reasonable for most applications.
    """
    rate = '100/hour'
    scope = 'webhook'


class PaymentCreationThrottle(AnonRateThrottle):
    """
    Throttle for payment creation endpoint.

    Limits: 20 payment creations per hour per IP.
    Prevents abuse of payment system.
    """
    rate = '20/hour'
    scope = 'payment_creation'
