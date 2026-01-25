"""
billing/admin.py

Django Admin для billing app.

Цели:
- удобное управление тарифами/подписками/платежами
- безопасность: ограничиваем опасные действия там, где это критично
- читаемость: цветные статусы, быстрые фильтры, нормальные search_fields

Важно:
- SubscriptionPlan: не даём создавать/удалять планы через админку (чтобы не сломать код/фронт).
- Payment/Refund/WebhookLog: обычно readonly (это аудит/история), но можно смотреть.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import Payment, Refund, Subscription, SubscriptionPlan, WebhookLog
from .notifications import send_gift_subscription_notification
from .usage import DailyUsage

# ---------------------------------------------------------------------
# SubscriptionPlan
# ---------------------------------------------------------------------


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """
    Админка тарифов.

    Политика:
    - Не создаём новые планы через админку.
    - Не удаляем планы через админку.
    - code readonly (SSOT).
    """

    list_display = (
        "code",
        "display_name",
        "price",
        "old_price",
        "duration_days",
        "daily_photo_limit",
        "history_days",
        "is_active",
        "is_test",
        "created_at",
    )
    list_filter = ("is_active", "is_test", "created_at")
    search_fields = ("code", "display_name", "description")
    ordering = ("price",)

    readonly_fields = ("code", "created_at", "updated_at")

    fieldsets = (
        (
            "Основное",
            {
                "fields": ("code", "display_name", "description", "is_active", "is_test"),
                "description": 'Поле "code" менять нельзя — оно используется в API и фронтенде.',
            },
        ),
        (
            "Цена и длительность",
            {
                "fields": ("price", "old_price", "duration_days"),
                "description": "old_price — якорная цена для отображения скидки (UI показывает 'было X₽').",
            },
        ),
        (
            "Лимиты и возможности",
            {
                "fields": (
                    "daily_photo_limit",
                    "history_days",
                    "ai_recognition",
                    "advanced_stats",
                    "priority_support",
                ),
            },
        ),
        (
            "Legacy (для совместимости)",
            {
                "fields": ("name", "max_photos_per_day"),
                "classes": ("collapse",),
                "description": "Устаревшие поля. В новых местах используем code/daily_photo_limit.",
            },
        ),
        (
            "Служебное",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Админка подписок пользователей."""

    list_display = (
        "user",
        "user_full_name",
        "plan",
        "start_date",
        "end_date",
        "is_active",
        "auto_renew",
        "card_bound",
        "days_left_badge",
    )
    list_filter = ("is_active", "auto_renew", "plan", "created_at")
    search_fields = (
        "user__email",
        "user__username",
        "user__telegram_profile__first_name",
        "user__telegram_profile__last_name",
        "user__telegram_profile__username",
    )
    ordering = ("-created_at",)
    raw_id_fields = ("user",)
    actions = ["grant_pro_monthly", "grant_pro_yearly", "downgrade_to_free"]

    @admin.action(description="🎁 Выдать PRO месяц (30 дней)")
    def grant_pro_monthly(self, request, queryset):
        """Выдаёт PRO месячную подписку выбранным пользователям."""
        self._grant_pro(request, queryset, "PRO_MONTHLY", 30)

    @admin.action(description="🎁 Выдать PRO год (365 дней)")
    def grant_pro_yearly(self, request, queryset):
        """Выдаёт PRO годовую подписку выбранным пользователям."""
        self._grant_pro(request, queryset, "PRO_YEARLY", 365)

    @admin.action(description="⬇️ Понизить до FREE")
    def downgrade_to_free(self, request, queryset):
        """Понижает выбранных пользователей до FREE плана."""
        try:
            free_plan = SubscriptionPlan.objects.get(code="FREE", is_active=True)
        except SubscriptionPlan.DoesNotExist:
            self.message_user(
                request,
                "❌ FREE план не найден в базе данных",
                messages.ERROR,
            )
            return

        now = timezone.now()
        count = 0
        for sub in queryset:
            sub.plan = free_plan
            sub.start_date = now
            sub.end_date = now + timedelta(days=365 * 10)
            sub.is_active = True
            sub.auto_renew = False
            sub.save()
            count += 1

        self.message_user(
            request,
            f"✅ {count} подписок понижено до FREE",
            messages.SUCCESS,
        )

    def _grant_pro(self, request, queryset, plan_code: str, days: int):
        """Общая логика выдачи PRO подписки."""
        try:
            pro_plan = SubscriptionPlan.objects.get(code=plan_code, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            self.message_user(
                request,
                f"❌ План {plan_code} не найден в базе данных",
                messages.ERROR,
            )
            return

        now = timezone.now()
        count = 0
        notified = 0
        for sub in queryset:
            # Если текущая подписка ещё активна и это PRO — продлеваем
            if sub.plan.code.startswith("PRO") and sub.end_date > now:
                sub.end_date = sub.end_date + timedelta(days=days)
            else:
                # Иначе — начинаем новую подписку с сегодня
                sub.start_date = now
                sub.end_date = now + timedelta(days=days)

            sub.plan = pro_plan
            sub.is_active = True
            sub.save()
            count += 1

            # Отправляем уведомление пользователю в Telegram
            tg_id = self._get_telegram_id(sub)
            if tg_id:
                end_date_str = sub.end_date.strftime("%d.%m.%Y")
                try:
                    if send_gift_subscription_notification(tg_id, pro_plan.display_name, end_date_str):
                        notified += 1
                except Exception:
                    pass  # Не ломаем процесс если уведомление не отправилось

        self.message_user(
            request,
            f"✅ {count} подписок обновлено до {pro_plan.display_name} (уведомлено: {notified})",
            messages.SUCCESS,
        )

    def _get_telegram_id(self, sub: Subscription) -> int | None:
        """Получает Telegram ID пользователя."""
        # Приоритет: telegram_profile
        if hasattr(sub.user, "telegram_profile"):
            return sub.user.telegram_profile.telegram_id
        # Fallback: из username (формат tg_XXXXXXXX)
        username = sub.user.username or ""
        if username.startswith("tg_"):
            try:
                return int(username[3:])
            except ValueError:
                pass
        return None

    @admin.display(description="Имя")
    def user_full_name(self, obj: Subscription) -> str:
        """Имя пользователя с ссылкой на Telegram профиль."""
        if hasattr(obj.user, "telegram_profile"):
            tg = obj.user.telegram_profile
            full = f"{tg.first_name} {tg.last_name}".strip() or "-"
            # Ссылка на Telegram: по username или по ID
            if tg.username:
                url = f"https://t.me/{tg.username}"
            else:
                url = f"tg://user?id={tg.telegram_id}"
            return format_html('<a href="{}" target="_blank">{}</a>', url, full)
        # Fallback на Profile.full_name
        if hasattr(obj.user, "profile") and obj.user.profile.full_name:
            return obj.user.profile.full_name
        return "-"

    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Пользователь и тариф", {"fields": ("user", "plan")}),
        ("Период", {"fields": ("start_date", "end_date")}),
        ("Статус", {"fields": ("is_active", "auto_renew")}),
        (
            "Карта/рекурренты",
            {
                "fields": ("yookassa_payment_method_id", "card_mask", "card_brand"),
                "description": "Эти поля заполняются после успешной оплаты/привязки карты (webhook).",
            },
        ),
        ("Служебное", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def card_bound(self, obj: Subscription):
        """Есть ли привязанная карта."""
        return bool(obj.yookassa_payment_method_id)

    card_bound.boolean = True
    card_bound.short_description = "Карта привязана"

    def days_left_badge(self, obj: Subscription):
        """Красивый бейдж оставшихся дней."""
        from django.utils.safestring import mark_safe

        days = obj.days_remaining
        if days is None:
            return mark_safe('<span style="color:#2b8a3e;font-weight:700;">FREE</span>')
        if days <= 0:
            return mark_safe('<span style="color:#c92a2a;font-weight:700;">Истекла</span>')
        if days < 7:
            return format_html('<span style="color:#e67700;font-weight:700;">{} дн.</span>', days)
        return f"{days} дн."

    days_left_badge.short_description = "Осталось"


# ---------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Админка платежей (история / аудит)."""

    list_display = (
        "id",
        "user",
        "plan",
        "amount",
        "currency",
        "status_badge",
        "provider",
        "is_recurring",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "provider", "is_recurring", "created_at")
    search_fields = ("user__email", "user__username", "yookassa_payment_id", "id")
    ordering = ("-created_at",)
    raw_id_fields = ("user", "subscription", "plan")

    readonly_fields = ("id", "created_at", "updated_at")

    fieldsets = (
        ("Связи", {"fields": ("id", "user", "subscription", "plan")}),
        ("Платёж", {"fields": ("amount", "currency", "status", "provider")}),
        ("YooKassa", {"fields": ("yookassa_payment_id", "yookassa_payment_method_id")}),
        ("Рекурренты", {"fields": ("is_recurring", "save_payment_method")}),
        ("Описание/ошибки", {"fields": ("description", "error_message", "metadata")}),
        (
            "Служебное",
            {
                "fields": ("created_at", "updated_at", "paid_at", "webhook_processed_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def status_badge(self, obj: Payment):
        colors = {
            "PENDING": "gray",
            "WAITING_FOR_CAPTURE": "#e67700",
            "SUCCEEDED": "#2b8a3e",
            "CANCELED": "#c92a2a",
            "FAILED": "#c92a2a",
            "REFUNDED": "#1c7ed6",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>', color, obj.get_status_display()
        )

    status_badge.short_description = "Статус"


# ---------------------------------------------------------------------
# Refund
# ---------------------------------------------------------------------


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """Админка возвратов (история / аудит)."""

    list_display = (
        "id",
        "payment",
        "amount",
        "status_badge",
        "created_at",
        "completed_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "payment__id", "yookassa_refund_id")
    ordering = ("-created_at",)
    raw_id_fields = ("payment",)

    readonly_fields = ("id", "created_at", "updated_at")

    fieldsets = (
        ("Связь", {"fields": ("id", "payment")}),
        ("Возврат", {"fields": ("amount", "status", "yookassa_refund_id")}),
        ("Причина/ошибки", {"fields": ("reason", "error_message")}),
        (
            "Служебное",
            {"fields": ("created_at", "updated_at", "completed_at"), "classes": ("collapse",)},
        ),
    )

    def status_badge(self, obj: Refund):
        colors = {"PENDING": "#e67700", "SUCCEEDED": "#2b8a3e", "CANCELED": "#c92a2a"}
        color = colors.get(obj.status, "black")
        return format_html(
            f'<span style="color:{color};font-weight:700;">{obj.get_status_display()}</span>'
        )

    status_badge.short_description = "Статус"


# ---------------------------------------------------------------------
# DailyUsage
# ---------------------------------------------------------------------


@admin.register(DailyUsage)
class DailyUsageAdmin(admin.ModelAdmin):
    """Админка дневного использования (лимиты фото)."""

    list_display = ("user", "date", "photo_ai_requests", "today_badge", "created_at")
    list_filter = ("date", "created_at")
    search_fields = ("user__email", "user__username")
    ordering = ("-date", "-created_at")
    raw_id_fields = ("user",)
    date_hierarchy = "date"

    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Пользователь", {"fields": ("user", "date")}),
        ("Использование", {"fields": ("photo_ai_requests",)}),
        ("Служебное", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def today_badge(self, obj: DailyUsage):
        return (
            format_html('<span style="color:#2b8a3e;font-weight:700;">✓</span>')
            if obj.is_today
            else "-"
        )

    today_badge.short_description = "Сегодня"


# ---------------------------------------------------------------------
# WebhookLog
# ---------------------------------------------------------------------


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    """
    Логи webhook.

    Это аудит/отладка:
    - видеть дубли
    - видеть ошибки парсинга/обработки
    - смотреть payload и client_ip
    """

    list_display = (
        "created_at",
        "event_type",
        "event_id",
        "payment_id",
        "status",
        "attempts",
        "client_ip",
    )
    list_filter = ("status", "event_type", "created_at")
    search_fields = ("event_id", "payment_id")
    ordering = ("-created_at",)

    readonly_fields = ("id", "created_at", "processed_at")

    fieldsets = (
        ("Событие", {"fields": ("event_type", "event_id", "payment_id")}),
        ("Статус", {"fields": ("status", "attempts", "error_message", "processed_at")}),
        ("Запрос", {"fields": ("client_ip", "raw_payload")}),
        ("Служебное", {"fields": ("id", "created_at"), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        return False
