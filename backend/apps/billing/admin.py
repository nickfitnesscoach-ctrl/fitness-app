"""
Django Admin конфигурация для billing app.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import SubscriptionPlan, Subscription, Payment, Refund


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Админка для тарифных планов."""

    list_display = [
        'display_name',
        'name',
        'price',
        'duration_days',
        'max_photos_per_day',
        'history_days',
        'is_active',
        'created_at',
    ]
    list_filter = ['name', 'is_active', 'created_at']
    search_fields = ['display_name', 'description']
    ordering = ['price']

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'display_name', 'description', 'is_active')
        }),
        ('Цены и длительность', {
            'fields': ('price', 'duration_days')
        }),
        ('Возможности плана', {
            'fields': (
                'max_photos_per_day',
                'history_days',
                'ai_recognition',
                'advanced_stats',
                'priority_support',
            )
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Админка для подписок."""

    list_display = [
        'user',
        'plan',
        'start_date',
        'end_date',
        'is_active',
        'auto_renew',
        'get_days_remaining',
    ]
    list_filter = ['is_active', 'auto_renew', 'plan', 'created_at']
    search_fields = ['user__email', 'user__name']
    ordering = ['-created_at']
    raw_id_fields = ['user']

    fieldsets = (
        ('Пользователь и план', {
            'fields': ('user', 'plan')
        }),
        ('Даты', {
            'fields': ('start_date', 'end_date')
        }),
        ('Статус', {
            'fields': ('is_active', 'auto_renew')
        }),
        ('Способ оплаты', {
            'fields': ('yookassa_payment_method_id',)
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['created_at', 'updated_at']

    def get_days_remaining(self, obj):
        """Отображение оставшихся дней."""
        days = obj.days_remaining
        if days is None:
            return 'Бессрочно'
        if days == 0:
            return format_html('<span style="color: red;">Истекла</span>')
        if days < 7:
            return format_html(f'<span style="color: orange;">{days} дней</span>')
        return f'{days} дней'

    get_days_remaining.short_description = 'Осталось дней'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Админка для платежей."""

    list_display = [
        'id',
        'user',
        'plan',
        'amount',
        'currency',
        'get_status_display_colored',
        'provider',
        'is_recurring',
        'created_at',
        'paid_at',
    ]
    list_filter = ['status', 'provider', 'is_recurring', 'created_at']
    search_fields = [
        'user__email',
        'user__name',
        'yookassa_payment_id',
        'id',
    ]
    ordering = ['-created_at']
    raw_id_fields = ['user', 'subscription', 'plan']

    fieldsets = (
        ('ID и связи', {
            'fields': ('id', 'user', 'subscription', 'plan')
        }),
        ('Платёжные данные', {
            'fields': ('amount', 'currency', 'status', 'provider')
        }),
        ('YooKassa', {
            'fields': ('yookassa_payment_id', 'yookassa_payment_method_id')
        }),
        ('Настройки', {
            'fields': ('is_recurring', 'save_payment_method')
        }),
        ('Дополнительно', {
            'fields': ('description', 'error_message', 'metadata')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at', 'paid_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['id', 'created_at', 'updated_at']

    def get_status_display_colored(self, obj):
        """Цветное отображение статуса."""
        colors = {
            'PENDING': 'gray',
            'WAITING_FOR_CAPTURE': 'orange',
            'SUCCEEDED': 'green',
            'CANCELED': 'red',
            'FAILED': 'red',
            'REFUNDED': 'blue',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            f'<span style="color: {color}; font-weight: bold;">{obj.get_status_display()}</span>'
        )

    get_status_display_colored.short_description = 'Статус'


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """Админка для возвратов."""

    list_display = [
        'id',
        'payment',
        'amount',
        'get_status_display_colored',
        'created_at',
        'completed_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['id', 'payment__id', 'yookassa_refund_id']
    ordering = ['-created_at']
    raw_id_fields = ['payment']

    fieldsets = (
        ('ID и связи', {
            'fields': ('id', 'payment')
        }),
        ('Данные возврата', {
            'fields': ('amount', 'status', 'yookassa_refund_id')
        }),
        ('Причина и ошибки', {
            'fields': ('reason', 'error_message')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['id', 'created_at', 'updated_at']

    def get_status_display_colored(self, obj):
        """Цветное отображение статуса."""
        colors = {
            'PENDING': 'orange',
            'SUCCEEDED': 'green',
            'CANCELED': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            f'<span style="color: {color}; font-weight: bold;">{obj.get_status_display()}</span>'
        )

    get_status_display_colored.short_description = 'Статус'
