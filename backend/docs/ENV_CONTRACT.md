# Environment & Settings Contract

This document defines critical rules for Django settings modules to prevent early import crashes and maintain predictable behavior.

## 🚫 Settings Module Rules

**Rule**: Settings files (`config/settings/*.py`) MUST be "data", NOT "code with side effects".

### Forbidden in Settings Modules

1. **App imports** - Never import from `apps.*` modules:
   ```python
   # ❌ FORBIDDEN
   from apps.billing.models import Subscription
   from apps.users.utils import get_user_id
   ```

2. **Heavy library imports that access settings at import time**:
   ```python
   # ❌ FORBIDDEN (if library reads settings during import)
   from rest_framework_simplejwt.settings import api_settings
   ```

3. **Computed settings that trigger early imports**:
   ```python
   # ❌ FORBIDDEN
   SIGNING_KEY = get_jwt_signing_key()  # if this imports apps.*

   # ✅ ALLOWED
   SIGNING_KEY = SECRET_KEY  # direct value, no imports
   ```

### Why This Rule Exists

**Problem**: Django settings are loaded BEFORE `django.setup()` is called. If settings code imports app modules:

1. App modules try to access `django.conf.settings`
2. Settings are still loading → **circular import**
3. Backend crashes: `ImproperlyConfigured: Requested setting SECRET_KEY, but settings are not configured`

**Example from 2026-01-09 incident**:
```python
# config/settings/base.py (OLD - BROKEN)
from rest_framework_simplejwt.settings import api_settings  # ❌
SIMPLE_JWT = {
    'SIGNING_KEY': api_settings.SIGNING_KEY,  # ❌ Triggers early import
}

# config/settings/base.py (NEW - FIXED)
SIMPLE_JWT = {
    'SIGNING_KEY': SECRET_KEY,  # ✅ Direct value, no import
}
```

## ✅ Allowed Patterns

1. **Direct environment variable reads**:
   ```python
   SECRET_KEY = os.getenv('SECRET_KEY')
   DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
   ```

2. **Built-in Python functions** (no Django imports):
   ```python
   import os
   import sys
   from pathlib import Path
   ```

3. **Static data structures**:
   ```python
   INSTALLED_APPS = [
       'django.contrib.admin',
       'apps.users',
   ]
   ```

4. **Safe library imports** (that don't access settings):
   ```python
   from datetime import timedelta
   ```

## 🧪 Smoke Test

To verify settings don't cause early import crashes, run:

```bash
# In CI or locally
docker compose exec -T backend python -c "import django; django.setup(); print('✅ Django setup OK')"

# Or in container directly
python -c "import django; django.setup(); print('✅ Django setup OK')"
```

**Expected output**: `✅ Django setup OK`

If this fails, settings likely have forbidden imports.

## 📋 Pre-Deploy Checklist

Before deploying backend changes:

1. ✅ Run migrations check: `python manage.py makemigrations --check`
2. ✅ Run smoke test: `python -c "import django; django.setup()"`
3. ✅ Review settings changes for forbidden patterns
4. ✅ Test locally with `docker compose up --build backend`

## 🔍 Historical Context

### Incident: 2026-01-09 - SECRET_KEY Early Import Crash

**Root cause**: `rest_framework_simplejwt.settings.api_settings` accessed at import time in `config/settings/base.py`

**Fix**: Replace computed `SIGNING_KEY` with direct `SECRET_KEY` reference

**Prevention**: This document + CI smoke test

See commit: `f8c075a` - "fix: defer SECRET_KEY access to prevent early import crash"

## 🚀 Deployment Contract

### Environment Setup

**Always run Docker Compose from project root**:

```bash
# ✅ CORRECT
cd /opt/eatfit24
docker compose up -d

# ❌ WRONG (uses wrong .env file)
docker compose -f /opt/eatfit24/compose.yml up -d
```

**Why**: Compose reads `.env` from current working directory. Running from wrong directory = wrong environment variables.

### Container Naming

Containers use `COMPOSE_PROJECT_NAME` prefix:

- **DEV**: `eatfit24_dev-backend-1` (with `COMPOSE_PROJECT_NAME=eatfit24_dev`)
- **PROD**: `eatfit24-backend-1` (with `COMPOSE_PROJECT_NAME=eatfit24`)

Always reference containers using current project context:
```bash
# ✅ Recommended (context-aware)
docker compose exec backend python manage.py shell

# ✅ Alternative (explicit name)
docker exec -it eatfit24-backend-1 python manage.py shell
```

### Required Environment Flags

Entrypoint expects **numeric flags** (1/0), not booleans:

```bash
# ✅ CORRECT
RUN_MIGRATIONS=1
RUN_COLLECTSTATIC=1
MIGRATIONS_STRICT=1

# ❌ WRONG
RUN_MIGRATIONS=true
RUN_COLLECTSTATIC=True
```

## 📚 Related Documentation

- [CLAUDE.md](../../CLAUDE.md) - Project overview & commands
- [backend/docs/architecture.md](../apps/billing/docs/architecture.md) - Billing architecture
- [scripts/pre-deploy-check.sh](../../scripts/pre-deploy-check.sh) - Pre-deployment validation

---

**Last updated**: 2026-01-09
**Incident reference**: SECRET_KEY early import crash (commit `f8c075a`)
