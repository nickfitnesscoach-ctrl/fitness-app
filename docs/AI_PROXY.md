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

The following variables are required in the Django backend:

| Variable | Description | Default / Example |
|----------|-------------|-------------------|
| `AI_PROXY_URL` | Base URL of the AI Proxy service | `http://100.84.210.65:8001` |
| `AI_PROXY_SECRET` | Authentication secret | `Authorization: Bearer <SECRET>` |

---

## 3. Client Specifications (P0)

### Timeouts
To prevent worker exhaustion while allowing for slow LLM generation, we use specific timeouts:
- **Connect Timeout**: 5 seconds
- **Read Timeout**: 35 seconds
- **Total SLA**: Max 40 seconds per request.

### Authentication
Requests must include the secret in the header:
`Authorization: Bearer <AI_PROXY_SECRET>`

---

## 4. API & Data Contract

### Endpoint
`POST /v1/recognize` (or as configured in `client.py`)

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
Verify the proxy is alive:
`curl -H "Authorization: Bearer <SECRET>" http://<AI_PROXY_URL>/health`

### Troubleshooting
- **"401 Unauthorized"**: Check that `AI_PROXY_SECRET` matches on both sides.
- **"Empty Result"**: LLM failed to identify food. Check if image normalization stripped the content.
- **"Connection Refused"**: Check VPN (Tailscale) status and UFW firewall on the Proxy server.

---

## 8. Data Management
- **Logging**: The `trace_id` from the main backend is passed to the AI Proxy via `X-Request-ID` to allow cross-service log correlation.
- **Redaction**: Raw image bytes and provider keys are never logged in clear text.
