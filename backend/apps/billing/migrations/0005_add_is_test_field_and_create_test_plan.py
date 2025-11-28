# Generated manually for adding is_test field and creating test tariff

from django.db import migrations, models
from decimal import Decimal


def create_test_plan(apps, schema_editor):
    """
    Создаёт тестовый план за 1₽ для проверки live-платежей.
    Доступен только владельцу/админам.
    """
    SubscriptionPlan = apps.get_model('billing', 'SubscriptionPlan')

    # Проверяем, не существует ли уже тестовый план
    if SubscriptionPlan.objects.filter(name='TEST_LIVE').exists():
        print("Test plan already exists, skipping...")
        return

    SubscriptionPlan.objects.create(
        name='TEST_LIVE',
        display_name='Test Live Payment 1₽',
        description='Тестовый платёж для проверки боевого магазина YooKassa. Только для владельца/админов.',
        price=Decimal('1.00'),
        duration_days=30,  # 1 месяц как у MONTHLY
        daily_photo_limit=None,  # Безлимит
        max_photos_per_day=-1,  # Legacy: неограниченно
        history_days=-1,  # Неограниченно
        ai_recognition=True,
        advanced_stats=True,
        priority_support=True,
        is_active=True,
        is_test=True,  # Флаг тестового плана
    )
    print("Created test plan: Test Live Payment 1₽")


def delete_test_plan(apps, schema_editor):
    """Удаляет тестовый план при откате миграции."""
    SubscriptionPlan = apps.get_model('billing', 'SubscriptionPlan')
    SubscriptionPlan.objects.filter(name='TEST_LIVE').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0004_add_card_fields_to_subscription'),
    ]

    operations = [
        # 1. Добавляем поле is_test
        migrations.AddField(
            model_name='subscriptionplan',
            name='is_test',
            field=models.BooleanField(
                default=False,
                help_text='Тестовый план для проверки live-платежей (только для владельца/админов)',
                verbose_name='Тестовый план'
            ),
        ),

        # 2. Создаём тестовый план за 1₽
        migrations.RunPython(create_test_plan, delete_test_plan),
    ]
