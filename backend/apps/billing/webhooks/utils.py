"""
Utility functions for YooKassa webhooks.
"""

import ipaddress
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# YooKassa official IP addresses for webhook notifications
YOOKASSA_IP_RANGES = [
    '185.71.76.0/27',
    '185.71.77.0/27',
    '77.75.153.0/25',
    '77.75.154.128/25',
    '2a02:5180::/32',
]


def is_ip_allowed(client_ip: str) -> bool:
    """
    Check if client IP is in YooKassa whitelist.

    Args:
        client_ip: IP address string

    Returns:
        bool: True if IP is allowed, False otherwise
    """
    # Allow localhost for development
    if getattr(settings, 'DEBUG', False) and client_ip in ['127.0.0.1', 'localhost', '::1']:
        return True

    try:
        client_addr = ipaddress.ip_address(client_ip)

        for ip_range in YOOKASSA_IP_RANGES:
            network = ipaddress.ip_network(ip_range, strict=False)
            if client_addr in network:
                return True

        return False
    except ValueError:
        logger.error(f"Invalid IP address format: {client_ip}")
        return False


def get_client_ip(request) -> str:
    """
    Extract client IP from request.
    
    Handles X-Real-IP and X-Forwarded-For headers from proxy.
    """
    return (
        request.META.get('HTTP_X_REAL_IP') or
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or
        request.META.get('REMOTE_ADDR')
    )
