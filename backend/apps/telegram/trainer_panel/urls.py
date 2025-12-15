"""
URL configuration for Trainer Panel.
"""

from django.urls import path

from apps.telegram.auth.views import trainer_panel_auth

urlpatterns = [
    # Trainer panel authentication
    path('auth/', trainer_panel_auth, name='trainer-panel-auth'),
]
