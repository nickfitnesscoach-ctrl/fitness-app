# Security SSOT — EatFit24

> **Status:** SSOT
> **Priority:** CRITICAL

---

## 1. Secret Management

- **Zero-Trust Commit Policy**: Never commit real secrets, API keys, or certificates.
- **Environment Files**: See [ENV_SSOT.md](ENV_SSOT.md) for the authoritative configuration.
  - `.env.local` — template (in git)
  - `.env` — active file (NOT in git, created from template)
  - `.env.prod` — **FORBIDDEN**, does not exist
- **Placeholder Rule**: Use generic placeholders (e.g., `your-openai-key`).

---

## 2. Infrastructure Security

- **Network Isolation**: DB and Redis only accept connections from `eatfit24-network` Docker network.
- **Port Hygiene**:
  - `8000` (Backend): localhost only, proxied by Nginx.
  - `3000` (Frontend): localhost only, proxied by Nginx.
  - `5432/6379`: Blocked by firewall for external IPs.

---

## 3. Application Security

- **Webhook Validation**: Billing webhooks validated against provider IP ranges.
- **AI Proxy Secret**: Bearer token required for internal AI communication.
- **Tracing**: Security-sensitive requests logged with `trace_id`.

---

## 4. Audit Checklist

Perform monthly:

1. **GitHub Grep**:
   ```bash
   git grep -E "sk-|test_|:AAH|BEGIN PRIVATE KEY"
   ```
2. **Permission Review**: Check server access to `.env`.
3. **Log Scrubbing**: Verify no secrets in production logs.
