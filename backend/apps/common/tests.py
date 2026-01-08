"""
Tests for common utilities.
"""

import io
from PIL import Image
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from .image_utils import compress_image, get_image_info


class ImageCompressionTestCase(TestCase):
    """Tests for B-013: Image compression utility."""

    def create_test_image(self, width=2000, height=1500, format='JPEG'):
        """Create a test image file."""
        img = Image.new('RGB', (width, height), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        buffer.seek(0)
        return SimpleUploadedFile(
            name=f'test.{format.lower()}',
            content=buffer.read(),
            content_type=f'image/{format.lower()}'
        )

    def test_compress_large_image(self):
        """Test that large images are resized."""
        # Create 2000x1500 image (larger than MAX_DIMENSION=1920)
        image_file = self.create_test_image(2000, 1500)
        original_size = image_file.size

        # Compress
        result = compress_image(image_file)

        # Verify it's compressed
        self.assertLessEqual(result.size, original_size)

        # Verify dimensions are reduced
        result.seek(0)
        img = Image.open(result)
        self.assertLessEqual(img.width, 1920)
        self.assertLessEqual(img.height, 1920)

    def test_small_image_unchanged(self):
        """Test that small images are not resized."""
        # Create 800x600 image (smaller than MAX_DIMENSION)
        image_file = self.create_test_image(800, 600)

        # Compress
        result = compress_image(image_file)

        # Should still be valid image
        result.seek(0)
        img = Image.open(result)
        # Dimensions should be similar (might change due to recompression)
        self.assertLessEqual(img.width, 1920)

    def test_rgba_to_rgb_conversion(self):
        """Test that RGBA images are converted to RGB."""
        # Create RGBA image (PNG with alpha)
        img = Image.new('RGBA', (500, 500), color=(255, 0, 0, 128))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        image_file = SimpleUploadedFile(
            name='test.png',
            content=buffer.read(),
            content_type='image/png'
        )

        # Compress
        result = compress_image(image_file)

        # Should be JPEG (RGB)
        result.seek(0)
        img = Image.open(result)
        self.assertEqual(img.mode, 'RGB')

    def test_get_image_info(self):
        """Test get_image_info utility."""
        image_file = self.create_test_image(1024, 768)

        info = get_image_info(image_file)

        self.assertEqual(info['width'], 1024)
        self.assertEqual(info['height'], 768)
        self.assertEqual(info['format'], 'JPEG')
        self.assertEqual(info['mode'], 'RGB')
        self.assertGreater(info['size_bytes'], 0)

    def test_compress_preserves_aspect_ratio(self):
        """Test that compression preserves aspect ratio."""
        # Create wide image
        image_file = self.create_test_image(3000, 1000)

        result = compress_image(image_file)

        result.seek(0)
        img = Image.open(result)

        # Aspect ratio should be preserved (3:1)
        aspect_ratio = img.width / img.height
        self.assertAlmostEqual(aspect_ratio, 3.0, places=1)

    def test_compress_tall_image(self):
        """Test compression of tall image."""
        # Create tall image
        image_file = self.create_test_image(1000, 3000)

        result = compress_image(image_file)

        result.seek(0)
        img = Image.open(result)

        # Height should be limited to 1920
        self.assertLessEqual(img.height, 1920)
        # Aspect ratio should be preserved
        aspect_ratio = img.height / img.width
        self.assertAlmostEqual(aspect_ratio, 3.0, places=1)


class ImageCompressionEdgeCasesTestCase(TestCase):
    """Edge case tests for image compression."""

    def test_invalid_image_returns_original(self):
        """Test that invalid image returns original file."""
        invalid_file = SimpleUploadedFile(
            name='invalid.jpg',
            content=b'not an image',
            content_type='image/jpeg'
        )

        # Should return original without crashing
        result = compress_image(invalid_file)
        self.assertIsNotNone(result)

    def test_empty_file_returns_original(self):
        """Test that empty file returns original."""
        empty_file = SimpleUploadedFile(
            name='empty.jpg',
            content=b'',
            content_type='image/jpeg'
        )

        result = compress_image(empty_file)
        self.assertIsNotNone(result)


class GetClientIPTestCase(TestCase):
    """
    Tests for get_client_ip() with XFF protection.

    Security requirements:
    - By default: NEVER trust X-Forwarded-For (prevents IP spoofing)
    - With TRUSTED_PROXIES_ENABLED: trust XFF ONLY from verified proxies
    - Always fallback to REMOTE_ADDR if XFF is not trusted
    """

    def _create_mock_request(self, remote_addr, xff=None):
        """Create mock request with META dict."""
        class MockRequest:
            def __init__(self, remote_addr, xff):
                self.META = {'REMOTE_ADDR': remote_addr}
                if xff:
                    self.META['HTTP_X_FORWARDED_FOR'] = xff
        return MockRequest(remote_addr, xff)

    def test_no_xff_returns_remote_addr(self):
        """Without XFF header, should return REMOTE_ADDR."""
        from .audit import get_client_ip

        request = self._create_mock_request('1.2.3.4')
        ip = get_client_ip(request)

        self.assertEqual(ip, '1.2.3.4')

    def test_xff_not_trusted_by_default(self):
        """
        By default (TRUSTED_PROXIES_ENABLED=False), XFF should be ignored.

        Security: prevents external clients from spoofing IP via XFF header.
        """
        from django.test import override_settings
        from .audit import get_client_ip

        request = self._create_mock_request('1.2.3.4', xff='9.9.9.9')

        with override_settings(TRUSTED_PROXIES_ENABLED=False):
            ip = get_client_ip(request)

        # Should ignore XFF and return REMOTE_ADDR
        self.assertEqual(ip, '1.2.3.4')

    def test_xff_from_untrusted_proxy_ignored(self):
        """
        XFF from non-trusted proxy should be ignored.

        Even if TRUSTED_PROXIES_ENABLED=True, if REMOTE_ADDR is not in
        TRUSTED_PROXIES list, XFF should be ignored.
        """
        from django.test import override_settings
        from .audit import get_client_ip

        request = self._create_mock_request('5.6.7.8', xff='9.9.9.9')

        with override_settings(
            TRUSTED_PROXIES_ENABLED=True,
            TRUSTED_PROXIES=['172.24.0.0/16']  # 5.6.7.8 is NOT in this range
        ):
            ip = get_client_ip(request)

        # Should ignore XFF because proxy is not trusted
        self.assertEqual(ip, '5.6.7.8')

    def test_xff_from_trusted_proxy_cidr(self):
        """
        XFF from trusted proxy (CIDR range) should be parsed correctly.

        If REMOTE_ADDR is in TRUSTED_PROXIES CIDR range, trust XFF.
        """
        from django.test import override_settings
        from .audit import get_client_ip

        request = self._create_mock_request('172.24.0.5', xff='9.9.9.9')

        with override_settings(
            TRUSTED_PROXIES_ENABLED=True,
            TRUSTED_PROXIES=['172.24.0.0/16']  # 172.24.0.5 is in this range
        ):
            ip = get_client_ip(request)

        # Should trust XFF and return real client IP
        self.assertEqual(ip, '9.9.9.9')

    def test_xff_from_trusted_proxy_single_ip(self):
        """
        XFF from trusted proxy (single IP) should be parsed correctly.
        """
        from django.test import override_settings
        from .audit import get_client_ip

        request = self._create_mock_request('10.0.0.1', xff='9.9.9.9')

        with override_settings(
            TRUSTED_PROXIES_ENABLED=True,
            TRUSTED_PROXIES=['10.0.0.1']  # Exact IP match
        ):
            ip = get_client_ip(request)

        # Should trust XFF and return real client IP
        self.assertEqual(ip, '9.9.9.9')

    def test_xff_chain_returns_leftmost(self):
        """
        XFF with multiple IPs should return leftmost (real client).

        Format: X-Forwarded-For: client_ip, proxy1_ip, proxy2_ip
        """
        from django.test import override_settings
        from .audit import get_client_ip

        request = self._create_mock_request('172.24.0.5', xff='9.9.9.9, 10.0.0.1, 172.24.0.5')

        with override_settings(
            TRUSTED_PROXIES_ENABLED=True,
            TRUSTED_PROXIES=['172.24.0.0/16']
        ):
            ip = get_client_ip(request)

        # Should return leftmost IP (real client)
        self.assertEqual(ip, '9.9.9.9')

    def test_xff_with_spaces(self):
        """
        XFF with spaces should be parsed correctly.
        """
        from django.test import override_settings
        from .audit import get_client_ip

        request = self._create_mock_request('172.24.0.5', xff='  9.9.9.9  ,  10.0.0.1  ')

        with override_settings(
            TRUSTED_PROXIES_ENABLED=True,
            TRUSTED_PROXIES=['172.24.0.0/16']
        ):
            ip = get_client_ip(request)

        # Should trim spaces and return real client IP
        self.assertEqual(ip, '9.9.9.9')

    def test_empty_xff_returns_remote_addr(self):
        """
        Empty XFF header should fallback to REMOTE_ADDR.
        """
        from django.test import override_settings
        from .audit import get_client_ip

        request = self._create_mock_request('172.24.0.5', xff='')

        with override_settings(
            TRUSTED_PROXIES_ENABLED=True,
            TRUSTED_PROXIES=['172.24.0.0/16']
        ):
            ip = get_client_ip(request)

        # Should fallback to REMOTE_ADDR
        self.assertEqual(ip, '172.24.0.5')

    def test_malformed_xff_returns_remote_addr(self):
        """
        Malformed XFF (only commas/spaces) should fallback to REMOTE_ADDR.
        """
        from django.test import override_settings
        from .audit import get_client_ip

        request = self._create_mock_request('172.24.0.5', xff='  ,  ,  ')

        with override_settings(
            TRUSTED_PROXIES_ENABLED=True,
            TRUSTED_PROXIES=['172.24.0.0/16']
        ):
            ip = get_client_ip(request)

        # Should fallback to REMOTE_ADDR
        self.assertEqual(ip, '172.24.0.5')

    def test_unknown_remote_addr_fallback(self):
        """
        If REMOTE_ADDR is missing, should return 'unknown'.
        """
        from .audit import get_client_ip

        class MockRequest:
            META = {}  # No REMOTE_ADDR

        request = MockRequest()
        ip = get_client_ip(request)

        self.assertEqual(ip, 'unknown')

    def test_multiple_trusted_proxies(self):
        """
        Multiple trusted proxy entries (CIDR + single IP) should work.
        """
        from django.test import override_settings
        from .audit import get_client_ip

        # Test CIDR range
        request1 = self._create_mock_request('172.24.0.5', xff='9.9.9.9')

        with override_settings(
            TRUSTED_PROXIES_ENABLED=True,
            TRUSTED_PROXIES=['172.24.0.0/16', '10.0.0.1']
        ):
            ip1 = get_client_ip(request1)
            self.assertEqual(ip1, '9.9.9.9')

            # Test single IP
            request2 = self._create_mock_request('10.0.0.1', xff='8.8.8.8')
            ip2 = get_client_ip(request2)
            self.assertEqual(ip2, '8.8.8.8')
