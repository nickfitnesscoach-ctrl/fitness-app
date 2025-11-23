"""
URL configuration for users app.
"""

from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/refresh/', views.CustomTokenRefreshView.as_view(), name='refresh'),

    # Email verification endpoints
    path('auth/verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('auth/resend-verification/', views.ResendVerificationEmailView.as_view(), name='resend-verification'),

    # Profile endpoints
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('profile/delete/', views.DeleteAccountView.as_view(), name='delete-account'),
]
