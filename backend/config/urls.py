"""
URL configuration for FoodMind AI project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth.decorators import user_passes_test
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.common.views import health_check, readiness_check, liveness_check
import base64


def basic_auth_required(view_func):
    """
    Decorator for basic HTTP authentication.
    Login: admin
    Password: 2865
    """
    def check_basic_auth(request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if auth_header.startswith('Basic '):
            try:
                # Decode base64 credentials
                credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
                username, password = credentials.split(':', 1)

                # Check credentials
                if username == 'admin' and password == '2865':
                    return True
            except Exception:
                pass

        return False

    def wrapped_view(request, *args, **kwargs):
        if check_basic_auth(request):
            return view_func(request, *args, **kwargs)

        # Return 401 with WWW-Authenticate header
        from django.http import HttpResponse
        response = HttpResponse('Unauthorized', status=401)
        response['WWW-Authenticate'] = 'Basic realm="FoodMind API Documentation"'
        return response

    return wrapped_view

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Health checks (for monitoring and Kubernetes probes)
    path("health/", health_check, name="health"),
    path("ready/", readiness_check, name="readiness"),
    path("live/", liveness_check, name="liveness"),

    # API v1 endpoints
    path("api/v1/users/", include("apps.users.urls")),
    path("api/v1/", include("apps.nutrition.urls")),  # meals/ and nutrition/goals/
    path("api/v1/billing/", include("apps.billing.urls")),
    path("api/v1/ai/", include("apps.ai.urls")),
    path("api/v1/telegram/", include("apps.telegram.urls")),

    # API Schema and Documentation (protected with Basic Auth)
    path("api/schema/", basic_auth_required(SpectacularAPIView.as_view()), name="schema"),
    path("api/schema/swagger-ui/", basic_auth_required(SpectacularSwaggerView.as_view(url_name="schema")), name="swagger-ui"),
    path("api/schema/redoc/", basic_auth_required(SpectacularRedocView.as_view(url_name="schema")), name="redoc"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
