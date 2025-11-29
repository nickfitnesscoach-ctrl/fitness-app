"""
Custom exceptions for AI Proxy client.
"""


class AIProxyError(Exception):
    """Base exception for AI Proxy errors."""
    pass


class AIProxyAuthenticationError(AIProxyError):
    """Raised when API key is invalid or missing (401)."""
    pass


class AIProxyServerError(AIProxyError):
    """Raised when AI service returns 500 error."""
    pass


class AIProxyTimeoutError(AIProxyError):
    """Raised when request times out."""
    pass


class AIProxyValidationError(AIProxyError):
    """Raised when request validation fails (422)."""
    pass
