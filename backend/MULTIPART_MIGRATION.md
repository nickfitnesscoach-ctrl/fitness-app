# Migration to Multipart/Form-Data for AI Proxy

## Overview

Django backend has been updated to send images to AI Proxy using `multipart/form-data` instead of JSON with data URLs.

## What Changed

### External API (No Breaking Changes)

The Django REST API endpoint `/api/v1/ai/recognize/` **remains unchanged**:

```json
POST /api/v1/ai/recognize/
Content-Type: application/json

{
  "image": "data:image/jpeg;base64,...",
  "comment": "My lunch"
}
```

### Internal Processing (New Implementation)

**Before:**
```
Client → Django → AI Proxy
  JSON     JSON      JSON
         (data URL) (data URL)
```

**After:**
```
Client → Django → AI Proxy
  JSON     JSON→     multipart/
         bytes     form-data
```

## Technical Details

### 1. New Utility: `parse_data_url`

**File**: `backend/apps/ai_proxy/utils.py`

Parses data URL and extracts image bytes:

```python
from apps.ai_proxy.utils import parse_data_url

image_bytes, content_type = parse_data_url("data:image/jpeg;base64,...")
# Returns: (bytes, "image/jpeg")
```

**Validation:**
- Data URL format (`data:image/{type};base64,...`)
- Content type (only JPEG/PNG)
- Base64 decoding
- Minimum size (50 bytes)

### 2. Updated AIProxyClient

**File**: `backend/apps/ai_proxy/client.py`

Changed signature from:
```python
def recognize_food(self, image_url: str, ...) -> Dict
```

To:
```python
def recognize_food(
    self,
    image_bytes: bytes,
    content_type: str,
    user_comment: Optional[str] = None,
    locale: str = "ru",
) -> Dict
```

Now sends multipart/form-data:
```python
files = {"image": ("image", image_bytes, content_type)}
data = {"locale": locale, "user_comment": user_comment}

response = httpx.post(url, headers=headers, files=files, data=data)
```

### 3. Updated AIProxyRecognitionService

**File**: `backend/apps/ai_proxy/service.py`

The service now:
1. Parses data URL → bytes using `parse_data_url()`
2. Passes bytes to client instead of data URL
3. Wraps `ValueError` in `AIProxyValidationError` for consistent error handling

```python
# Parse data URL
image_bytes, content_type = parse_data_url(image_data_url)

# Send to AI Proxy
ai_proxy_response = self.client.recognize_food(
    image_bytes=image_bytes,
    content_type=content_type,
    user_comment=final_comment,
    locale="ru",
)
```

### 4. Updated Error Handling

**File**: `backend/apps/ai/views.py`

Added handling for `AIProxyValidationError`:

```python
except AIProxyValidationError as e:
    return Response(
        {
            "error": "INVALID_IMAGE",
            "detail": "Некорректный формат изображения..."
        },
        status=400
    )
```

## Benefits

1. **No URL Length Limit**: Multipart file upload has no 2083 character URL limit
2. **Proper HTTP Semantics**: File uploads should use multipart/form-data, not JSON
3. **Better Performance**: No need to encode/decode base64 on AI Proxy side
4. **Cleaner Logs**: Image bytes are not logged, only size and content type

## Testing

Run the test script:

```bash
cd backend
python test_data_url_parsing.py
```

Expected output:
```
[OK] Success! (JPEG)
[OK] Success! (PNG)
[OK] Correctly rejected (invalid format)
[OK] Correctly rejected (invalid base64)
[OK] Correctly rejected (unsupported type)
[OK] Correctly rejected (empty data)
```

## Files Modified

1. `backend/apps/ai_proxy/utils.py` - NEW: Data URL parsing utility
2. `backend/apps/ai_proxy/client.py` - Updated to send multipart/form-data
3. `backend/apps/ai_proxy/service.py` - Updated to decode data URL
4. `backend/apps/ai/views.py` - Added AIProxyValidationError handling
5. `backend/apps/ai_proxy/README.md` - Updated documentation
6. `docs/API_DOCS.md` - Updated AI Proxy API docs

## Rollback Plan

If needed, rollback by reverting these commits. The external API contract didn't change, so clients won't be affected.

## Next Steps

1. Deploy updated Django backend
2. Verify AI Proxy accepts multipart/form-data (already implemented)
3. Monitor logs for any errors
4. Test with real images from mini-app

## Questions?

See:
- [AI Proxy README](../backend/apps/ai_proxy/README.md)
- [API Documentation](../docs/API_DOCS.md)
