"""
Management command: очистка/обслуживание истёкших подписок.

Задачи команды:
1) Найти подписки (НЕ FREE), которые истекли (end_date < now).
2) Если подписка истекла:
   - переводим пользователя на FREE план
   - отключаем auto_renew (чтобы не было “залипшего” флага)
   - сбрасываем card info по желанию (по умолчанию НЕ трогаем payment_method,
     т.к. пользователь может захотеть снова включить автопродление без повторной привязки)
3) НЕ трогаем FREE подписки.
4) Работает безопасно для продакшна:
   - транзакции
   - блокировка строки подписки (select_for_update)
   - батчами (чтобы не держать транзакцию слишком долго)
   - dry-run режим

ВАЖНО:
- Команда НЕ отменяет платежи.
- Команда НЕ делает возвраты.
- Команда НЕ создаёт новые подписки — только приводит состояние подписки к “норме”.
"""

from __future__ import annotations

import logging
from typing import Iterable

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Subscription, SubscriptionPlan

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Переводит истёкшие платные подписки в FREE и отключает автопродление."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Размер батча (сколько подписок обрабатывать за одну транзакцию). По умолчанию: 200.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что будет сделано, без изменений в базе.",
        )
        parser.add_argument(
            "--reset-card",
            action="store_true",
            help=(
                "Сбросить сохранённую карту (payment_method_id/mask/brand) у истёкших подписок. "
                "По умолчанию карта НЕ сбрасывается."
            ),
        )

    def handle(self, *args, **options):
        batch_size: int = options["batch_size"]
        dry_run: bool = options["dry_run"]
        reset_card: bool = options["reset_card"]

        now = timezone.now()

        self.stdout.write("")
        self.stdout.write("Очистка истёкших подписок")
        self.stdout.write(f"Сейчас: {now.isoformat()}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: изменения в базе выполняться не будут"))
        if reset_card:
            self.stdout.write(self.style.WARNING("RESET_CARD: данные карты будут сброшены у истёкших подписок"))
        self.stdout.write("")

        # FREE план — всегда берём по code (name legacy может быть NULL)
        free_plan = self._get_free_plan()

        # Ищем только НЕ FREE подписки, которые истекли.
        # Важно: фильтруем по plan__code, чтобы не зависеть от legacy 'name'.
        expired_qs = (
            Subscription.objects.select_related("user", "plan")
            .filter(is_active=True, end_date__lt=now)
            .exclude(plan__code="FREE")
            .order_by("end_date")
        )

        total = expired_qs.count()
        self.stdout.write(f"Найдено истёкших подписок (не FREE): {total}")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Нечего чистить."))
            return

        processed = 0
        updated = 0
        skipped = 0
        failed = 0

        # Обрабатываем батчами: меньше рисков блокировок и долгих транзакций
        ids = list(expired_qs.values_list("id", flat=True))
        for batch_ids in self._chunks(ids, batch_size):
            try:
                with transaction.atomic():
                    # Лочим строки подписок, чтобы параллельные процессы не спорили за одно и то же
                    subs = (
                        Subscription.objects.select_for_update()
                        .select_related("user", "plan")
                        .filter(id__in=batch_ids)
                    )

                    for sub in subs:
                        processed += 1

                        # Двойная проверка “на всякий случай” внутри лока:
                        # вдруг subscription уже кто-то обновил
                        if sub.plan.code == "FREE":
                            skipped += 1
                            continue
                        if not sub.is_active:
                            skipped += 1
                            continue
                        if not sub.is_expired():
                            skipped += 1
                            continue

                        # В dry-run мы только показываем, что бы сделали
                        if dry_run:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"[DRY RUN] {sub.user.email}: {sub.plan.code} истекла {sub.end_date.isoformat()} → FREE"
                                )
                            )
                            updated += 1
                            continue

                        # Переводим в FREE.
                        # Важный момент:
                        # - start_date/end_date для FREE в твоей текущей модели обязательны,
                        #   поэтому задаём “здоровые” значения:
                        #   start_date = now, end_date = now (FREE логикой определяется отдельно).
                        sub.plan = free_plan
                        sub.auto_renew = False  # истёкшая подписка не должна оставаться “на автопродлении”
                        sub.is_active = True    # FREE считаем активной

                        sub.start_date = now
                        sub.end_date = now

                        # Опционально сбрасываем карту (иногда нужно по требованиям бизнеса)
                        if reset_card:
                            sub.yookassa_payment_method_id = None
                            sub.card_mask = None
                            sub.card_brand = None

                        sub.save()

                        updated += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ {sub.user.email}: {sub.plan.code} истекла → переведён в FREE"
                            )
                        )

            except Exception as e:
                failed += len(batch_ids)
                logger.error(f"Cleanup batch failed (size={len(batch_ids)}): {e}", exc_info=True)
                self.stdout.write(self.style.ERROR(f"✗ Ошибка батча ({len(batch_ids)} подписок): {str(e)}"))

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(f"✓ Обработано: {processed}"))
        self.stdout.write(self.style.SUCCESS(f"✓ Обновлено: {updated}"))
        self.stdout.write(self.style.WARNING(f"⚠ Пропущено: {skipped}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"✗ Ошибок (примерно): {failed}"))
        self.stdout.write("=" * 70)
        self.stdout.write("")

    @staticmethod
    def _chunks(items: list, size: int) -> Iterable[list]:
        """Разбивает список на чанки фиксированного размера."""
        for i in range(0, len(items), size):
            yield items[i : i + size]

    @staticmethod
    def _get_free_plan() -> SubscriptionPlan:
        """
        Получаем FREE план максимально надёжно:
        1) по code='FREE'
        2) fallback на legacy name='FREE' (на случай старой базы)
        """
        try:
            return SubscriptionPlan.objects.get(code="FREE", is_active=True)
        except SubscriptionPlan.DoesNotExist:
            try:
                return SubscriptionPlan.objects.get(name="FREE", is_active=True)
            except SubscriptionPlan.DoesNotExist:
                raise RuntimeError(
                    "FREE plan не найден в базе. Создай план в админке: code=FREE, price=0."
                )
