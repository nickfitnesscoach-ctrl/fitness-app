# Generated manually for removing MONTHLY_TEST plan

from django.db import migrations


def remove_monthly_test_plan(apps, schema_editor):
    """
    Удаляет устаревший тестовый план MONTHLY_TEST из БД.

    Оставляем только 4 актуальных плана:
    - FREE
    - TEST_LIVE
    - PRO_MONTHLY
    - PRO_YEARLY
    """
    SubscriptionPlan = apps.get_model('billing', 'SubscriptionPlan')

    # Удаляем MONTHLY_TEST если он существует
    deleted_count = SubscriptionPlan.objects.filter(code='MONTHLY_TEST').delete()[0]

    if deleted_count > 0:
        print(f"Deleted MONTHLY_TEST plan ({deleted_count} record(s))")
    else:
        print("MONTHLY_TEST plan not found, skipping deletion")


def reverse_removal(apps, schema_editor):
    """
    Обратная миграция не требуется - MONTHLY_TEST больше не используется.
    """
    print("Reverse migration: MONTHLY_TEST plan will not be restored")


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0007_update_subscription_plans_data'),
    ]

    operations = [
        migrations.RunPython(remove_monthly_test_plan, reverse_removal),
    ]
