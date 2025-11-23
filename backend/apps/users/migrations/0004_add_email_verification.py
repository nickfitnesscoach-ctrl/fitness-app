# Generated manually for email verification feature

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_add_email_unique_constraint'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # Add email_verified field to Profile model
        migrations.AddField(
            model_name='profile',
            name='email_verified',
            field=models.BooleanField(
                default=False,
                verbose_name='Email подтвержден',
                help_text='Был ли email адрес подтвержден пользователем'
            ),
        ),

        # Create EmailVerificationToken model
        migrations.CreateModel(
            name='EmailVerificationToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(help_text='Уникальный токен для верификации email', max_length=64, unique=True, verbose_name='Токен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('expires_at', models.DateTimeField(help_text='Токен действителен в течение 24 часов', verbose_name='Срок действия')),
                ('is_used', models.BooleanField(default=False, help_text='Был ли токен использован для верификации', verbose_name='Использован')),
                ('used_at', models.DateTimeField(blank=True, null=True, verbose_name='Дата использования')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_verification_tokens', to='auth.user', verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Токен верификации email',
                'verbose_name_plural': 'Токены верификации email',
                'ordering': ['-created_at'],
            },
        ),

        # Add indexes
        migrations.AddIndex(
            model_name='emailverificationtoken',
            index=models.Index(fields=['token'], name='users_email_token_idx'),
        ),
        migrations.AddIndex(
            model_name='emailverificationtoken',
            index=models.Index(fields=['user', 'is_used'], name='users_email_user_used_idx'),
        ),
        migrations.AddIndex(
            model_name='emailverificationtoken',
            index=models.Index(fields=['expires_at'], name='users_email_expires_idx'),
        ),
    ]
