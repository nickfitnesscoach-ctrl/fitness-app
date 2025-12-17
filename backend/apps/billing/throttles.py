"""
billing/throttles.py

Throttle (rate limiting) для чувствительных endpoints биллинга.

Зачем это нужно:
- защита от спама и DoS
- ограничение злоупотреблений "создать платёж" (можно устроить нагрузку/мусор в БД)
- защита webhook endpoint от флудинга

Как это работает в DRF:
- throttle смотрит "ключ" (user или IP)
- считает запросы за окно времени
- если превышено — возвращает 429 Too Many Requests

ВАЖНО:
- Webhook должен быть доступен YooKassa, но не должен быть "дырой"
- Для webhook мы лимитим по IP
- Для create-payment лучше лимитить по user (если авторизован), иначе по IP
"""

from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class WebhookThrottle(SimpleRateThrottle):
    """
    Throttle для webhook endpoint.

    Ключ: IP адрес.
    Rate можно переопределить в settings.py в REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].

    По умолчанию: 100/hour
    """
    scope = "billing_webhook"
    rate = "100/hour"

    def get_cache_key(self, request, view):
        # Берём IP из DRF механизма (учитывает прокси при корректной настройке)
        ident = self.get_ident(request)
        if not ident:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}


class PaymentCreationThrottle(SimpleRateThrottle):
    """
    Throttle для endpoint создания платежа.

    Логика ключа:
    - если пользователь авторизован → лимит по user_id (честнее)
    - иначе → лимит по IP

    По умолчанию: 20/hour
    """
    scope = "billing_create_payment"
    rate = "20/hour"

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            ident = f"user:{user.id}"
        else:
            ident = self.get_ident(request)

        if not ident:
            return None

        return self.cache_format % {"scope": self.scope, "ident": ident}
