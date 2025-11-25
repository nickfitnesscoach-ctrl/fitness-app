# Generated manually for avatar validators and version field

from django.db import migrations, models
import apps.users.validators


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_profile_avatar'),
    ]

    operations = [
        # Add avatar_version field
        migrations.AddField(
            model_name='profile',
            name='avatar_version',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Версия аватара для cache busting (инкрементируется при каждой загрузке)',
                verbose_name='Версия аватара'
            ),
        ),
        # Update avatar field with validators
        migrations.AlterField(
            model_name='profile',
            name='avatar',
            field=models.ImageField(
                blank=True,
                help_text='Фото профиля пользователя (макс. 5 МБ, форматы: JPG, PNG, WebP)',
                null=True,
                upload_to='avatars/',
                validators=[
                    apps.users.validators.validate_avatar_file_extension,
                    apps.users.validators.validate_avatar_file_size,
                ],
                verbose_name='Аватар'
            ),
        ),
    ]
