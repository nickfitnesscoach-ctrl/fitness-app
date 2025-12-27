# AI Pipeline Audit

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Frontend (MiniApp)                                                         │
│       │                                                                     │
│       ▼ POST /api/v1/ai/recognize/                                          │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │ apps/ai/serializers.py                                          │        │
│  │  - Validates image/data_url                                     │        │
│  │  - MAX_IMAGE_BYTES = 10MB                                       │        │
│  │  - ALLOWED_MIME_TYPES = {jpeg, png, webp}  ⚠️ NO HEIC!          │        │
│  │  - Returns NormalizedImage(bytes, mime)                         │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │ apps/ai/views.py                                                │        │
│  │  - Creates Meal                                                 │        │
│  │  - Dispatches Celery task with bytes + mime                     │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│       │                                                                     │
│       ▼ Celery                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │ apps/ai/tasks.py                                                │        │
│  │  - Calls AIProxyService.recognize_food()                        │        │
│  │  - Retries on timeout/5xx (same bytes ✓)                        │        │
│  │  - ⚠️ DOES NOT CHECK meta.is_error!                             │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │ apps/ai_proxy/service.py                                        │        │
│  │  - Calls normalize_image() EXACTLY ONCE ✓                       │        │
│  │  - BEFORE base64, BEFORE retries ✓                              │        │
│  │  - Returns controlled error if action=reject ✓                  │        │
│  │  - Final assert: JPEG + ≤1024px ✓                               │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │ apps/ai_proxy/client.py                                         │        │
│  │  - multipart/form-data (NO base64 here) ✓                       │        │
│  │  - Throws exceptions for 4xx/5xx                                │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │ AI Proxy Microservice (FastAPI)                                 │        │
│  │  - Does base64 encoding internally                              │        │
│  │  - Calls OpenRouter/Claude/GPT-4V                               │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Responsibility Table

| Component | Responsibility | Validates |
|-----------|---------------|-----------|
| `serializers.py` | Anti-DoS validation | Size ≤10MB, mime type, format sniffing |
| `views.py` | HTTP handling, Meal creation | Creates Meal before task |
| `tasks.py` | Async orchestration | Celery retries on transient errors |
| `service.py` | SLA normalization | JPEG, ≤1024px, action-based |
| `client.py` | HTTP transport | Multipart, timeouts, error mapping |
| `adapter.py` | Response normalization | Field mapping, grams≥1 |
| `utils.py` | Image normalization | Format, size, EXIF, alpha |

---

## Findings

### P0 — Critical (Breaks SLA/Security/Data)

#### P0-1: HEIC Rejected in Serializer Before SLA Normalization

**Location**: `apps/ai/serializers.py:31`

```python
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
```

**Problem**: `image/heic` and `image/heif` are NOT in allowed list. Serializer rejects HEIC uploads BEFORE they reach `normalize_image()` which SUPPORTS HEIC via `pillow-heif`.

**Impact**: iPhone users sending HEIC photos get validation error instead of automatic conversion.

**Conflict**: `utils.py` has `HEIF_SUPPORTED=True` but never gets called for HEIC.

---

#### P0-2: Controlled Error Not Detected in Tasks

**Location**: `apps/ai/tasks.py:144-146`

```python
items = result.items
totals = result.totals
meta = result.meta
```

**Problem**: Task does NOT check `meta.is_error`. When `service.py` returns controlled error:
```python
RecognizeFoodResult(items=[], totals={}, meta={"is_error": True, "error_code": "..."})
```

Task treats it as "nothing recognized" and saves empty items to DB.

**Impact**: 
- User sees "success" with 0 items instead of clear error
- Daily usage counter incremented for failed requests
- DB contains orphan Meals with no items

---

### P1 — Important (Affects Stability/UX)

#### P1-1: 10MB Limit May Reject Large Android JPEGs

**Location**: `apps/ai/serializers.py:29`

```python
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB
```

**Problem**: Modern Android phones produce JPEGs 8-15MB. Users may get "file too large" before normalization can resize them.

**Impact**: Some valid photos rejected unnecessarily.

---

#### P1-2: Byte Sniffing Doesn't Detect HEIC

**Location**: `apps/ai/serializers.py:48-56`

```python
def _detect_mime_from_bytes(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    # ... no HEIC signature check
```

**Problem**: Even if HEIC added to `ALLOWED_MIME_TYPES`, byte sniffing will return `None` and reject it.

---

### P2 — Code Quality/Maintainability

#### P2-1: Duplicate request_id Generation

**Locations**:
- `apps/ai/views.py:43-44`: `_new_request_id()`
- `apps/ai_proxy/utils.py:33-42`: `new_request_id()`

**Problem**: Two identical functions exist.

---

#### P2-2: content_type Normalization Done Twice

**Locations**:
- `serializers.py:65`: `mime = m.group("mime").lower().strip()`
- `utils.py:134`: `ct_raw = (content_type or "unknown").lower().split(";")[0].strip()`

**Observation**: Both normalize content_type — this is actually OK (defense in depth), but inconsistent (one strips `;`, other doesn't).

---

## SLA Invariant Verification

| Invariant | Status | Evidence |
|-----------|--------|----------|
| `normalize_image()` called exactly once | ✅ PASS | Only in `service.py:75` |
| Normalization before base64 | ✅ PASS | Client uses multipart, no base64 |
| No HEIC/PNG/WebP to microservice | ⚠️ PARTIAL | Service OK, but HEIC rejected upstream |
| Controlled error stops client call | ✅ PASS | `action=reject` returns before client |
| Retries use same normalized bytes | ✅ PASS | Celery retries don't re-call service |
| No image bytes in logs | ✅ PASS | Only metrics logged |

---

## Security Check

| Check | Status |
|-------|--------|
| API key not logged | ✅ |
| Image bytes not logged | ✅ |
| base64 not logged | ✅ |
| request_id propagates | ✅ |
| Stack traces not in user errors | ✅ |
