# AI Pipeline Remediation Plan

## Status: ✅ IMPLEMENTED

All P0/P1 fixes have been applied.

---

## Implemented Fixes

### ✅ P0-2: tasks.py — Handle Controlled Errors

**Location**: `apps/ai/tasks.py:148-166`

**Change**: Added `is_error` check before DB write:
```python
if meta.get("is_error"):
    # Return error to frontend, no DB write, no usage increment
    return {"error": error_code, "error_message": ...}
```

**Effect**: 
- No garbage in DB
- No usage increment for failures
- Frontend sees clear error

---

### ✅ P0/P1: serializers.py — HEIC Support

**Location**: `apps/ai/serializers.py:28-35, 86-99, 115-126`

**Change**: 
- Added `image/heic`, `image/heif` to `ALLOWED_MIME_TYPES`
- Trust MIME for HEIC (skip unreliable byte sniffing)
- Keep byte sniffing for jpeg/png/webp

**Effect**: iPhone HEIC photos accepted, normalized by `normalize_image()`

---

### ✅ P1-1: serializers.py — Increased Limit

**Location**: `apps/ai/serializers.py:29`

**Change**: 
```python
MAX_IMAGE_BYTES = 15 * 1024 * 1024  # was 10MB
```

**Effect**: Large Android JPEGs (10-15MB) no longer rejected

---

## Verification Checklist

- [x] iPhone HEIC photo → 202 accepted
- [x] Corrupted image → Task returns error, no DB write
- [x] Android 12MB JPEG → Accepted for normalization
- [x] `meta.is_error=True` → Error returned to frontend

---

## Note on Celery Retries

HTTP retries inside `client.py` do NOT repeat normalization (uses same bytes).

Celery retry = re-runs entire task = calls `normalize_image()` again.
This is acceptable (rare, ~200ms overhead).
