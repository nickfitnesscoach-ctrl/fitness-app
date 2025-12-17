"""
billing/urls.py

Маршруты Billing API.

Цель:
- дать один "каноничный" набор URL (с / в конце там, где это принято)
- сохранить legacy URL без слэша и старые названия эндпоинтов
- убрать дубли и путаницу

Примечание:
- Все endpoint'ы остаются доступными, чтобы не ломать фронт/старые клиенты.
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

    # Legacy alias (старый путь). Оставляем, но он deprecated в views.
    path("plan", views.get_current_plan, name="current-plan"),

    # -----------------------------------------------------------------
    # Payment creation
    # -----------------------------------------------------------------
    # Каноничный путь
    path("create-payment/", views.create_payment, name="create-payment"),

    # Legacy alias (старый плюс-платёж)
    path("create-plus-payment/", views.create_plus_payment, name="create-plus-payment"),

    # Legacy endpoint subscribe (остается как wrapper)
    path("subscribe", views.subscribe, name="subscribe"),

    # -----------------------------------------------------------------
    # Card binding (привязка карты)
    # -----------------------------------------------------------------
    path("bind-card/start/", views.bind_card_start, name="bind-card-start"),

    # Admin-only тестовый live платеж на 1₽ (проверка prod webhook цепочки)
    path("create-test-live-payment/", views.create_test_live_payment, name="create-test-live-payment"),

    # -----------------------------------------------------------------
    # Auto-renew
    # -----------------------------------------------------------------
    # Новый API для настроек
    path("subscription/autorenew/", views.set_auto_renew, name="set-auto-renew"),

    # Legacy toggle
    path("auto-renew/toggle", views.toggle_auto_renew, name="toggle-auto-renew"),

    # -----------------------------------------------------------------
    # Settings screen endpoints (новые)
    # -----------------------------------------------------------------
    path("subscription/", views.get_subscription_details, name="subscription-details"),
    path("payment-method/", views.get_payment_method_details, name="payment-method-details"),

    # -----------------------------------------------------------------
    # Payments history
    # -----------------------------------------------------------------
    # Новый короткий список (limit)
    path("payments/", views.get_payments_history, name="payments-history"),

    # Legacy paginated history
    path("payments", views.get_payment_history, name="payment-history"),

    # -----------------------------------------------------------------
    # Webhooks
    # -----------------------------------------------------------------
    path("webhooks/yookassa", yookassa_webhook, name="yookassa-webhook"),
]
