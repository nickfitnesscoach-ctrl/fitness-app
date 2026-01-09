# Environment Variable Contract — EatFit24

> **Status:** SSOT
> **Domain:** Configuration, Security, Portability

---

## 1. Canonical File Structure

| File | Tracked? | Purpose |
|------|----------|---------|
| `.env.example` | **Yes** | Single Source of Truth for all keys. Contains descriptions and placeholders. **No secrets.** |
| `.env.local` | No | Local development values. `DEBUG=True`, local DB, development keys. |
| `.env.prod` | No | Production values. `DEBUG=False`, strict security, real production keys. |

---

## 2. Docker Compose Integration

We avoid the generic `.env` file to prevent "double truth" and environment mixing.

### Development
```bash
docker compose -f compose.yml -f compose.dev.yml --env-file .env.local up -d
```

### Production
```bash
docker compose -f compose.yml -f compose.prod.yml --env-file .env.prod up -d
```

---

## 3. Variable Groups

### Database (PostgreSQL)
- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password

### Backend (Django)
- `SECRET_KEY`: Django secret key
- `ALLOWED_HOSTS`: Comma-separated list of domains
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of origins for frontend
- `DJANGO_SETTINGS_MODULE`: Usually `config.settings.local` or `config.settings.production`

### AI Integration
- `AI_PROXY_URL`: Internal URL of the AI Proxy service
- `AI_PROXY_SECRET`: Bearer token for authentication

### Billing (YooKassa)
- `YOOKASSA_SHOP_ID`: Shop identifier
- `YOOKASSA_SECRET_KEY`: Private API key
- `BILLING_RECURRING_ENABLED`: Toggle for auto-renew features

### Telegram Bot
- `TELEGRAM_BOT_TOKEN`: BotFather token
- `TELEGRAM_BOT_NAME`: Public username of the bot

---

## 4. Security Requirements

1. **Placeholder Hygiene**: `.env.example` must use neutral placeholders like `your-api-key`. Never leave real keys, even if they are inactive.
2. **Production Strictness**: `.env.prod` must never contain `localhost`, `test`, or `dev` values.
3. **Audit**: Periodic `grep` should be performed to ensure no secrets leaked into the git history.
4. **No `.env` in Root**: The repository must not contain a `.env` file. Only explicit `.env.local` or `.env.prod` are allowed on the server/local machine.
