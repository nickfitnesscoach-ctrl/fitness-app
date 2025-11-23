"""
Management command для обработки рекуррентных платежей.
Должен запускаться ежедневно через cron/scheduler.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.billing.models import Subscription, Payment, SubscriptionPlan
from apps.billing.services import YooKassaService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Обрабатывает рекуррентные платежи для подписок с автопродлением'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days-before',
            type=int,
            default=3,
            help='За сколько дней до окончания подписки создавать платёж (по умолчанию: 3)'
        )

    def handle(self, *args, **options):
        days_before = options['days_before']
        today = timezone.now()
        renewal_date = today + timedelta(days=days_before)

        self.stdout.write(f'\nПроверка подписок для автопродления...')
        self.stdout.write(f'Дата: {today.date()}')
        self.stdout.write(f'Подписки, истекающие до: {renewal_date.date()}\n')

        # Находим подписки, которые нужно продлить
        subscriptions_to_renew = Subscription.objects.filter(
            auto_renew=True,
            is_active=True,
            end_date__lte=renewal_date,
            end_date__gte=today,
            yookassa_payment_method_id__isnull=False,
        ).exclude(
            plan__name='FREE'
        )

        total_count = subscriptions_to_renew.count()
        success_count = 0
        failed_count = 0

        self.stdout.write(f'Найдено подписок для продления: {total_count}\n')

        for subscription in subscriptions_to_renew:
            try:
                # Проверяем, что нет pending платежей для этой подписки
                existing_payment = Payment.objects.filter(
                    subscription=subscription,
                    status__in=['PENDING', 'WAITING_FOR_CAPTURE'],
                    created_at__gte=today - timedelta(days=1)
                ).exists()

                if existing_payment:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠ У подписки {subscription.id} ({subscription.user.email}) '
                            f'уже есть активный платёж'
                        )
                    )
                    continue

                # Создаём рекуррентный платёж
                plan = subscription.plan

                self.stdout.write(
                    f'  → Создание платежа для {subscription.user.email} '
                    f'(план: {plan.display_name}, {plan.price}₽)'
                )

                # Создаём платёж в YooKassa
                yookassa_service = YooKassaService()
                yookassa_payment = yookassa_service.create_recurring_payment(
                    amount=plan.price,
                    description=f'Автопродление подписки {plan.display_name}',
                    payment_method_id=subscription.yookassa_payment_method_id,
                    metadata={
                        'subscription_id': str(subscription.id),
                        'user_id': str(subscription.user.id),
                        'plan_name': plan.name,
                        'recurring': True,
                    }
                )

                # Создаём запись платежа в БД
                payment = Payment.objects.create(
                    user=subscription.user,
                    subscription=subscription,
                    plan=plan,
                    amount=plan.price,
                    currency='RUB',
                    status='PENDING',
                    provider='YOOKASSA',
                    yookassa_payment_id=yookassa_payment['id'],
                    yookassa_payment_method_id=subscription.yookassa_payment_method_id,
                    is_recurring=True,
                    save_payment_method=True,
                    description=f'Автопродление подписки {plan.display_name}',
                )

                success_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Платёж создан: {payment.id} (YooKassa: {yookassa_payment["id"]})'
                    )
                )

            except Exception as e:
                failed_count += 1
                logger.error(
                    f'Error creating recurring payment for subscription {subscription.id}: {str(e)}',
                    exc_info=True
                )
                self.stdout.write(
                    self.style.ERROR(
                        f'  ✗ Ошибка для подписки {subscription.id}: {str(e)}'
                    )
                )

        # Итоги
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'✓ Успешно создано платежей: {success_count}'))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f'✗ Ошибок: {failed_count}'))
        self.stdout.write('=' * 60 + '\n')
