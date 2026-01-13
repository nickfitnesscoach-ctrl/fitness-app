"""
billing/models.py

Модели биллинга: тарифы, подписки, платежи, возвраты, лог webhook.

Важно:
- Мы НЕ ломаем существующую схему (поля сохранены)
- При этом наводим порядок в коде, комментариях и безопасности

SSOT:
- SubscriptionPlan.code — основной идентификатор тарифа
- SubscriptionPlan.name — legacy (оставлен ради обратной совместимости)

Поток денег:
- Payment создаётся при старте оплаты
- Payment становится SUCCEEDED только после webhook (webhooks/handlers.py)
- Подписка продлевается/активируется после SUCCEEDED webhook
"""

from __future__ import annotations

from datetime import timedelta
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

# ---------------------------------------------------------------------
# SubscriptionPlan
# ---------------------------------------------------------------------


class SubscriptionPlan(models.Model):
    """
    Тарифный план.

    Админ может управлять тарифами через Django Admin.
    Для кода используем поле `code` (уникально, SSOT).
    Поле `name` — legacy, оставлено для старых частей системы.
    """

    PLAN_CHOICES = [
        ("FREE", "Бесплатный"),
        ("PRO_MONTHLY", "PRO месячный"),
        ("PRO_YEARLY", "PRO годовой"),
        ("MONTHLY", "Месячный (legacy)"),
        ("YEARLY", "Годовой (legacy)"),
    ]

    code = models.CharField(
        "Системный код",
        max_length=50,
        unique=True,
        help_text="Уникальный код для API: FREE, PRO_MONTHLY, PRO_YEARLY и т.д.",
    )

    # Legacy поле (не использовать в новых вызовах)
    name = models.CharField(
        "Название плана (legacy)",
        max_length=50,
        choices=PLAN_CHOICES,
        unique=True,
        blank=True,
        null=True,
        help_text="DEPRECATED: используйте поле code",
    )

    display_name = models.CharField("Отображаемое название", max_length=100)
    description = models.TextField("Описание", blank=True)

    # Pricing
    price = models.DecimalField("Цена (₽)", max_digits=10, decimal_places=2, default=0)
    old_price = models.PositiveIntegerField(
        "Старая цена (₽)",
        null=True,
        blank=True,
        help_text="Якорная цена для отображения скидки (например: было 4990₽)",
    )
    duration_days = models.IntegerField("Длительность (дней)", default=0)

    # Features
    daily_photo_limit = models.IntegerField(
        "Лимит фото в день",
        null=True,
        blank=True,
        help_text="Null = безлимит",
    )

    # Legacy поле (оставлено)
    max_photos_per_day = models.IntegerField(
        "Макс. фото в день (legacy)",
        default=3,
        help_text="DEPRECATED: используйте daily_photo_limit. -1 = неограниченно",
    )

    history_days = models.IntegerField(
        "Хранение истории (дней)",
        default=7,
        help_text="-1 = неограниченно",
    )

    ai_recognition = models.BooleanField("AI распознавание", default=True)
    advanced_stats = models.BooleanField("Расширенная статистика", default=False)
    priority_support = models.BooleanField("Приоритетная поддержка", default=False)

    # Flags
    is_active = models.BooleanField("Активен", default=True)
    is_test = models.BooleanField(
        "Тестовый план",
        default=False,
        help_text="Тестовый план для проверки live-платежей (только для админов)",
    )

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        db_table = "subscription_plans"
        verbose_name = "Тарифный план"
        verbose_name_plural = "Тарифные планы"
        ordering = ["price"]

    def __str__(self) -> str:
        return f"{self.display_name} - {self.price}₽"

    def get_features_dict(self) -> dict:
        """Удобная форма features для API/UI."""
        return {
            "daily_photo_limit": self.daily_photo_limit,
            "max_photos_per_day": self.max_photos_per_day,  # legacy
            "history_days": self.history_days,
            "ai_recognition": self.ai_recognition,
            "advanced_stats": self.advanced_stats,
            "priority_support": self.priority_support,
        }


# ---------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------


