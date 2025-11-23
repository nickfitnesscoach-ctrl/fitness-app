"""
Comprehensive tests for email verification functionality.
Tests cover: token creation, email sending, verification flow, error cases.
"""

from datetime import timedelta
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import EmailVerificationToken
from apps.users.services import EmailVerificationService
from apps.users.validators import validate_email_domain, is_email_verified


class EmailVerificationTokenModelTest(TestCase):
    """Test EmailVerificationToken model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )

    def test_token_generation(self):
        """Test that token is generated automatically."""
        token = EmailVerificationToken.objects.create(user=self.user)

        self.assertIsNotNone(token.token)
        self.assertEqual(len(token.token), 43)  # URL-safe base64 32 bytes = 43 chars

    def test_token_expiration(self):
        """Test token expiration calculation."""
        token = EmailVerificationToken.objects.create(user=self.user)

        # Token should expire 24 hours from now
        expected_expiry = timezone.now() + timedelta(hours=24)
        self.assertAlmostEqual(
            token.expires_at.timestamp(),
            expected_expiry.timestamp(),
            delta=2  # Allow 2 seconds difference
        )

    def test_token_is_valid(self):
        """Test token validity check."""
        token = EmailVerificationToken.objects.create(user=self.user)

        # New token should be valid
        self.assertTrue(token.is_valid)
        self.assertFalse(token.is_expired)
        self.assertFalse(token.is_used)

    def test_token_is_expired(self):
        """Test expired token detection."""
        token = EmailVerificationToken.objects.create(user=self.user)

        # Manually set expiration to past
        token.expires_at = timezone.now() - timedelta(hours=1)
        token.save()

        self.assertFalse(token.is_valid)
        self.assertTrue(token.is_expired)

    def test_token_mark_as_used(self):
        """Test marking token as used."""
        token = EmailVerificationToken.objects.create(user=self.user)

        token.mark_as_used()

        self.assertFalse(token.is_valid)
        self.assertTrue(token.is_used)
        self.assertIsNotNone(token.used_at)

    def test_unique_token_constraint(self):
        """Test that token is unique."""
        token1 = EmailVerificationToken.objects.create(user=self.user)

        # Try to create another token with same string (should be impossible)
        # This test just verifies uniqueness at DB level
        from django.db import IntegrityError

        # Create a duplicate token manually
        token2 = EmailVerificationToken(user=self.user, token=token1.token)
        with self.assertRaises(IntegrityError):
            token2.save()


class EmailValidationTest(TestCase):
    """Test email validation utilities."""

    def test_valid_email(self):
        """Test validation of normal email."""
        email = 'user@example.com'
        result = validate_email_domain(email)
        self.assertEqual(result, email)

    def test_disposable_email_blocked(self):
        """Test that disposable emails are blocked."""
        from django.core.exceptions import ValidationError

        disposable_emails = [
            'test@10minutemail.com',
            'test@tempmail.com',
            'test@guerrillamail.com',
            'test@mailinator.com',
        ]

        for email in disposable_emails:
            with self.assertRaises(ValidationError):
                validate_email_domain(email)

    def test_suspicious_domain_pattern(self):
        """Test that suspicious patterns are detected."""
        from django.core.exceptions import ValidationError

        suspicious_emails = [
            'test@fakeemail.com',
            'test@tempmail123.com',
            'test@trashmail.org',
        ]

        for email in suspicious_emails:
            with self.assertRaises(ValidationError):
                validate_email_domain(email)

    def test_invalid_email_format(self):
        """Test invalid email format."""
        from django.core.exceptions import ValidationError

        invalid_emails = [
            'notanemail',
            '@example.com',
            'user@',
            'user @example.com',
        ]

        for email in invalid_emails:
            with self.assertRaises(ValidationError):
                validate_email_domain(email)


class EmailVerificationServiceTest(TestCase):
    """Test EmailVerificationService."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )

    def test_create_verification_token(self):
        """Test token creation."""
        token = EmailVerificationService.create_verification_token(self.user)

        self.assertIsNotNone(token)
        self.assertEqual(token.user, self.user)
        self.assertTrue(token.is_valid)

    def test_create_token_invalidates_old_tokens(self):
        """Test that creating new token invalidates old ones."""
        # Create first token
        token1 = EmailVerificationService.create_verification_token(self.user)

        # Create second token
        token2 = EmailVerificationService.create_verification_token(self.user)

        # Refresh first token from DB
        token1.refresh_from_db()

        # First token should be marked as used
        self.assertTrue(token1.is_used)
        self.assertFalse(token2.is_used)

    def test_send_verification_email(self):
        """Test sending verification email."""
        # Send email
        token = EmailVerificationService.send_verification_email(self.user)

        # Check that one email was sent
        self.assertEqual(len(mail.outbox), 1)

        # Check email content
        email = mail.outbox[0]
        self.assertIn(self.user.email, email.to)
        self.assertIn('Подтвердите ваш email', email.subject)
        self.assertIn(token.token, email.body)

    def test_verify_valid_token(self):
        """Test verifying valid token."""
        token = EmailVerificationService.create_verification_token(self.user)

        success, message, user = EmailVerificationService.verify_token(token.token)

        self.assertTrue(success)
        self.assertEqual(user, self.user)
        self.assertIn('успешно', message.lower())

        # Check that email is verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile.email_verified)

    def test_verify_expired_token(self):
        """Test verifying expired token."""
        token = EmailVerificationService.create_verification_token(self.user)

        # Expire the token
        token.expires_at = timezone.now() - timedelta(hours=1)
        token.save()

        success, message, user = EmailVerificationService.verify_token(token.token)

        self.assertFalse(success)
        self.assertIsNone(user)
        self.assertIn('истек', message.lower())

    def test_verify_used_token(self):
        """Test verifying already used token."""
        token = EmailVerificationService.create_verification_token(self.user)

        # Mark token as used
        token.mark_as_used()

        success, message, user = EmailVerificationService.verify_token(token.token)

        self.assertFalse(success)
        self.assertIsNone(user)
        self.assertIn('использован', message.lower())

    def test_verify_invalid_token(self):
        """Test verifying non-existent token."""
        success, message, user = EmailVerificationService.verify_token('invalid_token_123')

        self.assertFalse(success)
        self.assertIsNone(user)
        self.assertIn('неверный', message.lower())


