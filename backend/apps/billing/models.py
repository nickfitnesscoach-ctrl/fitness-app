"""
Модели для управления тарифами, подписками и платежами.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from datetime import timedelta, datetime
import uuid


class SubscriptionPlan(models.Model):
    """
    Тарифный план подписки.
    Администраторы могут создавать и редактировать планы через Django Admin.
    """
    PLAN_CHOICES = [
        ('FREE', 'Бесплатный'),
        ('PRO_MONTHLY', 'PRO месячный'),
        ('PRO_YEARLY', 'PRO годовой'),
        ('MONTHLY', 'Месячный (legacy)'),  # Deprecated, use PRO_MONTHLY
        ('YEARLY', 'Годовой (legacy)'),    # Deprecated, use PRO_YEARLY
    ]

    # System code for programmatic access (unique identifier)
    code = models.CharField(
        'Системный код',
        max_length=50,
        unique=True,
        help_text='Уникальный код для API (например: FREE, PRO_MONTHLY, PRO_YEARLY)'
    )

    # Legacy name field - deprecated, use 'code' instead
    name = models.CharField(
        'Название плана (legacy)',
        max_length=50,
        choices=PLAN_CHOICES,
        unique=True,
        blank=True,
        null=True,
        help_text='DEPRECATED: используйте поле code'
    )
    display_name = models.CharField('Отображаемое название', max_length=100)
    description = models.TextField('Описание', blank=True)

    # Pricing
    price = models.DecimalField('Цена (₽)', max_digits=10, decimal_places=2, default=0)
    duration_days = models.IntegerField('Длительность (дней)', default=0)

    # Features
    daily_photo_limit = models.IntegerField(
        'Лимит фото в день',
        null=True,
        blank=True,
        help_text='Максимум фото в день. Null = безлимит'
    )
    # Legacy field - deprecated, use daily_photo_limit
    max_photos_per_day = models.IntegerField(
        'Макс. фото в день (legacy)',
        default=3,
        help_text='DEPRECATED: используйте daily_photo_limit. -1 = неограниченно'
    )
    history_days = models.IntegerField(
        'Хранение истории (дней)',
        default=7,
        help_text='-1 = неограниченно'
    )
    ai_recognition = models.BooleanField('AI распознавание', default=True)
    advanced_stats = models.BooleanField('Расширенная статистика', default=False)
    priority_support = models.BooleanField('Приоритетная поддержка', default=False)

    # Metadata
    is_active = models.BooleanField('Активен', default=True)
    is_test = models.BooleanField(
        'Тестовый план',
        default=False,
        help_text='Тестовый план для проверки live-платежей (только для владельца/админов)'
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        db_table = 'subscription_plans'
        verbose_name = 'Тарифный план'
        verbose_name_plural = 'Тарифные планы'
        ordering = ['price']

    def __str__(self):
        return f"{self.display_name} - {self.price}₽"

    def get_features_dict(self):
        """Возвращает словарь с features для API response."""
        return {
            'daily_photo_limit': self.daily_photo_limit,
            'max_photos_per_day': self.max_photos_per_day,  # legacy
            'history_days': self.history_days,
            'ai_recognition': self.ai_recognition,
            'advanced_stats': self.advanced_stats,
            'priority_support': self.priority_support,
        }


class Subscription(models.Model):
    """
    Подписка пользователя на тарифный план.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name='Пользователь'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name='Тарифный план'
    )

    # Dates
    start_date = models.DateTimeField('Дата начала')
    end_date = models.DateTimeField('Дата окончания')

    # Status
    is_active = models.BooleanField('Активна', default=True)
    auto_renew = models.BooleanField('Автопродление', default=False)

    # Payment method (для рекуррентных платежей)
    yookassa_payment_method_id = models.CharField(
        'ID способа оплаты ЮKassa',
        max_length=255,
        blank=True,
        null=True,
        help_text='Сохранённый способ оплаты для рекуррентных платежей'
    )
    card_mask = models.CharField(
        'Маска карты',
        max_length=20,
        blank=True,
        null=True,
        help_text='Последние 4 цифры карты, например "•••• 1234"'
    )
    card_brand = models.CharField(
        'Тип карты',
        max_length=50,
        blank=True,
        null=True,
        help_text='Тип платёжной карты: Visa, MasterCard, МИР и т.д.'
    )

    # Metadata
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        db_table = 'subscriptions'
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'end_date']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.plan.display_name}"

    @property
    def days_remaining(self):
        """Вычисляет оставшиеся дни подписки."""
        if self.plan.code == 'FREE':
            return None

        if not self.is_active:
            return 0

        now = timezone.now()
        if self.end_date <= now:
            return 0

        delta = self.end_date - now
        return delta.days

    def is_expired(self):
        """Проверяет, истекла ли подписка."""
        if self.plan.code == 'FREE':
            return False
        return timezone.now() >= self.end_date

    def extend_subscription(self, days):
        """
        Продлевает подписку на указанное количество дней.
        Если подписка истекла, продлевает от текущего момента.
        Если активна, добавляет к текущей дате окончания.
        """
        from django.db import transaction

        with transaction.atomic():
            now = timezone.now()

            if self.is_expired():
                # Подписка истекла - начинаем с текущего момента
                self.start_date = now
                self.end_date = now + timedelta(days=days)
            else:
                # Подписка активна - добавляем к существующей
                self.end_date += timedelta(days=days)

            self.is_active = True
            self.save()


