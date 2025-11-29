# Generated manually for adding code field to SubscriptionPlan

from django.db import migrations, models


def populate_code_field(apps, schema_editor):
    """
    Заполняет поле code существующих планов на основе поля name.
    """
    SubscriptionPlan = apps.get_model('billing', 'SubscriptionPlan')

    # Mapping: name -> code
    name_to_code = {
        'FREE': 'FREE',
        'MONTHLY': 'PRO_MONTHLY',
        'YEARLY': 'PRO_YEARLY',
        'TEST_LIVE': 'TEST_LIVE',
    }

    for plan in SubscriptionPlan.objects.all():
        if plan.name in name_to_code:
            plan.code = name_to_code[plan.name]
            plan.save(update_fields=['code'])
            print(f"Updated plan {plan.name} -> code={plan.code}")
        else:
            # Для неизвестных планов используем name как code
            plan.code = plan.name
            plan.save(update_fields=['code'])
            print(f"Updated unknown plan {plan.name} -> code={plan.code}")


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_add_is_test_field_and_create_test_plan'),
    ]

    operations = [
        # 1. Добавляем поле code (nullable и не unique для начала)
        migrations.AddField(
            model_name='subscriptionplan',
            name='code',
            field=models.CharField(
                max_length=50,
                verbose_name='Системный код',
                help_text='Уникальный код для API (например: FREE, PRO_MONTHLY, PRO_YEARLY)',
                null=True,
                blank=True,
            ),
        ),

        # 2. Заполняем code для существующих записей
        migrations.RunPython(populate_code_field, migrations.RunPython.noop),

        # 3. Делаем поле code обязательным и уникальным
        migrations.AlterField(
            model_name='subscriptionplan',
            name='code',
            field=models.CharField(
                max_length=50,
                unique=True,
                verbose_name='Системный код',
                help_text='Уникальный код для API (например: FREE, PRO_MONTHLY, PRO_YEARLY)'
            ),
        ),

        # 4. Делаем поле name опциональным (теперь используем code)
        migrations.AlterField(
            model_name='subscriptionplan',
            name='name',
            field=models.CharField(
                verbose_name='Название плана (legacy)',
                max_length=50,
                choices=[
                    ('FREE', 'Бесплатный'),
                    ('PRO_MONTHLY', 'PRO месячный'),
                    ('PRO_YEARLY', 'PRO годовой'),
                    ('MONTHLY', 'Месячный (legacy)'),
                    ('YEARLY', 'Годовой (legacy)'),
                ],
                unique=True,
                blank=True,
                null=True,
                help_text='DEPRECATED: используйте поле code'
            ),
        ),
    ]
