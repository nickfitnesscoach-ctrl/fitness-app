"""
Billing webhooks module.

Публичный API модуля:
- yookassa_webhook — единственная точка входа для YooKassa

Все handlers и utils являются внутренней реализацией
и не предназначены для прямого импорта извне.
"""

from .views import yookassa_webhook

__all__ = [
    "yookassa_webhook",
]
