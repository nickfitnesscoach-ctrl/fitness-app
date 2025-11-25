# Generated manually for avatar field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_profile_ai_recommendations_profile_current_body_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='avatar',
            field=models.ImageField(
                blank=True,
                help_text='Фото профиля пользователя (макс. 5 МБ, форматы: JPG, PNG, WebP)',
                null=True,
                upload_to='avatars/',
                verbose_name='Аватар'
            ),
        ),
    ]
