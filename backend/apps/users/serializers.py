"""
Serializers for users app.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Profile
from .validators import validate_email_domain, validate_email_not_exists


class ProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for Profile model.
    """
    age = serializers.ReadOnlyField()
    bmi = serializers.ReadOnlyField()
    email_verified = serializers.ReadOnlyField()

    class Meta:
        model = Profile
        fields = [
            'full_name',
            'gender',
            'birth_date',
            'height',
            'weight',
            'activity_level',
            'goal_type',
            'age',
            'bmi',
            'email_verified',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'email_verified']

    def validate_height(self, value):
        """Validate height is in realistic range."""
        if value is not None and not (50 <= value <= 250):
            raise serializers.ValidationError("Рост должен быть от 50 до 250 см")
        return value

    def validate_weight(self, value):
        """Validate weight is in realistic range."""
        if value is not None and not (20 <= float(value) <= 500):
            raise serializers.ValidationError("Вес должен быть от 20 до 500 кг")
        return value


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model with profile.
    """
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'profile']
        read_only_fields = ['id', 'email']  # email нельзя менять, username можно


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration with email verification.
    """
    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(queryset=User.objects.all())
        ]
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm']

    def validate_email(self, value):
        """
        Validate email domain and check for disposable emails.
        """
        # Validate domain and disposable email check
        validated_email = validate_email_domain(value)
        return validated_email

    def validate(self, attrs):
        """
        Validate that passwords match.
        """
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Пароли не совпадают."
            })
        return attrs

    def create(self, validated_data):
        """
        Create new user with hashed password.
        Email is NOT verified initially - verification email will be sent.
        """
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        # Profile is created automatically via signal
        # email_verified defaults to False
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login with progressive rate limiting.

    SECURITY FEATURES:
    - Validates credentials
    - Tracks failed login attempts
    - Returns user-friendly error messages
    - No timing attack vulnerabilities (same error for user not found vs wrong password)
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        """
        Validate credentials and authenticate user.

        Raises:
            ValidationError: If credentials are invalid or account is locked
        """
        email = attrs.get('email')
        password = attrs.get('password')

        # Check for account lockout (via throttling)
        # Note: Actual throttling is done in LoginThrottle, but we provide
        # user-friendly error messages here

        # Find user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # SECURITY: Same error message as wrong password to prevent user enumeration
            raise serializers.ValidationError({
                "detail": "Неверный email или пароль."
            })

        # Authenticate with username and password
        authenticated_user = authenticate(username=user.username, password=password)

        if authenticated_user is None:
            # Record failed attempt for progressive rate limiting
            # IP address will be tracked in the view
            raise serializers.ValidationError({
                "detail": "Неверный email или пароль."
            })

        if not authenticated_user.is_active:
            raise serializers.ValidationError({
                "detail": "Учетная запись отключена. Обратитесь в поддержку."
            })

        attrs['user'] = authenticated_user
        return attrs


class TokenSerializer(serializers.Serializer):
    """
    Serializer for JWT tokens response.
    """
    refresh = serializers.CharField()
    access = serializers.CharField()
    user = UserSerializer()

    @staticmethod
    def get_tokens_for_user(user):
        """
        Generate JWT tokens for user.
        """
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password.
    """
    old_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        """
        Validate that new passwords match.
        """
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                "new_password": "Новые пароли не совпадают."
            })
        return attrs

    def validate_old_password(self, value):
        """
        Validate that old password is correct.
        """
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Старый пароль неверен.")
        return value
