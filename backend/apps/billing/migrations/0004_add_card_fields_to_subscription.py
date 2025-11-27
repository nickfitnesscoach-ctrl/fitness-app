# Generated manually for card_mask and card_brand fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_populate_subscription_plans'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='card_mask',
            field=models.CharField(
                blank=True,
                help_text='Последние 4 цифры карты, например "•••• 1234"',
                max_length=20,
                null=True,
                verbose_name='Маска карты'
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='card_brand',
            field=models.CharField(
                blank=True,
                help_text='Тип платёжной карты: Visa, MasterCard, МИР и т.д.',
                max_length=50,
                null=True,
                verbose_name='Тип карты'
            ),
        ),
    ]
