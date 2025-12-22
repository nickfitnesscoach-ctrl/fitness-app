# Audit: apps/ai vs apps/ai_proxy

**Date:** 2024-12-22  
**Scope:** Clarify responsibilities, find duplicates/dead code, define SSOT

---

## Executive Summary

### What is `apps/ai` now?
**Business logic layer** for AI-powered food recognition:
- API endpoints (`views.py`) — HTTP API for clients
- Request/response serializers (`serializers.py`) — DTOs with validation
- Business use-cases (`services.py::recognize_and_save_meal`) — orchestration
- Async tasks (`tasks.py`) — Celery background processing
- Rate limiting (`throttles.py`) — usage control
- URL routing (`urls.py`)

### What is `apps/ai_proxy` now?
**Integration layer** — HTTP client to external AI Proxy microservice:
- HTTP client (`client.py`) — calls `POST /api/v1/ai/recognize-food`
- Response adapter (`adapter.py`) — transforms AI Proxy response to legacy format
- Exceptions (`exceptions.py`) — typed errors for client code
- Utilities (`utils.py`) — data URL parsing

### Main Issue
1. **Dead code**: `AIRecognitionService` class (~300 lines) in `apps/ai/services.py` is legacy OpenRouter integration — **never used in production**
2. **Test debt**: Tests in `apps/ai/tests.py` mock `AIRecognitionService` instead of `AIProxyRecognitionService`

### Verdict
✅ **Structure is correct**. Two directories serve different purposes:
- `apps/ai` = business logic (SSOT for AI features)
- `apps/ai_proxy` = integration client (could be `apps/ai/clients/ai_proxy/`)

---

## File Map

### apps/ai (11 files)

| File | Role | Lines | Status | Notes |
|------|------|-------|--------|-------|
| `__init__.py` | Package | - | ✅ Keep | - |
| `admin.py` | Admin | - | ✅ Keep | Django admin registration |
| `apps.py` | App config | - | ✅ Keep | Django app config |
| `models.py` | Storage | 4 | ⚠️ Empty | No models defined |
| `serializers.py` | DTO | 310 | ✅ Keep | Request/response validation |
| `services.py` | Use-case | 426 | ⚠️ Dead code | `AIRecognitionService` class is dead |
| `tasks.py` | Celery | 196 | ✅ Keep | Async recognition task |
| `tests.py` | Tests | - | ⚠️ Stale | Mocks dead `AIRecognitionService` |
| `throttles.py` | Rate limit | 67 | ✅ Keep | Per-minute/day throttling |
| `urls.py` | Routing | 17 | ✅ Keep | API routes |
| `views.py` | API | 495 | ✅ Keep | `/recognize/`, `/task/<id>/` |

### apps/ai_proxy (7 files)

| File | Role | Lines | Status | Notes |
|------|------|-------|--------|-------|
| `__init__.py` | Package | - | ✅ Keep | - |
| `adapter.py` | Adapter | 111 | ✅ Keep | Response transformation |
| `apps.py` | App config | - | ✅ Keep | Django app config |
| `client.py` | HTTP client | 299 | ✅ Keep | httpx client to AI Proxy |
| `exceptions.py` | Errors | 29 | ✅ Keep | Typed exceptions |
| `README.md` | Docs | - | ✅ Keep | - |
| `service.py` | Facade | 109 | ✅ Keep | High-level service wrapper |
| `utils.py` | Utils | 70 | ✅ Keep | Data URL parsing |

---

## Imports & Entrypoints

### Who imports `apps.ai_proxy`?

| File | Import | Purpose |
|------|--------|---------|
| `apps/ai/services.py:17` | `AIProxyRecognitionService` | Main recognition service |
| `apps/ai/tasks.py:49` | `AIProxyRecognitionService` | Async task |
| `apps/ai/views.py:24` | `AIProxyError, AIProxyValidationError, AIProxyTimeoutError` | Error handling |

### API Endpoints

| Endpoint | View | File |
|----------|------|------|
| `POST /api/v1/ai/recognize/` | `AIRecognitionView` | `apps/ai/views.py` |
| `GET /api/v1/ai/task/<task_id>/` | `TaskStatusView` | `apps/ai/views.py` |

---

## Dead Code Candidates

### 🔴 P0: `AIRecognitionService` class (apps/ai/services.py:22-319)

**Evidence:**
- Defined at line 22, ~300 lines of OpenRouter integration code
- **Never instantiated in production code**
- `recognize_and_save_meal()` (line 322) uses `AIProxyRecognitionService` instead
- Only referenced in `apps/ai/tests.py` (stale tests)

**Code flow:**
```
views.py -> recognize_and_save_meal() -> AIProxyRecognitionService (from ai_proxy)
                                     NOT -> AIRecognitionService (dead)
```

