# Deployment & Operations — EatFit24

> **Status:** SSOT
> **Domain:** DevOps, Infrastructure, Lifecycle

---

> [!IMPORTANT]
> ## SSOT Rule
> Docker Compose **always reads `.env`** — this is the only active environment file.
> Other env files (`.env.local`, `.env.example`) are **templates only**.
>
> ❌ `--env-file .env.local` — **FORBIDDEN**
> ❌ `--env-file .env.prod` — **FORBIDDEN**

---

## 1. Local Development (Quick Start)

### Requirements
- Docker & Docker Compose
- Python 3.11+ (for local IDE support)
- uv (preferred package manager)

### Commands
1. **Setup Env**:
   ```bash
   cp .env.local .env
   # Edit .env with your keys if needed (replace REPLACE_ME placeholders)
   ```
2. **Start Services**:
   ```bash
   docker compose -f compose.yml -f compose.dev.yml up -d
   ```
3. **Database Migrations**:
   ```bash
   docker compose exec backend python manage.py migrate
   ```

---

## 2. Production Deployment

### Infrastructure
- **Cloud Provider**: Timeweb Cloud / Other VPS
- **OS**: Ubuntu 22.04 LTS
- **Network**: Tailscale (for internal AI Proxy communication)

### Deployment Steps
1. **Pull latest code**: `git pull origin main`
2. **Verify Environment**: Ensure `.env` has production values.
   ```bash
   grep -E "APP_ENV|POSTGRES_DB|YOOKASSA_MODE|DEBUG" .env
   # Expected: APP_ENV=prod, POSTGRES_DB=eatfit24, YOOKASSA_MODE=prod, DEBUG=false
   ```
3. **Deploy**:
   ```bash
   docker compose up -d --build
   ```
4. **Automatic Migrations**: Handled by the `backend` container's entrypoint.

---

## 3. CI/CD (GitHub Actions)

We use a multi-stage pipeline:
- **Linting**: Ruff and Black for Python, ESLint for JS.
- **Testing**: `pytest` for backend apps (Billing, AI Proxy, Core).
- **Security Audit**: Automated `grep` for secrets and tokens.

---

## 4. Troubleshooting & Disaster Recovery

### Logs
- **Combined**: `docker compose logs -f`
- **Specific**: `docker compose logs -f backend`

### Database Backups
Automated nightly dumps are stored in `/var/lib/eatfit24/backups/` and rotated weekly.

### Common Issues
- **Redis Connection**: If workers fail to pick up tasks, check `CELERY_BROKER_URL` in `.env` (prod: `redis://redis:6379/1`).
- **Media Permissions**: Ensure `/var/lib/eatfit24/media` is owned by the user running Docker.
- **Env not applied after change**: Use `docker compose up -d --force-recreate backend` (not `restart`).

---

## 5. Forbidden (Legacy)

| Item | Status | Notes |
|------|--------|-------|
| `compose.prod.yml` | **DEPRECATED** | Use `compose.yml` |
| `.env.prod` | **FORBIDDEN** | Use `.env` |
| `--env-file` flag | **FORBIDDEN** | Docker reads `.env` by default |