class Subscription(models.Model):
    """
    Подписка пользователя.

    Важно:
    - Для FREE подписки мы считаем, что она "не истекает" логически
      (см. is_expired), но end_date всё равно хранится как поле.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
        verbose_name="Пользователь",
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name="Тарифный план",
    )

    start_date = models.DateTimeField("Дата начала")
    end_date = models.DateTimeField("Дата окончания")

    is_active = models.BooleanField("Активна", default=True)
    auto_renew = models.BooleanField("Автопродление", default=False)

    # Saved payment method for recurring payments
    yookassa_payment_method_id = models.CharField(
        "ID способа оплаты ЮKassa",
        max_length=255,
        blank=True,
        null=True,
        help_text="Сохранённый способ оплаты для рекуррентных платежей",
    )

    card_mask = models.CharField(
        "Маска карты",
        max_length=20,
        blank=True,
        null=True,
        help_text='Например: "•••• 1234"',
    )

    card_brand = models.CharField(
        "Тип карты",
        max_length=50,
        blank=True,
        null=True,
        help_text="Visa, MasterCard, МИР и т.д.",
    )

    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        db_table = "subscriptions"
        verbose_name = "Подписка"
        verbose_name_plural = "Подписки"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "end_date"]),
        ]

    def __str__(self) -> str:
        email = getattr(self.user, "email", None) or str(self.user_id)
        return f"{email} - {self.plan.display_name}"

    def is_expired(self) -> bool:
        """
        Истекла ли подписка?

        FREE по бизнес-логике НЕ истекает.
        """
        if self.plan and self.plan.code == "FREE":
            return False
        return timezone.now() >= self.end_date

    @property
    def days_remaining(self):
        """
        Сколько дней осталось.

        - FREE → None
        - inactive → 0
        - expired → 0
        """
        if self.plan and self.plan.code == "FREE":
            return None
        if not self.is_active:
            return 0
        if self.is_expired():
            return 0
        return max(0, (self.end_date - timezone.now()).days)

    def extend_subscription(self, days: int) -> None:
        """
        Продлевает подписку.

        - если истекла → продление от сейчас
        - если активна → добавляем дни к end_date

        Важно: это просто "утилита модели".
        Основная логика продления должна быть в services.activate_or_extend_subscription
        и вызываться из webhook обработчика.
        """
        if days <= 0:
            return

        now = timezone.now()

        if self.is_expired():
            self.start_date = now
            self.end_date = now + timedelta(days=days)
        else:
            self.end_date = self.end_date + timedelta(days=days)

        self.is_active = True
        self.save(update_fields=["start_date", "end_date", "is_active", "updated_at"])


# ---------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------


class Payment(models.Model):
    """
    Платёж пользователя.

    IMPORTANT:
    - Статус SUCCEEDED выставляется только после webhook от YooKassa
    - payment_method_id сохраняем только если save_payment_method=True
    """

    STATUS_CHOICES = [
        ("PENDING", "Ожидание оплаты"),
        ("WAITING_FOR_CAPTURE", "Ожидание подтверждения"),
        ("SUCCEEDED", "Успешно"),
        ("CANCELED", "Отменён"),
        ("FAILED", "Ошибка"),
        ("REFUNDED", "Возврат"),
    ]

    PROVIDER_CHOICES = [
        ("YOOKASSA", "ЮKassa"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Пользователь",
    )

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.SET_NULL,
        related_name="payments",
        verbose_name="Подписка",
        null=True,
        blank=True,
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        related_name="payments",
        verbose_name="Тарифный план",
        null=True,
        blank=True,
    )

    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    currency = models.CharField("Валюта", max_length=3, default="RUB")

    status = models.CharField("Статус", max_length=50, choices=STATUS_CHOICES, default="PENDING")

    provider = models.CharField(
        "Платёжный провайдер", max_length=50, choices=PROVIDER_CHOICES, default="YOOKASSA"
    )

    yookassa_payment_id = models.CharField(
        "ID платежа ЮKassa",
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )

    yookassa_payment_method_id = models.CharField(
        "ID способа оплаты ЮKassa",
        max_length=255,
        null=True,
        blank=True,
        help_text="Сохраняется при успешной оплате, если save_payment_method=True",
    )

    is_recurring = models.BooleanField("Рекуррентный платёж", default=False)
    save_payment_method = models.BooleanField("Сохранить способ оплаты", default=True)

    description = models.TextField("Описание", blank=True)
    error_message = models.TextField("Сообщение об ошибке", blank=True)
    metadata = models.JSONField("Дополнительные данные", default=dict, blank=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)
    paid_at = models.DateTimeField("Дата оплаты", null=True, blank=True)

    # Для DB guard рекуррентных платежей
    billing_period_end = models.DateTimeField(
        "Окончание периода оплаты",
        null=True,
        blank=True,
        db_index=True,
        help_text="Для recurring: end_date подписки на момент создания платежа. Используется для DB guard.",
    )

    webhook_processed_at = models.DateTimeField(
        "Webhook обработан",
        null=True,
        blank=True,
        help_text="Для идемпотентности: если webhook повторится — мы видим, что уже обработали",
    )

    class Meta:
        db_table = "payments"
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["yookassa_payment_id"]),
            # DB guard для recurring: предотвращает двойное списание за один период
            models.Index(fields=["subscription", "billing_period_end", "status"]),
        ]

    def __str__(self) -> str:
        email = getattr(self.user, "email", None) or str(self.user_id)
        return f"{email} - {self.amount}₽ ({self.status})"

    def mark_as_succeeded(self, payment_method_id: str | None = None) -> None:
        """Помечает платёж как успешный."""
        self.status = "SUCCEEDED"
        self.paid_at = timezone.now()
        if payment_method_id and self.save_payment_method:
            self.yookassa_payment_method_id = payment_method_id
        self.save(update_fields=["status", "paid_at", "yookassa_payment_method_id", "updated_at"])

    def mark_as_failed(self, error_message: str = "") -> None:
        """Помечает платёж как FAILED."""
        self.status = "FAILED"
        self.error_message = error_message
        self.save(update_fields=["status", "error_message", "updated_at"])

    def mark_as_canceled(self) -> None:
        """Помечает платёж как CANCELED."""
        self.status = "CANCELED"
        self.save(update_fields=["status", "updated_at"])

    def mark_as_refunded(self) -> None:
        """Помечает платёж как REFUNDED."""
        self.status = "REFUNDED"
        self.save(update_fields=["status", "updated_at"])


# ---------------------------------------------------------------------
# Refund
# ---------------------------------------------------------------------


class Refund(models.Model):
    """Возврат средств по платежу."""

    STATUS_CHOICES = [
        ("PENDING", "В обработке"),
        ("SUCCEEDED", "Успешно"),
        ("CANCELED", "Отменён"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="refunds",
        verbose_name="Платёж",
    )

    amount = models.DecimalField("Сумма возврата", max_digits=10, decimal_places=2)
    status = models.CharField("Статус", max_length=50, choices=STATUS_CHOICES, default="PENDING")

    yookassa_refund_id = models.CharField(
        "ID возврата ЮKassa",
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )

    reason = models.TextField("Причина", blank=True)
    error_message = models.TextField("Сообщение об ошибке", blank=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)
    completed_at = models.DateTimeField("Дата завершения", null=True, blank=True)

    class Meta:
        db_table = "refunds"
        verbose_name = "Возврат"
        verbose_name_plural = "Возвраты"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Refund {self.amount}₽ for payment {self.payment_id}"


# ---------------------------------------------------------------------
# WebhookLog
# ---------------------------------------------------------------------


class WebhookLog(models.Model):
    """
    Лог входящих webhook.

    Зачем:
    - дебаг
    - идемпотентность/защита от дублей
    - основа для retry (если захочешь)

    Поля идемпотентности:
    - event_id: computed key (event_type:obj_id:obj_status) или provider_event_id
    - provider_event_id: оригинальный ID от YooKassa (если присутствует)

    Observability:
    - trace_id: уникальный ID запроса для корреляции логов
    """

    STATUS_CHOICES = [
        ("RECEIVED", "Получен"),
        ("QUEUED", "В очереди"),
        ("PROCESSING", "Обработка"),
        ("SUCCESS", "Успешно"),
        ("FAILED", "Ошибка"),
        ("DUPLICATE", "Дубликат"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    event_type = models.CharField("Тип события", max_length=100)
    event_id = models.CharField(
        "Idempotency key",
        max_length=255,
        unique=True,  # Гарантирует идемпотентность на уровне БД
        help_text="Уникальный ключ: provider_event_id или computed event_type:obj_id:obj_status",
    )

    # YooKassa native event ID (если присутствует в payload)
    provider_event_id = models.CharField(
        "ID события от провайдера",
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Оригинальный event ID от YooKassa (uuid или id поле)",
    )

    payment_id = models.CharField(
        "ID платежа YooKassa",
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
    )

    # Observability
    trace_id = models.CharField(
        "Trace ID",
        max_length=36,
        null=True,
        blank=True,
        db_index=True,
        help_text="Уникальный ID запроса для корреляции логов",
    )

    status = models.CharField(
        "Статус обработки", max_length=20, choices=STATUS_CHOICES, default="RECEIVED"
    )
    attempts = models.PositiveIntegerField("Попытки обработки", default=0)
    error_message = models.TextField("Сообщение об ошибке", blank=True)

    raw_payload = models.JSONField("Сырые данные webhook", default=dict)
    client_ip = models.GenericIPAddressField("IP клиента", null=True, blank=True)

    created_at = models.DateTimeField("Получен", auto_now_add=True)
    processed_at = models.DateTimeField("Обработан", null=True, blank=True)

    class Meta:
        db_table = "webhook_logs"
        verbose_name = "Лог webhook"
        verbose_name_plural = "Логи webhook"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["trace_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} ({self.status})"


# ---------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------


@receiver(post_save, sender=User)
def create_free_subscription(sender, instance: User, created: bool, **kwargs):
    """
    Автоматически создаём FREE подписку при создании нового пользователя.

    Почему это нужно:
    - чтобы все части системы могли предполагать, что subscription существует
    - чтобы не ловить Subscription.DoesNotExist в проде

    Важно:
    - если FREE план не создан в админке — мы не падаем, а логируем предупреждение
    """
    if not created:
        return

    import logging

    log = logging.getLogger(__name__)

    try:
        try:
            free_plan = SubscriptionPlan.objects.get(code="FREE", is_active=True)
        except SubscriptionPlan.DoesNotExist:
            free_plan = SubscriptionPlan.objects.get(name="FREE", is_active=True)

        # end_date берём из settings, если задано, иначе — 10 лет "вперёд"
        end_date = getattr(settings, "FREE_SUBSCRIPTION_END_DATE", None) or (
            timezone.now() + timedelta(days=365 * 10)
        )

        Subscription.objects.create(
            user=instance,
            plan=free_plan,
            start_date=timezone.now(),
            end_date=end_date,
            is_active=True,
            auto_renew=False,
        )

    except SubscriptionPlan.DoesNotExist:
        log.warning(
            "FREE subscription plan not found. "
            "User %s created without subscription. Create FREE plan in Admin.",
            instance.username,
        )
