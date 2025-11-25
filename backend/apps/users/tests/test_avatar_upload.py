"""
Comprehensive tests for avatar upload functionality.
Tests cover: avatar upload, validation (size, MIME type), URL generation, deletion of old avatars.
"""

import os
from io import BytesIO
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import Profile


# Use temporary media root for tests
TEMP_MEDIA_ROOT = 'test_media'


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AvatarUploadTest(TestCase):
    """Test avatar upload functionality."""

    def setUp(self):
        """Set up test client and user."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        self.profile = self.user.profile

        # Simulate Telegram authentication headers
        self.client.defaults['HTTP_X_TELEGRAM_ID'] = '123456789'
        self.client.defaults['HTTP_X_TELEGRAM_FIRST_NAME'] = 'Test'

        # Force authenticate for testing
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        """Clean up uploaded test files."""
        # Delete test media files
        if os.path.exists(TEMP_MEDIA_ROOT):
            import shutil
            shutil.rmtree(TEMP_MEDIA_ROOT)

    def create_test_image(self, format='JPEG', size=(100, 100), color='red'):
        """Helper to create a test image file."""
        image = Image.new('RGB', size, color)
        file = BytesIO()
        image.save(file, format=format)
        file.seek(0)

        # Determine file extension and MIME type
        ext_map = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'), 'WEBP': ('webp', 'image/webp')}
        ext, mime_type = ext_map.get(format, ('jpg', 'image/jpeg'))

        return SimpleUploadedFile(
            name=f'test_avatar.{ext}',
            content=file.read(),
            content_type=mime_type
        )

    def test_upload_avatar_success_jpeg(self):
        """Test successful avatar upload with JPEG."""
        avatar_file = self.create_test_image(format='JPEG')

        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('profile', response.data)
        self.assertIsNotNone(response.data['profile']['avatar_url'])
        self.assertIn('/media/avatars/', response.data['profile']['avatar_url'])

        # Verify profile was updated
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.avatar)
        self.assertTrue(self.profile.avatar.name.startswith('avatars/'))

    def test_upload_avatar_success_png(self):
        """Test successful avatar upload with PNG."""
        avatar_file = self.create_test_image(format='PNG')

        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['profile']['avatar_url'])

    def test_upload_avatar_success_webp(self):
        """Test successful avatar upload with WebP."""
        avatar_file = self.create_test_image(format='WEBP')

        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['profile']['avatar_url'])

    def test_upload_avatar_replaces_old_avatar(self):
        """Test that uploading a new avatar deletes the old one."""
        # Upload first avatar
        avatar_file_1 = self.create_test_image(format='JPEG', color='red')
        response_1 = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file_1},
            format='multipart'
        )
        self.assertEqual(response_1.status_code, status.HTTP_200_OK)

        self.profile.refresh_from_db()
        old_avatar_path = self.profile.avatar.path
        old_avatar_name = self.profile.avatar.name

        # Upload second avatar
        avatar_file_2 = self.create_test_image(format='PNG', color='blue')
        response_2 = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file_2},
            format='multipart'
        )
        self.assertEqual(response_2.status_code, status.HTTP_200_OK)

        self.profile.refresh_from_db()
        new_avatar_name = self.profile.avatar.name

        # Check that avatar was replaced
        self.assertNotEqual(old_avatar_name, new_avatar_name)
        # Note: Old file deletion is handled by the view, file system cleanup happens in tearDown

    def test_upload_avatar_file_too_large(self):
        """Test that files larger than 5MB are rejected."""
        # Create a large image (simulating >5MB)
        # We'll mock this by creating a large BytesIO object
        large_file = BytesIO(b'0' * (6 * 1024 * 1024))  # 6 MB
        avatar_file = SimpleUploadedFile(
            name='large_avatar.jpg',
            content=large_file.read(),
            content_type='image/jpeg'
        )

        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('превышает', response.data['error'].lower())

    def test_upload_avatar_invalid_mime_type(self):
        """Test that invalid MIME types are rejected."""
        # Create a text file instead of image
        text_file = SimpleUploadedFile(
            name='test.txt',
            content=b'This is not an image',
            content_type='text/plain'
        )

        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': text_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('формат', response.data['error'].lower())

    def test_upload_avatar_no_file_provided(self):
        """Test error when no file is provided."""
        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('не предоставлен', response.data['error'].lower())

    def test_upload_avatar_requires_authentication(self):
        """Test that avatar upload requires authentication."""
        # Log out and remove Telegram headers
        self.client.force_authenticate(user=None)
        # Remove Telegram auth headers
        del self.client.defaults['HTTP_X_TELEGRAM_ID']
        del self.client.defaults['HTTP_X_TELEGRAM_FIRST_NAME']

        avatar_file = self.create_test_image()
        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_avatar_url_in_profile_response(self):
        """Test that avatar_url is included in profile GET response."""
        # Upload an avatar first
        avatar_file = self.create_test_image()
        self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file},
            format='multipart'
        )

        # Get profile
        response = self.client.get('/api/v1/users/profile/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('profile', response.data)
        self.assertIsNotNone(response.data['profile']['avatar_url'])
        self.assertIn('avatars/', response.data['profile']['avatar_url'])

    def test_avatar_url_null_when_no_avatar(self):
        """Test that avatar_url is null when user has no avatar."""
        response = self.client.get('/api/v1/users/profile/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('profile', response.data)
        self.assertIsNone(response.data['profile']['avatar_url'])


class ProfileSerializerTest(TestCase):
    """Test ProfileSerializer avatar_url field."""

    def setUp(self):
        """Set up test user and profile."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        self.profile = self.user.profile

    def test_avatar_url_returns_full_url_with_request_context(self):
        """Test that avatar_url returns full URL when request context is provided."""
        from apps.users.serializers import ProfileSerializer
        from django.test import RequestFactory

        # Create a mock avatar
        avatar_file = SimpleUploadedFile(
            name='test_avatar.jpg',
            content=b'fake image content',
            content_type='image/jpeg'
        )
        self.profile.avatar = avatar_file
        self.profile.save()

        # Create request context
        factory = RequestFactory()
        request = factory.get('/api/v1/users/profile/')

        serializer = ProfileSerializer(self.profile, context={'request': request})

        self.assertIsNotNone(serializer.data['avatar_url'])
        self.assertTrue(serializer.data['avatar_url'].startswith('http'))

    def test_avatar_url_returns_relative_url_without_request_context(self):
        """Test that avatar_url returns relative URL when no request context."""
        from apps.users.serializers import ProfileSerializer

        # Create a mock avatar
        avatar_file = SimpleUploadedFile(
            name='test_avatar.jpg',
            content=b'fake image content',
            content_type='image/jpeg'
        )
        self.profile.avatar = avatar_file
        self.profile.save()

        serializer = ProfileSerializer(self.profile)

        self.assertIsNotNone(serializer.data['avatar_url'])
        self.assertIn('avatars/', serializer.data['avatar_url'])

    def test_avatar_url_null_when_no_avatar(self):
        """Test that avatar_url is None when profile has no avatar."""
        from apps.users.serializers import ProfileSerializer

        serializer = ProfileSerializer(self.profile)

        self.assertIsNone(serializer.data['avatar_url'])


