"""
Admin configuration for users app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile, EmailVerificationToken


class ProfileInline(admin.StackedInline):
    """
    Inline admin for Profile model.
    """
    model = Profile
    can_delete = False
    verbose_name_plural = 'Профиль'


class UserAdmin(BaseUserAdmin):
    """
    Extended User admin with Profile inline.
    """
    inlines = (ProfileInline,)


# Unregister default User admin and register custom one
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for Profile model.
    """
    list_display = [
        'user',
        'full_name',
        'gender',
        'age',
        'height',
        'weight',
        'bmi',
        'activity_level',
        'created_at',
    ]
    list_filter = ['gender', 'activity_level', 'created_at']
    search_fields = ['user__username', 'user__email', 'full_name']
    readonly_fields = ['created_at', 'updated_at', 'age', 'bmi']

    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'full_name', 'gender', 'birth_date')
        }),
        ('Физические параметры', {
            'fields': ('height', 'weight', 'activity_level')
        }),
        ('Вычисляемые поля', {
            'fields': ('age', 'bmi'),
            'classes': ('collapse',)
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    """
    Admin interface for EmailVerificationToken model.
    """
    list_display = [
        'user',
        'token_short',
        'created_at',
        'expires_at',
        'is_used',
        'used_at',
        'is_valid_status',
    ]
    list_filter = ['is_used', 'created_at', 'expires_at']
    search_fields = ['user__username', 'user__email', 'token']
    readonly_fields = ['token', 'created_at', 'expires_at', 'used_at']
    ordering = ['-created_at']

    def token_short(self, obj):
        """Display shortened token."""
        return f"{obj.token[:8]}...{obj.token[-8:]}"
    token_short.short_description = 'Токен'

    def is_valid_status(self, obj):
        """Display if token is valid."""
        return obj.is_valid
    is_valid_status.short_description = 'Валидный'
    is_valid_status.boolean = True

    def has_add_permission(self, request):
        """Disable manual token creation in admin."""
        return False
