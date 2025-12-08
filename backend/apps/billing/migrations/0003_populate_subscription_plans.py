# Generated manually
# Data migration to create/update subscription plans

from django.db import migrations


def populate_subscription_plans(apps, schema_editor):
    """
    Создаёт или обновляет стандартные тарифные планы:
    - FREE: бесплатный план с лимитом 3 фото в день
    - MONTHLY: месячный Pro план с безлимитным распознаванием
    - YEARLY: годовой Pro план с безлимитным распознаванием
    """
    SubscriptionPlan = apps.get_model('billing', 'SubscriptionPlan')

    # FREE Plan
    free_plan, created = SubscriptionPlan.objects.update_or_create(
        name='FREE',
        defaults={
            'display_name': 'Бесплатный',
            'description': 'Базовый функционал с ограничением 3 фото в день',
            'price': 0,
            'duration_days': 0,
            'daily_photo_limit': 3,  # Лимит 3 фото в день
            'max_photos_per_day': 3,  # Legacy field for compatibility
            'history_days': 7,
            'ai_recognition': True,
            'advanced_stats': False,
            'priority_support': False,
            'is_active': True,
        }
    )
    if created:
        print(f"[OK] Created FREE plan")
    else:
        print(f"[OK] Updated FREE plan")

    # MONTHLY Plan (Pro Monthly)
    monthly_plan, created = SubscriptionPlan.objects.update_or_create(
        name='MONTHLY',
        defaults={
            'display_name': 'Pro Месячный',
            'description': 'Безлимитное распознавание фото, расширенная статистика',
            'price': 299,
            'duration_days': 30,
            'daily_photo_limit': None,  # Безлимит
            'max_photos_per_day': -1,  # Legacy field: -1 = unlimited
            'history_days': -1,  # Unlimited history
            'ai_recognition': True,
            'advanced_stats': True,
            'priority_support': True,
            'is_active': True,
        }
    )
    if created:
        print(f"[OK] Created MONTHLY plan")
    else:
        print(f"[OK] Updated MONTHLY plan")

    # YEARLY Plan (Pro Yearly)
    yearly_plan, created = SubscriptionPlan.objects.update_or_create(
        name='YEARLY',
        defaults={
            'display_name': 'Pro Годовой',
            'description': 'Безлимитное распознавание фото, расширенная статистика. Экономия 30%!',
            'price': 2490,
            'duration_days': 365,
            'daily_photo_limit': None,  # Безлимит
            'max_photos_per_day': -1,  # Legacy field: -1 = unlimited
            'history_days': -1,  # Unlimited history
            'ai_recognition': True,
            'advanced_stats': True,
            'priority_support': True,
            'is_active': True,
        }
    )
    if created:
        print(f"[OK] Created YEARLY plan")
    else:
        print(f"[OK] Updated YEARLY plan")


def reverse_populate_plans(apps, schema_editor):
    """
    Откат миграции - удаляет созданные планы.
    """
    SubscriptionPlan = apps.get_model('billing', 'SubscriptionPlan')

    # Удаляем только если нет активных подписок
    for plan_name in ['FREE', 'MONTHLY', 'YEARLY']:
        try:
            plan = SubscriptionPlan.objects.get(name=plan_name)
            if plan.subscriptions.count() == 0:
                plan.delete()
                print(f"[OK] Deleted {plan_name} plan (no active subscriptions)")
            else:
                print(f"[WARNING] Kept {plan_name} plan (has active subscriptions)")
        except SubscriptionPlan.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_add_daily_photo_limit_and_usage'),
    ]

    operations = [
        migrations.RunPython(
            populate_subscription_plans,
            reverse_code=reverse_populate_plans
        ),
    ]