class EmailVerificationAPITest(TestCase):
    """Test email verification API endpoints."""

    def setUp(self):
        self.client = APIClient()

    def test_registration_sends_verification_email(self):
        """Test that registration sends verification email."""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!'
        }

        response = self.client.post('/api/v1/users/auth/register/', data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('newuser@example.com', mail.outbox[0].to)

        # Check response includes verification status
        self.assertIn('email_verified', response.data)
        self.assertFalse(response.data['email_verified'])

    def test_registration_with_disposable_email_fails(self):
        """Test that registration with disposable email fails."""
        data = {
            'username': 'testuser',
            'email': 'test@10minutemail.com',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!'
        }

        response = self.client.post('/api/v1/users/auth/register/', data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_verify_email_endpoint_success(self):
        """Test email verification endpoint with valid token."""
        # Create user and token
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        token = EmailVerificationService.create_verification_token(user)

        # Verify email
        response = self.client.get(
            f'/api/v1/users/auth/verify-email/?token={token.token}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('успешно', response.data['detail'].lower())

        # Check that email is verified
        user.refresh_from_db()
        self.assertTrue(user.profile.email_verified)

    def test_verify_email_without_token(self):
        """Test verification endpoint without token."""
        response = self.client.get('/api/v1/users/auth/verify-email/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_verify_email_with_invalid_token(self):
        """Test verification with invalid token."""
        response = self.client.get(
            '/api/v1/users/auth/verify-email/?token=invalid_token_123'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_verify_email_with_expired_token(self):
        """Test verification with expired token."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        token = EmailVerificationService.create_verification_token(user)

        # Expire token
        token.expires_at = timezone.now() - timedelta(hours=1)
        token.save()

        response = self.client.get(
            f'/api/v1/users/auth/verify-email/?token={token.token}'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('истек', response.data['error'].lower())

    def test_resend_verification_email(self):
        """Test resending verification email."""
        # Create user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )

        # Login
        self.client.force_authenticate(user=user)

        # Resend verification
        response = self.client.post('/api/v1/users/auth/resend-verification/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('отправлено', response.data['detail'].lower())

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_verification_already_verified(self):
        """Test resending when email is already verified."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )

        # Mark email as verified
        user.profile.email_verified = True
        user.profile.save()

        # Login
        self.client.force_authenticate(user=user)

        # Try to resend
        response = self.client.post('/api/v1/users/auth/resend-verification/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('уже подтвержден', response.data['detail'].lower())

    def test_resend_verification_requires_authentication(self):
        """Test that resend requires authentication."""
        response = self.client.post('/api/v1/users/auth/resend-verification/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class EmailVerificationIntegrationTest(TestCase):
    """Integration tests for complete email verification flow."""

    def setUp(self):
        self.client = APIClient()

    def test_complete_verification_flow(self):
        """Test complete flow: register -> receive email -> verify."""
        # 1. Register new user
        register_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'TestPass123!',
            'password_confirm': 'TestPass123!'
        }

        register_response = self.client.post(
            '/api/v1/users/auth/register/',
            register_data
        )

        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        # 2. Extract token from email
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body

        # Find token in email (it's the last part of the URL)
        token = None
        for line in email_body.split('\n'):
            if 'token=' in line:
                token = line.split('token=')[1].strip()
                break

        self.assertIsNotNone(token)

        # 3. Verify email with token
        verify_response = self.client.get(
            f'/api/v1/users/auth/verify-email/?token={token}'
        )

        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        # 4. Check that user's email is verified
        user = User.objects.get(username='newuser')
        self.assertTrue(user.profile.email_verified)

        # 5. Try to use same token again (should fail)
        verify_again_response = self.client.get(
            f'/api/v1/users/auth/verify-email/?token={token}'
        )

        self.assertEqual(verify_again_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('использован', verify_again_response.data['error'].lower())

    def test_profile_shows_verification_status(self):
        """Test that profile endpoint shows email verification status."""
        # Create and login user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        self.client.force_authenticate(user=user)

        # Get profile
        response = self.client.get('/api/v1/users/profile/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('email_verified', response.data['profile'])
        self.assertFalse(response.data['profile']['email_verified'])
