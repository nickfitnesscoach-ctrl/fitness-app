# Security SSOT — EatFit24

> **Status:** SSOT
> **Priority:** CRITICAL

---

## 1. Secret Management

- **Zero-Trust Commit Policy**: Never commit real secrets, API keys, or certificates to the repository.
- **Environment Files**: Use `.env.example` as a template. Only `.env.local` and `.env.prod` are allowed on machines (and must be `.gitignored`).
- **Placeholder Rule**: All placeholders must be generic (e.g., `your-openai-key`). Neutral formats prevent scanner false positives.

---

## 2. Infrastructure Security

- **Network Isolation**: Production database and Redis are NOT exposed to the public internet. They only accept connections from the `eatfit24-network` Docker network.
- **Port Hygiene**:
  - `8000` (Backend): Accessible only from localhost (proxied by Nginx).
  - `3000` (Frontend): Accessible only from localhost (proxied by Nginx).
  - `5432/6379`: Blocked by firewall for external IPs.

---

## 3. Application Security

- **Webhook Validation**: Billing webhooks are validated against provider IP ranges and XFF trust rules.
- **AI Proxy Secret**: Communication with the internal AI Proxy requires a Bearer token.
- **Tracing**: Every security-sensitive request (Auth, Billing) must logged with a `trace_id`.

---

## 4. Audit Checklist

Perform these checks monthly:
1. **GitHub Grep**: 
   ```bash
   git grep -E "sk-|test_|:AAH|BEGIN PRIVATE KEY"
   ```
2. **Permission Review**: Check who has access to production `.env.prod`.
3. **Log Scrubbing**: Ensure no passwords or tokens are accidentally logged in production.