**Action:** DELETE class, update tests

### 🟡 P1: Stale tests in `apps/ai/tests.py`

**Evidence:**
- Line 15: `from apps.ai.services import AIRecognitionService`
- Lines 80, 121, 143, 220: `patch.object(AIRecognitionService, ...)`

**Action:** Update tests to mock `AIProxyRecognitionService`

### 🟢 OK: `apps/ai/models.py` (empty)

Empty models file is standard Django pattern. No action needed.

---

## Duplicates Analysis

### Schema/DTO Comparison

| Concept | apps/ai | apps/ai_proxy | AI Proxy microservice |
|---------|---------|---------------|----------------------|
| Food item | `RecognizedItemSerializer` | - (adapter transforms) | `FoodItem` (Pydantic) |
| Response | `AIRecognitionResponseSerializer` | `adapt_ai_proxy_response()` | `RecognizeFoodResponse` |
| Request | `AIRecognitionRequestSerializer` | - | multipart/form-data |

**Verdict:** ✅ No real duplication. `apps/ai_proxy/adapter.py` transforms AI Proxy schema to legacy format expected by `apps/ai`.

### Field Name Mapping

| Backend (legacy) | AI Proxy | Adapter handling |
|-----------------|----------|------------------|
| `estimated_weight` | `grams` | ✅ Mapped in adapter |
| `calories` | `kcal` or `calories` | ✅ Handles both |
| `carbohydrates` | `carbs` or `carbohydrates` | ✅ Handles both |
| `confidence` | - | ✅ Default 0.95 |

---

## Contract Compliance

### Backend vs AI Proxy Contract

| Check | Status | Notes |
|-------|--------|-------|
| Endpoint URL | ✅ OK | `/api/v1/ai/recognize-food` |
| Auth header | ✅ OK | `X-API-Key: {AI_PROXY_SECRET}` |
| Content-Type | ✅ OK | `multipart/form-data` |
| Image field | ✅ OK | `image` (bytes, JPEG/PNG) |
| Comment field | ✅ OK | `user_comment` |
| Locale field | ✅ OK | `locale` (default: "ru") |
| Response fields | ✅ OK | `items`, `total`, `model_notes` |
| Error codes | ✅ OK | 401/422/500 handled |
| X-Request-ID | ⚠️ NOT USED | Backend doesn't send/log correlation ID |

### Missing Feature: X-Request-ID
Backend client doesn't send `X-Request-ID` header. This would improve debugging/tracing across services.

---

## Decision Proposal

### Keep current structure (RECOMMENDED)

```
apps/
├── ai/                    # SSOT for AI business logic
│   ├── views.py           # API endpoints
│   ├── serializers.py     # Request/response DTOs
│   ├── services.py        # Use-cases (DELETE dead class)
│   ├── tasks.py           # Celery tasks
│   └── throttles.py       # Rate limiting
│
└── ai_proxy/              # Integration layer (HTTP client)
    ├── client.py          # HTTP client
    ├── service.py         # High-level facade
    ├── adapter.py         # Response transformation
    ├── exceptions.py      # Typed errors
    └── utils.py           # Utilities
```

### Alternative: Merge into `apps/ai/clients/`

```
apps/ai/
├── clients/
│   └── ai_proxy/
│       ├── client.py
│       ├── adapter.py
│       ├── exceptions.py
│       └── utils.py
```

**Not recommended** — current separation is clear and follows Django app conventions.

---

## Action Plan

### P0: Critical (do now)

| # | Action | File | Effort |
|---|--------|------|--------|
| 1 | Delete `AIRecognitionService` class | `apps/ai/services.py` | 5 min |
| 2 | Remove import of `AIRecognitionService` from settings if any | settings | 5 min |
| 3 | Update tests to use `AIProxyRecognitionService` | `apps/ai/tests.py` | 30 min |

### P1: Important (this sprint)

| # | Action | File | Effort |
|---|--------|------|--------|
| 4 | Add `X-Request-ID` to AI Proxy client | `apps/ai_proxy/client.py` | 15 min |
| 5 | Log correlation ID in views | `apps/ai/views.py` | 15 min |

### P2: Nice to have

| # | Action | File | Effort |
|---|--------|------|--------|
| 6 | Consider moving `ai_proxy` to `apps/ai/clients/` | - | 1 hour |
| 7 | Add integration tests for AI Proxy client | - | 2 hours |

---

## Verification

After cleanup:
1. ✅ `rg "AIRecognitionService" apps/` returns 0 matches
2. ✅ Tests pass: `python manage.py test apps.ai`
3. ✅ Production still works (uses `AIProxyRecognitionService`)
