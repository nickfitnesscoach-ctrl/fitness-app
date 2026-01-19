# AI Proxy SSOT — EatFit24

> **Status:** ACTIVE
> **Domain:** AI Image Recognition, LLM Bridging
> **Infrastructure:** Django Backend <-> AI Proxy (Internal) <-> OpenAI/OpenRouter

---

## 1. Overview & Architecture

The AI Proxy serves as a security and normalization bridge between the main Django backend and external LLM providers.

### Component Logic
```
[Frontend] -> [Django (apps/ai)] -> [Django (apps/ai_proxy)] -> [AI Proxy (Server)] -> [LLM]
```
- **`apps/ai`**: Handles user logic, Celery tasks, and polling.
- **`apps/ai_proxy`**: Low-level client that talks to the internal AI Proxy service.
- **AI Proxy Server**: Performs heavy lifting, image processing, and prompt engineering.

### Why a Proxy?
- **Security**: Provider API keys are hidden from the main backend.
- **Reliability**: Centralized retries and provider fallback.
- **Observability**: Unified logging for all AI requests.

---

## 2. Environment Configuration

### SSOT: Environment Variables

**RU Backend (85.198.81.133)** — `/opt/eatfit24/.env`:
- `AI_PROXY_URL` — Base URL of AI Proxy service (e.g., `http://185.171.80.128:8001`)
- `AI_PROXY_SECRET` — Authentication secret (MUST match NL proxy)

**NL AI Proxy (185.171.80.128)** — `/opt/eatfit24-ai-proxy/.env`:
- `API_PROXY_SECRET` — Authentication secret (MUST match RU backend)
- `OPENROUTER_API_KEY` — OpenRouter credentials
- `OPENROUTER_MODEL` — Model ID (e.g., `openai/gpt-5-image-mini`)

**Critical:** `AI_PROXY_SECRET` (backend) MUST equal `API_PROXY_SECRET` (proxy). Header used: `X-API-Key`.

### Quick Verification

```bash
# RU: Check secret is in container
ssh deploy@85.198.81.133
docker compose exec backend env | grep AI_PROXY_SECRET | head -c 20

# NL: Check secret is in container
ssh root@185.171.80.128
docker compose exec ai-proxy env | grep API_PROXY_SECRET | head -c 20
```

---

## 3. Client Specifications (P0)

### Timeouts
To prevent worker exhaustion while allowing for slow LLM generation, we use specific timeouts:
- **Connect Timeout**: 5 seconds
- **Read Timeout**: 35 seconds
- **Total SLA**: Max 40 seconds per request.

### Authentication
Requests must include the secret in the header:
**Header:** `X-API-Key: <AI_PROXY_SECRET>`

See [backend/apps/ai_proxy/client.py:102](../backend/apps/ai_proxy/client.py#L102) for implementation.

---

## 4. API & Data Contract

### Endpoint

**SSOT:** `backend/apps/ai_proxy/client.py:_RECOGNIZE_PATH`

`POST /api/v1/ai/recognize-food`

```bash
# Example curl (replace with real values)
curl -X POST http://185.171.80.128:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $AI_PROXY_SECRET" \
  -H "X-Request-ID: test-trace-id" \
  -F "image=@food.jpg" \
  -F "locale=ru"
```

### Standard Response Format
The `ai_proxy` module normalizes all AI responses into a unified structure:

```json
{
  "items": [
    {
      "name": "Chicken with Rice",
      "grams": 250,
      "calories": 450,
      "protein": 30.0,
      "fat": 12.5,
      "carbohydrates": 45.0,
      "confidence": 0.95
    }
  ],
  "totals": {
     "calories": 450,
     "protein": 30.0,
     "fat": 12.5,
     "carbohydrates": 45.0
  },
  "meta": {
    "request_id": "uuid",
    "model": "gpt-4o",
    "processing_time_ms": 1200
  }
}
```

### Normalization Guarantees
- **Units**: Grams are always ≥ 1.
- **Aliases**: `kcal` is mapped to `calories`, `carbs` to `carbohydrates`.
- **Value types**: All macronutrients are float or int, never `null`.

### Zone Mapping (SSOT)

**Code SSOT:** [`backend/apps/ai_proxy/constants.py`](../backend/apps/ai_proxy/constants.py)

AI Proxy may return a `zone` field indicating recognition confidence tier. Backend maps zones to error codes:

| AI Proxy Zone | Backend Error Code | User Action |
|---------------|-------------------|-------------|
| `not_food`, `no_food`, `unsupported` | `UNSUPPORTED_CONTENT` | "Попробуйте другое фото" |
| `low_confidence`, `low`, `food_possible` | `LOW_CONFIDENCE` | "Выберите блюдо вручную" |
| `food_likely` (empty items) | `EMPTY_RESULT` | "Сделать фото крупнее" |
| (no zone, confidence < threshold) | `LOW_CONFIDENCE` | "Выберите блюдо вручную" |
| (no zone, no confidence) | `EMPTY_RESULT` | Fallback |

**Config:** `settings.AI_PROXY_LOW_CONFIDENCE_THRESHOLD` (default: 0.5, clamped to [0.0, 1.0])

> [!IMPORTANT]
> When adding new zones to AI Proxy, update this table and `backend/apps/ai/tasks.py`.

---

## 5. Image Normalization SLA

- **Frequency**: Images must be normalized **exactly once** before being sent to the AI Proxy.
- **Format**: JPEG is the preferred transmission format.
- **Size**: Max 1200px on the longest side to optimize token usage and latency.

---

## 6. Error Handling

| Exception | Cause | Retryable? |
|-----------|-------|------------|
| `AIProxyValidationError` | Invalid image or parameters. | ❌ No |
| `AIProxyAuthenticationError`| Invalid/Missing `AI_PROXY_SECRET`. | ❌ No |
| `AIProxyTimeoutError` | AI Proxy took > 40s to respond. | ✅ Yes |
| `AIProxyServerError` | 5xx error or network failure. | ✅ Yes |

---

## 7. Operational Runbook

### Health Check
```bash
# Backend health
curl -s -k https://eatfit24.ru/health/ | jq .

# AI Proxy health
curl -i http://185.171.80.128:8001/health
```

### Secret Verification (Post-Deploy)
```bash
# RU Backend
ssh deploy@85.198.81.133
cd /opt/eatfit24
docker compose exec backend env | grep AI_PROXY_SECRET
# Expected: AI_PROXY_SECRET=<64-char hex>

# NL AI Proxy
ssh root@185.171.80.128
cd /opt/eatfit24-ai-proxy
docker compose exec ai-proxy env | grep API_PROXY_SECRET
# Expected: API_PROXY_SECRET=<64-char hex>

# Secrets MUST match!
```

### Troubleshooting
- **"401 Unauthorized"**: Check that `AI_PROXY_SECRET` (RU) = `API_PROXY_SECRET` (NL). Header must be `X-API-Key`.
- **"Empty Result"**: LLM failed to identify food. Check if image normalization stripped the content.
- **"Connection Refused"**: Check network RU→NL: `curl -i http://185.171.80.128:8001/health` from RU server.
- **"UPSTREAM_ERROR"**: OpenRouter credentials invalid or model unavailable. Check `OPENROUTER_API_KEY` on NL proxy.

---

## 8. Data Management
- **Logging**: The `trace_id` from the main backend is passed to the AI Proxy via `X-Request-ID` to allow cross-service log correlation.
- **Redaction**: Raw image bytes and provider keys are never logged in clear text.
