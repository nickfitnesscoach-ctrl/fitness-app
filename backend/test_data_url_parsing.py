"""
Test script for data URL parsing utility.

This script tests the parse_data_url function to ensure it correctly
parses data URLs and extracts image bytes and content type.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

import django
django.setup()

from apps.ai_proxy.utils import parse_data_url


def test_parse_data_url():
    """Test parse_data_url function with various inputs."""

    print("=" * 80)
    print("Testing parse_data_url utility")
    print("=" * 80)

    # Test 1: Valid JPEG data URL
    print("\n1. Testing valid JPEG data URL...")
    # Create a small valid JPEG (1x1 red pixel)
    jpeg_base64 = "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlbaWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uLj5OXm5+jp6vLz9PX29/j5+v/aAAwDAQACEQMRAD8A4+iiigD/2Q=="
    data_url = f"data:image/jpeg;base64,{jpeg_base64}"

    try:
        image_bytes, content_type = parse_data_url(data_url)
        print(f"[OK] Success!")
        print(f"  Content Type: {content_type}")
        print(f"  Image Size: {len(image_bytes)} bytes")
        print(f"  First 10 bytes: {image_bytes[:10].hex()}")
    except Exception as e:
        print(f"[FAIL] Failed: {e}")

    # Test 2: Valid PNG data URL
    print("\n2. Testing valid PNG data URL...")
    # Create a small valid PNG (1x1 transparent pixel)
    png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    data_url = f"data:image/png;base64,{png_base64}"

    try:
        image_bytes, content_type = parse_data_url(data_url)
        print(f"[OK] Success!")
        print(f"  Content Type: {content_type}")
        print(f"  Image Size: {len(image_bytes)} bytes")
        print(f"  First 10 bytes: {image_bytes[:10].hex()}")
    except Exception as e:
        print(f"[FAIL] Failed: {e}")

    # Test 3: Invalid format (no data: prefix)
    print("\n3. Testing invalid format (no data: prefix)...")
    try:
        image_bytes, content_type = parse_data_url(jpeg_base64)
        print(f"[FAIL] Should have failed but didn't!")
    except ValueError as e:
        print(f"[OK] Correctly rejected: {e}")

    # Test 4: Invalid base64
    print("\n4. Testing invalid base64...")
    data_url = "data:image/jpeg;base64,!!!invalid!!!"
    try:
        image_bytes, content_type = parse_data_url(data_url)
        print(f"[FAIL] Should have failed but didn't!")
    except ValueError as e:
        print(f"[OK] Correctly rejected: {e}")

    # Test 5: Unsupported content type
    print("\n5. Testing unsupported content type...")
    data_url = f"data:image/gif;base64,{jpeg_base64}"
    try:
        image_bytes, content_type = parse_data_url(data_url)
        print(f"[FAIL] Should have failed but didn't!")
    except ValueError as e:
        print(f"[OK] Correctly rejected: {e}")

    # Test 6: Empty data
    print("\n6. Testing empty data...")
    data_url = "data:image/jpeg;base64,"
    try:
        image_bytes, content_type = parse_data_url(data_url)
        print(f"[FAIL] Should have failed but didn't!")
    except ValueError as e:
        print(f"[OK] Correctly rejected: {e}")

    print("\n" + "=" * 80)
    print("All tests completed!")
    print("=" * 80)


if __name__ == "__main__":
    test_parse_data_url()
