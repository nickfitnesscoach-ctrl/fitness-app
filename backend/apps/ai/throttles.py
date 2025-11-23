"""
Custom throttling classes for AI recognition.
"""

from rest_framework.throttling import SimpleRateThrottle


class AIRecognitionPerMinuteThrottle(SimpleRateThrottle):
    """
    Throttle AI recognition requests per minute per IP.
    Limit: 10 requests per minute
    """
    scope = 'ai_per_minute'

    def get_cache_key(self, request, view):
        """Use IP address as cache key."""
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class AIRecognitionPerDayThrottle(SimpleRateThrottle):
    """
    Throttle AI recognition requests per day per IP.
    Limit: 100 requests per day
    """
    scope = 'ai_per_day'

    def get_cache_key(self, request, view):
        """Use IP address as cache key."""
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