class AvatarValidatorTest(TestCase):
    """Test avatar validators."""

    def setUp(self):
        """Set up test user and profile."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        self.profile = self.user.profile

    def create_test_image(self, format='JPEG', size=(100, 100)):
        """Helper to create a test image file."""
        image = Image.new('RGB', size, 'red')
        file = BytesIO()
        image.save(file, format=format)
        file.seek(0)

        ext_map = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'), 'WEBP': ('webp', 'image/webp')}
        ext, mime_type = ext_map.get(format, ('jpg', 'image/jpeg'))

        return SimpleUploadedFile(
            name=f'test_avatar.{ext}',
            content=file.read(),
            content_type=mime_type
        )

    def test_validate_avatar_file_size(self):
        """Test that file size validator works correctly."""
        from apps.users.validators import validate_avatar_file_size
        from django.core.exceptions import ValidationError

        # Create a large file (simulating >5MB)
        large_file = SimpleUploadedFile(
            name='large.jpg',
            content=b'0' * (6 * 1024 * 1024),  # 6 MB
            content_type='image/jpeg'
        )

        with self.assertRaises(ValidationError) as context:
            validate_avatar_file_size(large_file)

        self.assertIn('превышает', str(context.exception).lower())

    def test_validate_avatar_file_extension(self):
        """Test that file extension validator works correctly."""
        from apps.users.validators import validate_avatar_file_extension
        from django.core.exceptions import ValidationError

        # Create a file with invalid extension
        invalid_file = SimpleUploadedFile(
            name='test.txt',
            content=b'not an image',
            content_type='text/plain'
        )

        with self.assertRaises(ValidationError) as context:
            validate_avatar_file_extension(invalid_file)

        self.assertIn('формат', str(context.exception).lower())

    def test_validate_avatar_mime_type(self):
        """Test that MIME type validator works correctly."""
        from apps.users.validators import validate_avatar_mime_type
        from django.core.exceptions import ValidationError

        # Create a file with invalid MIME type
        invalid_file = SimpleUploadedFile(
            name='test.txt',
            content=b'not an image',
            content_type='text/plain'
        )

        with self.assertRaises(ValidationError) as context:
            validate_avatar_mime_type(invalid_file)

        self.assertIn('формат', str(context.exception).lower())


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AvatarVersionTest(TestCase):
    """Test avatar_version and cache busting functionality."""

    def setUp(self):
        """Set up test client and user."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        self.profile = self.user.profile

        # Simulate Telegram authentication headers
        self.client.defaults['HTTP_X_TELEGRAM_ID'] = '123456789'
        self.client.defaults['HTTP_X_TELEGRAM_FIRST_NAME'] = 'Test'

        # Force authenticate for testing
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        """Clean up uploaded test files."""
        if os.path.exists(TEMP_MEDIA_ROOT):
            import shutil
            shutil.rmtree(TEMP_MEDIA_ROOT)

    def create_test_image(self, format='JPEG', size=(100, 100)):
        """Helper to create a test image file."""
        image = Image.new('RGB', size, 'red')
        file = BytesIO()
        image.save(file, format=format)
        file.seek(0)

        ext_map = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png')}
        ext, mime_type = ext_map.get(format, ('jpg', 'image/jpeg'))

        return SimpleUploadedFile(
            name=f'test_avatar.{ext}',
            content=file.read(),
            content_type=mime_type
        )

    def test_avatar_version_starts_at_zero(self):
        """Test that new profiles have avatar_version = 0."""
        self.assertEqual(self.profile.avatar_version, 0)

    def test_avatar_version_increments_on_upload(self):
        """Test that avatar_version increments when avatar is uploaded."""
        avatar_file = self.create_test_image()

        # Upload first avatar
        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_version, 1)

        # Upload second avatar
        avatar_file_2 = self.create_test_image()
        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file_2},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.avatar_version, 2)

    def test_avatar_url_includes_version_parameter(self):
        """Test that avatar_url includes version parameter for cache busting."""
        avatar_file = self.create_test_image()

        # Upload avatar
        response = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        avatar_url = response.data['profile']['avatar_url']

        # Check that version parameter is included
        self.assertIn('?v=1', avatar_url)

    def test_avatar_url_version_updates_on_replace(self):
        """Test that version parameter changes when avatar is replaced."""
        # Upload first avatar
        avatar_file_1 = self.create_test_image()
        response_1 = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file_1},
            format='multipart'
        )
        avatar_url_1 = response_1.data['profile']['avatar_url']

        # Upload second avatar
        avatar_file_2 = self.create_test_image(format='PNG')
        response_2 = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file_2},
            format='multipart'
        )
        avatar_url_2 = response_2.data['profile']['avatar_url']

        # Check that version parameters are different
        self.assertIn('?v=1', avatar_url_1)
        self.assertIn('?v=2', avatar_url_2)
        self.assertNotEqual(avatar_url_1, avatar_url_2)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class AvatarDeletionTest(TestCase):
    """Test safe avatar deletion functionality."""

    def setUp(self):
        """Set up test client and user."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        self.profile = self.user.profile

        # Simulate Telegram authentication headers
        self.client.defaults['HTTP_X_TELEGRAM_ID'] = '123456789'
        self.client.defaults['HTTP_X_TELEGRAM_FIRST_NAME'] = 'Test'

        # Force authenticate for testing
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        """Clean up uploaded test files."""
        if os.path.exists(TEMP_MEDIA_ROOT):
            import shutil
            shutil.rmtree(TEMP_MEDIA_ROOT)

    def create_test_image(self, format='JPEG'):
        """Helper to create a test image file."""
        image = Image.new('RGB', (100, 100), 'red')
        file = BytesIO()
        image.save(file, format=format)
        file.seek(0)

        ext_map = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png')}
        ext, mime_type = ext_map.get(format, ('jpg', 'image/jpeg'))

        return SimpleUploadedFile(
            name=f'test_avatar.{ext}',
            content=file.read(),
            content_type=mime_type
        )

    def test_old_avatar_deleted_on_new_upload(self):
        """Test that old avatar file is deleted when new one is uploaded."""
        from django.core.files.storage import default_storage

        # Upload first avatar
        avatar_file_1 = self.create_test_image()
        response_1 = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file_1},
            format='multipart'
        )
        self.assertEqual(response_1.status_code, status.HTTP_200_OK)

        self.profile.refresh_from_db()
        old_avatar_path = self.profile.avatar.name

        # Verify old avatar exists
        self.assertTrue(default_storage.exists(old_avatar_path))

        # Upload second avatar
        avatar_file_2 = self.create_test_image(format='PNG')
        response_2 = self.client.post(
            '/api/v1/users/profile/avatar/',
            {'avatar': avatar_file_2},
            format='multipart'
        )
        self.assertEqual(response_2.status_code, status.HTTP_200_OK)

        # Verify old avatar was deleted
        self.assertFalse(default_storage.exists(old_avatar_path))

        # Verify new avatar exists
        self.profile.refresh_from_db()
        new_avatar_path = self.profile.avatar.name
        self.assertTrue(default_storage.exists(new_avatar_path))
        self.assertNotEqual(old_avatar_path, new_avatar_path)

    def test_set_avatar_method_deletes_old_avatar(self):
        """Test that Profile.set_avatar() safely deletes old avatar."""
        from django.core.files.storage import default_storage

        # Set first avatar using set_avatar method
        avatar_file_1 = self.create_test_image()
        self.profile.set_avatar(avatar_file_1)

        old_avatar_path = self.profile.avatar.name
        self.assertTrue(default_storage.exists(old_avatar_path))

        # Set second avatar
        avatar_file_2 = self.create_test_image(format='PNG')
        self.profile.set_avatar(avatar_file_2)

        # Verify old avatar was deleted
        self.assertFalse(default_storage.exists(old_avatar_path))

        # Verify new avatar exists
        new_avatar_path = self.profile.avatar.name
        self.assertTrue(default_storage.exists(new_avatar_path))
        self.assertNotEqual(old_avatar_path, new_avatar_path)
