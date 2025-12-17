"""
billing/urls.py

Маршруты Billing API.

Все endpoint'ы с trailing slash (каноничный формат).
"""

from __future__ import annotations

from django.urls import path

from . import views
from .webhooks import yookassa_webhook

app_name = "billing"


urlpatterns = [
    # -----------------------------------------------------------------
    # Public
    # -----------------------------------------------------------------
    path("plans/", views.get_subscription_plans, name="subscription-plans"),

    # -----------------------------------------------------------------
    # Subscription status (основной "короткий" эндпоинт для UI)
    # -----------------------------------------------------------------
    path("me/", views.get_subscription_status, name="subscription-status"),

    # -----------------------------------------------------------------
    # Payment creation
    # -----------------------------------------------------------------
    path("create-payment/", views.create_payment, name="create-payment"),

    # -----------------------------------------------------------------
    # Card binding (привязка карты)
    # -----------------------------------------------------------------
    path("bind-card/start/", views.bind_card_start, name="bind-card-start"),

    # Admin-only тестовый live платеж на 1₽ (проверка prod webhook цепочки)
    path("create-test-live-payment/", views.create_test_live_payment, name="create-test-live-payment"),

    # -----------------------------------------------------------------
    # Auto-renew
    # -----------------------------------------------------------------
    path("subscription/autorenew/", views.set_auto_renew, name="set-auto-renew"),

    # -----------------------------------------------------------------
    # Settings screen endpoints
    # -----------------------------------------------------------------
    path("subscription/", views.get_subscription_details, name="subscription-details"),
    path("payment-method/", views.get_payment_method_details, name="payment-method-details"),

    # -----------------------------------------------------------------
    # Payments history
    # -----------------------------------------------------------------
    path("payments/", views.get_payments_history, name="payments-history"),

    # -----------------------------------------------------------------
    # Webhooks
    # -----------------------------------------------------------------
    path("webhooks/yookassa", yookassa_webhook, name="yookassa-webhook"),
]
