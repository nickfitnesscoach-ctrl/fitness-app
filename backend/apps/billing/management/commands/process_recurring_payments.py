"""
Management command: обработка рекуррентных платежей (автопродление подписок).

Запускать по расписанию (cron / systemd timer), например 1 раз в день.

Цель команды:
- найти подписки, у которых включено автопродление и срок скоро закончится;
- создать рекуррентный платеж в YooKassa по сохранённому payment_method_id;
- создать локальную запись Payment (PENDING);
- дальше финальная активация/продление подписки происходит через webhook (payment.succeeded).

ВАЖНО:
- команда НЕ продлевает подписку сама.
- команда только создаёт платеж и ждёт webhook.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from decimal import Decimal
import logging
from typing import Any, Dict
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
import requests

from apps.billing.models import Payment, Subscription

logger = logging.getLogger(__name__)


YOOKASSA_API_URL = "https://api.yookassa.ru/v3"


class Command(BaseCommand):
    help = "Создаёт рекуррентные платежи для подписок с автопродлением (оплата — через webhook)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-before",
            type=int,
            default=3,
            help="За сколько дней до окончания подписки создавать рекуррентный платеж (по умолчанию: 3).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что будет сделано, не создавая платежи.",
        )

    def handle(self, *args, **options):
        days_before: int = options["days_before"]
        dry_run: bool = options["dry_run"]

        now = timezone.now()
        renewal_deadline = now + timedelta(days=days_before)

        self.stdout.write("")
        self.stdout.write("Проверка подписок для автопродления")
        self.stdout.write(f"Сейчас: {now.isoformat()}")
        self.stdout.write(f"Создаём платежи для подписок, истекающих до: {renewal_deadline.date()}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: платежи создаваться не будут"))
        self.stdout.write("")

        # Базовая валидация конфигурации YooKassa (fail-fast)
        shop_id = getattr(settings, "YOOKASSA_SHOP_ID", None)
        secret_key = getattr(settings, "YOOKASSA_SECRET_KEY", None)

        if not shop_id or not secret_key:
            raise RuntimeError("YOOKASSA_SHOP_ID/YOOKASSA_SECRET_KEY не настроены в settings/env")

        # Ищем подписки на продление:
        # - auto_renew=True
        # - подписка активна
        # - заканчивается скоро (до renewal_deadline)
        # - не истекла прямо сейчас (end_date >= now)
        # - есть сохранённый payment_method_id
        # - план не FREE
        qs = (
            Subscription.objects.select_related("user", "plan")
            .filter(
                auto_renew=True,
                is_active=True,
                end_date__lte=renewal_deadline,
                end_date__gte=now,
                yookassa_payment_method_id__isnull=False,
            )
            .exclude(plan__code="FREE")
            .order_by("end_date")
        )

        total = qs.count()
        self.stdout.write(f"Найдено подписок для продления: {total}")
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Нечего продлевать."))
            return

        created_ok = 0
        skipped = 0
        failed = 0

        for sub in qs:
            try:
                # Лочим конкретную подписку, чтобы параллельный запуск команды не создал дубль.
                with transaction.atomic():
                    locked_sub = (
                        Subscription.objects.select_for_update()
                        .select_related("user", "plan")
                        .get(id=sub.id)
                    )

                    plan = locked_sub.plan

                    # Safety: план должен быть платным
                    if plan.price is None or Decimal(plan.price) <= Decimal("0"):
                        skipped += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"⚠ Пропуск: подписка {locked_sub.id} ({locked_sub.user.email}) — план неплатный/некорректный."
                            )
                        )
                        continue

                    # Анти-дубль: если есть активный pending платеж за последние 24 часа — не создаём новый.
                    day_ago = now - timedelta(hours=24)
                    has_pending = Payment.objects.filter(
                        subscription=locked_sub,
                        is_recurring=True,
                        status__in=["PENDING", "WAITING_FOR_CAPTURE"],
                        created_at__gte=day_ago,
                    ).exists()

                    if has_pending:
                        skipped += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"⚠ Пропуск: у подписки {locked_sub.id} ({locked_sub.user.email}) уже есть pending платёж за последние 24ч."
                            )
                        )
                        continue

                    # Создаём локальную запись платежа заранее.
                    # Это важно: мы получаем "стабильный" Idempotence-Key, чтобы повторный запуск команды
                    # не создавал новый платёж в YooKassa.
                    idempotence_key = str(uuid.uuid4())

                    payment = Payment.objects.create(
                        user=locked_sub.user,
                        subscription=locked_sub,
                        plan=plan,
                        amount=plan.price,
                        currency="RUB",
                        status="PENDING",
                        provider="YOOKASSA",
                        is_recurring=True,
                        save_payment_method=True,
                        yookassa_payment_method_id=locked_sub.yookassa_payment_method_id,
                        description=f"Автопродление подписки {plan.display_name}",
                        metadata={
                            "kind": "recurring_autorenew",
                            "subscription_id": str(locked_sub.id),
                            "plan_code": plan.code,
                            "idempotence_key": idempotence_key,
                            "created_by": "management_command:process_recurring_payments",
                            "created_at": now.isoformat(),
                        },
                    )

                    self.stdout.write(
                        f"→ {locked_sub.user.email}: создаём рекуррентный платёж "
                        f"(подписка {locked_sub.id}, план {plan.display_name}, {plan.price}₽)"
                    )

                    if dry_run:
                        # В DRY RUN мы ничего не отправляем в YooKassa.
                        skipped += 1
                        payment.status = "CANCELED"
                        payment.error_message = "DRY RUN: платеж не отправлялся в YooKassa"
                        payment.save(update_fields=["status", "error_message", "updated_at"])
                        self.stdout.write(self.style.WARNING("  [DRY RUN] пропуск отправки в YooKassa"))
                        continue

                    # Создаём рекуррентный платёж в YooKassa (прямой запрос).
                    yk_response = self._create_recurring_payment_yookassa(
                        shop_id=shop_id,
                        secret_key=secret_key,
                        idempotence_key=idempotence_key,
                        amount=Decimal(plan.price),
                        description=f"Автопродление {plan.display_name}",
                        payment_method_id=locked_sub.yookassa_payment_method_id,
                        metadata={
                            "payment_id": str(payment.id),           # локальный Payment UUID
                            "subscription_id": str(locked_sub.id),
                            "user_id": str(locked_sub.user_id),
                            "plan_code": plan.code,
                            "recurring": True,
                        },
                    )

                    # Сохраняем yookassa_payment_id в наш Payment
                    yk_payment_id = yk_response.get("id")
                    payment.yookassa_payment_id = yk_payment_id
                    payment.metadata["yookassa_raw_response"] = self._safe_response_for_storage(yk_response)
                    payment.save(update_fields=["yookassa_payment_id", "metadata", "updated_at"])

                    created_ok += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✓ Платёж создан: {payment.id} (YooKassa: {yk_payment_id})")
                    )

            except Exception as e:
                failed += 1
                logger.error(
                    f"Recurring payment error for subscription {sub.id}: {e}",
                    exc_info=True,
                )
                self.stdout.write(
                    self.style.ERROR(f"✗ Ошибка для подписки {sub.id} ({sub.user.email}): {str(e)}")
                )

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(f"✓ Успешно создано платежей: {created_ok}"))
        self.stdout.write(self.style.WARNING(f"⚠ Пропущено: {skipped}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"✗ Ошибок: {failed}"))
        self.stdout.write("=" * 70)
        self.stdout.write("")

    @staticmethod
    def _create_recurring_payment_yookassa(
        *,
        shop_id: str,
        secret_key: str,
        idempotence_key: str,
        amount: Decimal,
        description: str,
        payment_method_id: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Создание рекуррентного платежа в YooKassa через requests.

        Мы НЕ используем SDK, чтобы:
        - избегать глобального состояния Configuration.*
        - иметь полный контроль над запросом/ответом
        """
        url = f"{YOOKASSA_API_URL}/payments"

        credentials = f"{shop_id}:{secret_key}"
        auth_header = "Basic " + base64.b64encode(credentials.encode()).decode()

        payload = {
            "amount": {"value": str(amount), "currency": "RUB"},
            "capture": True,
            "payment_method_id": payment_method_id,
            "description": description,
            "metadata": metadata,
        }

        headers = {
            "Authorization": auth_header,
            "Idempotence-Key": idempotence_key,
            "Content-Type": "application/json",
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code not in (200, 201):
            # Не тащим весь resp.text наружу “вечно”, но в ошибку — можно.
            raise RuntimeError(f"YooKassa API error: {resp.status_code} - {resp.text}")

        return resp.json()

    @staticmethod
    def _safe_response_for_storage(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Безопасно сохраняем ответ YooKassa в metadata.
        Стараемся не хранить лишнее и не раздувать JSON.

        Если хочешь — можно ещё сильнее урезать (оставить только id/status/paid).
        """
        allowed_keys = {
            "id",
            "status",
            "paid",
            "created_at",
            "amount",
            "income_amount",
            "payment_method",
            "metadata",
        }
        return {k: v for k, v in data.items() if k in allowed_keys}