class Payment(models.Model):
    """
    Платёж пользователя.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Ожидание оплаты'),
        ('WAITING_FOR_CAPTURE', 'Ожидание подтверждения'),
        ('SUCCEEDED', 'Успешно'),
        ('CANCELED', 'Отменён'),
        ('FAILED', 'Ошибка'),
        ('REFUNDED', 'Возврат'),
    ]

    PROVIDER_CHOICES = [
        ('YOOKASSA', 'ЮKassa'),
    ]

    # IDs
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relations
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Пользователь'
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        related_name='payments',
        verbose_name='Подписка',
        null=True,
        blank=True
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        related_name='payments',
        verbose_name='Тарифный план',
        null=True,
        blank=True
    )

    # Payment details
    amount = models.DecimalField('Сумма', max_digits=10, decimal_places=2)
    currency = models.CharField('Валюта', max_length=3, default='RUB')
    status = models.CharField(
        'Статус',
        max_length=50,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    # Provider info
    provider = models.CharField(
        'Платёжный провайдер',
        max_length=50,
        choices=PROVIDER_CHOICES,
        default='YOOKASSA'
    )
    yookassa_payment_id = models.CharField(
        'ID платежа ЮKassa',
        max_length=255,
        unique=True,
        null=True,
        blank=True
    )
    yookassa_payment_method_id = models.CharField(
        'ID способа оплаты ЮKassa',
        max_length=255,
        null=True,
        blank=True,
        help_text='Для сохранения способа оплаты'
    )

    # Payment metadata
    is_recurring = models.BooleanField('Рекуррентный платёж', default=False)
    save_payment_method = models.BooleanField('Сохранить способ оплаты', default=True)

    # Additional data
    description = models.TextField('Описание', blank=True)
    error_message = models.TextField('Сообщение об ошибке', blank=True)
    metadata = models.JSONField('Дополнительные данные', default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    paid_at = models.DateTimeField('Дата оплаты', null=True, blank=True)
    webhook_processed_at = models.DateTimeField(
        'Webhook обработан',
        null=True,
        blank=True,
        help_text='Время обработки webhook (для idempotency)'
    )

    class Meta:
        db_table = 'payments'
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['yookassa_payment_id']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.amount}₽ ({self.get_status_display()})"

    def mark_as_succeeded(self, payment_method_id=None):
        """Помечает платёж как успешный."""
        self.status = 'SUCCEEDED'
        self.paid_at = timezone.now()

        if payment_method_id and self.save_payment_method:
            self.yookassa_payment_method_id = payment_method_id

        self.save()

    def mark_as_failed(self, error_message=''):
        """Помечает платёж как неудачный."""
        self.status = 'FAILED'
        self.error_message = error_message
        self.save()

    def mark_as_canceled(self):
        """Помечает платёж как отменённый."""
        self.status = 'CANCELED'
        self.save()

    def mark_as_refunded(self):
        """Помечает платёж как возвращённый."""
        self.status = 'REFUNDED'
        self.save()


class Refund(models.Model):
    """
    Возврат средств.
    """
    STATUS_CHOICES = [
        ('PENDING', 'В обработке'),
        ('SUCCEEDED', 'Успешно'),
        ('CANCELED', 'Отменён'),
    ]

    # IDs
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relations
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='refunds',
        verbose_name='Платёж'
    )

    # Refund details
    amount = models.DecimalField('Сумма возврата', max_digits=10, decimal_places=2)
    status = models.CharField(
        'Статус',
        max_length=50,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    # YooKassa info
    yookassa_refund_id = models.CharField(
        'ID возврата ЮKassa',
        max_length=255,
        unique=True,
        null=True,
        blank=True
    )

    # Additional data
    reason = models.TextField('Причина', blank=True)
    error_message = models.TextField('Сообщение об ошибке', blank=True)

    # Timestamps
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    completed_at = models.DateTimeField('Дата завершения', null=True, blank=True)

    class Meta:
        db_table = 'refunds'
        verbose_name = 'Возврат'
        verbose_name_plural = 'Возвраты'
        ordering = ['-created_at']

    def __str__(self):
        return f"Возврат {self.amount}₽ для платежа {self.payment.id}"


class WebhookLog(models.Model):
    """
    Лог обработки webhook уведомлений.
    Используется для отладки и retry логики.
    """
    STATUS_CHOICES = [
        ('RECEIVED', 'Получен'),
        ('PROCESSING', 'Обработка'),
        ('SUCCESS', 'Успешно'),
        ('FAILED', 'Ошибка'),
        ('DUPLICATE', 'Дубликат'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Event info
    event_type = models.CharField('Тип события', max_length=100)
    event_id = models.CharField(
        'ID события YooKassa',
        max_length=255,
        db_index=True
    )
    payment_id = models.CharField(
        'ID платежа YooKassa',
        max_length=255,
        null=True,
        blank=True,
        db_index=True
    )
    
    # Processing info
    status = models.CharField(
        'Статус обработки',
        max_length=20,
        choices=STATUS_CHOICES,
        default='RECEIVED'
    )
    attempts = models.PositiveIntegerField('Попытки обработки', default=0)
    error_message = models.TextField('Сообщение об ошибке', blank=True)
    
    # Request data
    raw_payload = models.JSONField('Сырые данные webhook', default=dict)
    client_ip = models.GenericIPAddressField('IP клиента', null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField('Получен', auto_now_add=True)
    processed_at = models.DateTimeField('Обработан', null=True, blank=True)

    class Meta:
        db_table = 'webhook_logs'
        verbose_name = 'Лог webhook'
        verbose_name_plural = 'Логи webhook'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.status}) - {self.created_at}"


# Signals
@receiver(post_save, sender=User)
def create_free_subscription(sender, instance, created, **kwargs):
    """
    Automatically create FREE subscription when a new user is created.
    This ensures every user has a subscription from day one.
    """
    if created:
        try:
            from django.conf import settings
            free_plan = SubscriptionPlan.objects.get(name='FREE')
            Subscription.objects.create(
                user=instance,
                plan=free_plan,
                start_date=timezone.now(),
                end_date=settings.FREE_SUBSCRIPTION_END_DATE,
                is_active=True,
                auto_renew=False
            )
        except SubscriptionPlan.DoesNotExist:
            # If FREE plan doesn't exist, log warning but don't fail
            # Admins should create FREE plan via Django Admin
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"FREE subscription plan not found. User {instance.username} created without subscription.")
