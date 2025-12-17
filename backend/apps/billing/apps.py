"""
billing/apps.py

AppConfig для billing приложения.

Зачем нужен:
- корректное имя приложения
- человекочитаемое verbose_name в админке
- место для будущих "подключений" (например: сигналов или системных проверок)

ВАЖНО:
- Сигналы у нас уже объявлены в models.py через @receiver, поэтому
  здесь НЕ нужно импортировать models ради сигналов.
- Не добавляем лишних side-effect import'ов в ready(), чтобы не было двойной загрузки.
"""

from __future__ import annotations

from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.billing"
    verbose_name = "Billing / Подписки и платежи"
