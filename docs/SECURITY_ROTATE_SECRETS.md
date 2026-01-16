# Secrets Rotation Runbook — EatFit24

> **Security:** This document describes how to rotate secrets without downtime.

---

## Secret Inventory

| Secret | Service | Location | Rotation Frequency |
|--------|---------|----------|-------------------|
| `SECRET_KEY` / `DJANGO_SECRET_KEY` | backend | `.env` | On breach or annually |
| `POSTGRES_PASSWORD` | db, backend | `.env` | On breach |
| `TELEGRAM_BOT_TOKEN` | backend, bot | `.env` | On breach (requires @BotFather) |
| `TELEGRAM_BOT_API_SECRET` | backend, bot | `.env` | On breach or quarterly |
| `YOOKASSA_SECRET_KEY` | backend | `.env` | On breach (requires YooKassa panel) |
| `AI_PROXY_SECRET` | backend, ai-proxy | `.env`, proxy config | On breach |
| `OPENROUTER_API_KEY` | bot, ai-proxy | bot `.env`, proxy | On breach or if rate limits hit |

---

## Rotation Procedures

### SECRET_KEY / DJANGO_SECRET_KEY

**Impact:** Sessions invalidated, users must re-authenticate.

**Steps:**
```bash
# 1. Generate new key
python -c "import secrets; print(secrets.token_hex(32))"

# 2. Update .env on server
nano /opt/eatfit24/.env
# Replace SECRET_KEY=old_value with new value

# 3. Restart backend (full recreate required for env reload)
cd /opt/eatfit24
docker compose up -d --force-recreate backend celery-worker celery-beat

# 4. Verify
curl -H "Host: eatfit24.ru" http://localhost:8000/health/
```

---

### POSTGRES_PASSWORD

**Impact:** DB connection fails during rotation. **Schedule maintenance window.**

**Steps:**
```bash
# 1. Generate new password
openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32

# 2. Stop all services that connect to DB
cd /opt/eatfit24
docker compose stop backend celery-worker celery-beat bot

# 3. Update password in PostgreSQL
docker compose exec db psql -U eatfit24 -c "ALTER USER eatfit24 PASSWORD 'new_password';"

# 4. Update .env
nano .env
# Change POSTGRES_PASSWORD=new_password

# 5. Restart services
docker compose up -d --force-recreate

# 6. Verify
docker compose logs backend | tail -20
curl -H "Host: eatfit24.ru" http://localhost:8000/health/
```

---

### TELEGRAM_BOT_TOKEN

**Impact:** Bot stops working immediately. **Coordinate with bot restart.**

**Steps:**
```bash
# 1. Go to @BotFather → /mybots → select bot → API Token → Revoke

# 2. Get new token from BotFather

# 3. Update .env on server
nano /opt/eatfit24/.env
# Replace TELEGRAM_BOT_TOKEN=new_token

# 4. Restart affected services
docker compose up -d --force-recreate backend bot

# 5. Verify
# Send test message to bot, check responses
docker compose logs bot --tail 50
```

---

### TELEGRAM_BOT_API_SECRET

**Impact:** Bot-to-backend internal auth fails.

**Steps:**
```bash
# 1. Generate new secret
python -c "import secrets; print(secrets.token_hex(32))"

# 2. Update .env (both services use same value)
nano /opt/eatfit24/.env
# Replace TELEGRAM_BOT_API_SECRET=new_value

# 3. Restart both services simultaneously
docker compose up -d --force-recreate backend bot

# 4. Verify
docker compose logs bot --tail 20 | grep -E "error|success"
```

---

### YOOKASSA_SECRET_KEY

**Impact:** New payments fail. **Existing payments unaffected.**

**Steps:**
```bash
# 1. Go to YooKassa merchant panel
# 2. Generate new secret key (old key is revoked)
# 3. Note: Use live_ prefix for production, test_ for testing

# 4. Update .env
nano /opt/eatfit24/.env
# Replace YOOKASSA_SECRET_KEY=live_new_key

# 5. Restart backend
docker compose up -d --force-recreate backend celery-worker

# 6. Verify (test payment flow)
# Or check webhook processing:
docker compose logs backend | grep -i yookassa
```

---

### AI_PROXY_SECRET

**Impact:** AI recognition fails.

**Steps:**
```bash
# 1. Generate new secret
python -c "import secrets; print(secrets.token_hex(32))"

# 2. Update in BOTH locations:
#    a) EatFit24 .env
#    b) AI Proxy config

# 3. Restart EatFit24 backend
docker compose up -d --force-recreate backend celery-worker

# 4. Restart AI Proxy (separate deployment)

# 5. Verify AI recognition works
curl -X POST .../api/v1/ai/recognize/...
```

---

## Emergency Breach Response

1. **Identify** which secrets may be compromised
2. **Rotate immediately** using procedures above
3. **Check audit logs** for unauthorized access
4. **Notify users** if session data may be compromised (SECRET_KEY breach)
5. **Document** incident timeline

---

## Best Practices

- ✅ Store secrets only in `.env` (not in compose files)
- ✅ Different secrets for dev and prod
- ✅ Use strong random values (32+ chars, mixed alphanumeric)
- ✅ Rotate on any suspicion of breach
- ❌ Never commit `.env` to git (already in `.gitignore`)
- ❌ Never share secrets in Telegram/email/docs
