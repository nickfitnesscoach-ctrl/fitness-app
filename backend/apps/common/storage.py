"""
Storage utilities for FoodMind AI project.

Provides abstraction layer for file storage with easy migration to cloud services (S3, etc.).
"""

import os
from django.core.files.storage import FileSystemStorage
from django.conf import settings


class CustomFileStorage(FileSystemStorage):
    """
    Custom file storage class with abstraction for future S3 migration.

    Currently uses local filesystem storage, but can be easily switched to S3
    by changing the parent class to S3Boto3Storage or similar.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('location', settings.MEDIA_ROOT)
        kwargs.setdefault('base_url', settings.MEDIA_URL)
        super().__init__(*args, **kwargs)

    def get_available_name(self, name, max_length=None):
        """
        Get available filename by adding suffix if file already exists.
        """
        if self.exists(name):
            # Remove file extension
            name_parts = name.rsplit('.', 1)
            if len(name_parts) > 1:
                base_name, extension = name_parts
                name = f"{base_name}_{self._get_timestamp()}.{extension}"
            else:
                name = f"{name}_{self._get_timestamp()}"
        return super().get_available_name(name, max_length)

    def _get_timestamp(self):
        """Generate timestamp for unique filenames."""
        from datetime import datetime
        return datetime.now().strftime('%Y%m%d_%H%M%S')


# Ready for S3 migration:
#
# 1. Install boto3 and django-storages:
#    pip install boto3 django-storages
#
# 2. Add 'storages' to INSTALLED_APPS in settings
#
# 3. Configure settings:
#    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
#    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
#    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
#    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
#    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
#    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
#    AWS_DEFAULT_ACL = 'public-read'
#    AWS_QUERYSTRING_AUTH = False
#
# 4. Replace CustomFileStorage parent class:
#    from storages.backends.s3boto3 import S3Boto3Storage
#
#    class CustomFileStorage(S3Boto3Storage):
#        location = 'media'
#        file_overwrite = False
#
# 5. Update settings:
#    DEFAULT_FILE_STORAGE = 'apps.common.storage.CustomFileStorage'


def upload_to_user_photos(instance, filename):
    """
    Upload path function for user profile photos.

    Returns: 'uploads/users/{user_id}/photos/{filename}'
    """
    return os.path.join('uploads', 'users', str(instance.user.id), 'photos', filename)


def upload_to_food_photos(instance, filename):
    """
    Upload path function for food photos.

    Returns: 'uploads/users/{user_id}/food/{filename}'
    """
    return os.path.join('uploads', 'users', str(instance.user.id), 'food', filename)


def upload_to_meal_photos(instance, filename):
    """
    Upload path function for meal photos.

    Returns: 'uploads/users/{user_id}/meals/{meal_id}/{filename}'
    """
    return os.path.join('uploads', 'users', str(instance.user.id), 'meals', str(instance.id), filename)
