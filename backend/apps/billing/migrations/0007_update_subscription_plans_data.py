# Generated manually for updating subscription plan data (prices, names, etc.)

from django.db import migrations
from decimal import Decimal


def update_subscription_plans(apps, schema_editor):
    """
    Обновляет данные тарифных планов согласно ТЗ:
    - FREE: 0 RUB, бессрочно
    - PRO_MONTHLY: 299 RUB, 30 дней
    - PRO_YEARLY: 2490 RUB, 365 дней
    """
    SubscriptionPlan = apps.get_model('billing', 'SubscriptionPlan')

    # Обновляем FREE план
    free_plan = SubscriptionPlan.objects.filter(code='FREE').first()
    if free_plan:
        free_plan.display_name = 'Бесплатный'
        free_plan.price = Decimal('0.00')
        free_plan.duration_days = 0
        free_plan.daily_photo_limit = 3
        free_plan.history_days = 7
        free_plan.ai_recognition = True
        free_plan.advanced_stats = False
        free_plan.priority_support = False
        free_plan.is_active = True
        free_plan.save()
        print(f"Updated plan: {free_plan.code} -> {free_plan.display_name} ({free_plan.price} RUB)")

    # Обновляем PRO_MONTHLY план
    monthly_plan = SubscriptionPlan.objects.filter(code='PRO_MONTHLY').first()
    if monthly_plan:
        monthly_plan.display_name = 'PRO месяц'
        monthly_plan.price = Decimal('299.00')
        monthly_plan.duration_days = 30
        monthly_plan.daily_photo_limit = None  # Безлимит
        monthly_plan.history_days = 180  # 180 дней
        monthly_plan.ai_recognition = True
        monthly_plan.advanced_stats = True
        monthly_plan.priority_support = True
        monthly_plan.is_active = True
        monthly_plan.save()
        print(f"Updated plan: {monthly_plan.code} -> {monthly_plan.display_name} ({monthly_plan.price} RUB)")

    # Обновляем PRO_YEARLY план
    yearly_plan = SubscriptionPlan.objects.filter(code='PRO_YEARLY').first()
    if yearly_plan:
        yearly_plan.display_name = 'PRO год'
        yearly_plan.price = Decimal('2490.00')
        yearly_plan.duration_days = 365
        yearly_plan.daily_photo_limit = None  # Безлимит
        yearly_plan.history_days = 180  # 180 дней
        yearly_plan.ai_recognition = True
        yearly_plan.advanced_stats = True
        yearly_plan.priority_support = True
        yearly_plan.is_active = True
        yearly_plan.save()
        print(f"Updated plan: {yearly_plan.code} -> {yearly_plan.display_name} ({yearly_plan.price} RUB)")


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0006_add_code_field_to_subscription_plan'),
    ]

    operations = [
        migrations.RunPython(update_subscription_plans, migrations.RunPython.noop),
    ]
