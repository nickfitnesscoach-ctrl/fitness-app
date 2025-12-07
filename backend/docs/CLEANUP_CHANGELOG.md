# EatFit24 Project Cleanup — December 2025

---

# Backend Cleanup

## Summary

Root directory cleanup of `backend/` to remove unused files and caches.

## Removed

| File | Reason |
|------|--------|
| `__pycache__/` | Python bytecode cache (should never be in git) |
| `.pytest_cache/` | pytest cache (should never be in git) |
| `check_db_data.py` | Legacy diagnostic script, not used in Docker/CI/infra |
| `nginx.conf` | Unused Nginx config for Docker-internal nginx (project uses host nginx via `deploy/nginx-eatfit24.ru.conf`) |

## Kept

| File | Reason |
|------|--------|
| `nginx-host.conf` | Reference config for host-based Nginx setup (localhost:8001 → Django) |
| `pyproject.toml` | Contains **ruff** linter configuration (not Poetry) |
| `.env.example` | Actual environment template for EatFit24 backend |
| `gunicorn_config.py` | Gunicorn production settings |
| `entrypoint.sh` | Docker entrypoint script |
| `Dockerfile` | Backend container build |
| `requirements.txt` | Python dependencies |
| `manage.py` | Django management script |

## Ignore Files Status

### `.gitignore` — OK
Already ignores:
- `__pycache__/`, `*.py[cod]`
- `*.sqlite3`
- `.env`, `*.env.local`
- `logs/`, `media/`, `staticfiles/`
- `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`

### `.dockerignore` — OK
Already ignores:
- `__pycache__/`, `*.py[cod]`
- `.env`, `.env.local`
- `*.sqlite3`
- `.pytest_cache/`, `.coverage`
- `docs/`, `*.md`
- `.git/`, `.github/`

## Infrastructure Notes

- **Database**: PostgreSQL via Docker Compose (no SQLite)
- **Nginx**: Host-based nginx using `deploy/nginx-eatfit24.ru.conf` for production
- **Dependencies**: Managed via `pip install -r requirements.txt` (no Poetry)
- **Linting**: ruff configured in `pyproject.toml`

---

# Frontend Cleanup

## Summary

Root directory cleanup of `frontend/` to remove unused files, backups, and outdated documentation.

## Removed

| File/Directory | Reason |
|------|--------|
| `.agent/` | Agent workflow cache directory |
| `audit_logs/` | Empty directory |
| `Dockerfile.backup` | Outdated backup, current `Dockerfile` is up to date |
| `nginx.conf.backup` | Outdated backup, current `nginx.conf` is up to date |
| `AUDIT_REPORT_TEMPLATE.md` | Unused audit report template |
| `BUGFIX_ROADMAP.md` | Outdated bugfix roadmap (2025-12-06) |
| `BUGS_TRACKER.csv` | Bug tracker file (should be in GitHub Issues) |
| `FRONTEND_AUDIT_TZ.md` | Completed audit task specification |
| `roadmap.md` | Outdated roadmap (all tasks completed) |
| `DEPLOY.md` | Outdated deploy docs (CI/CD via GitHub Actions) |
| `deploy.sh` | Legacy deploy script (GitHub Actions in use) |

## Archived (moved to `docs/archive/`)

| File | Reason |
|------|--------|
| `AI_PROMPT.md` | Reference documentation |
| `API_COMPATIBILITY_CHECK.md` | API compatibility notes |
| `FRONTEND_API_SCHEMA.md` | API schema documentation |
| `FRONTEND_AUDIT.md` | Audit results |
| `FRONTEND_REACT_EXAMPLES.md` | React code examples |
| `REFACTORING_CHANGELOG.md` | Refactoring history |

## Kept

| File | Reason |
|------|--------|
| `nginx.conf` | Production nginx config (used in Dockerfile) |
| `nginx.local.conf` | Local development nginx config |
| `Dockerfile` | Frontend container build |
| `.env.example` | Environment template |
| `.env.development` | Development environment |
| `.env.production` | Production environment |
| `README.md` | Project documentation |
| `package.json` | Node.js dependencies |
| `vite.config.js` | Vite build configuration |
| `tailwind.config.js` | Tailwind CSS configuration |
| `tsconfig.json` | TypeScript configuration |
| `eslint.config.js` | ESLint configuration |

## Ignore Files Status

### `.gitignore` — OK
Already ignores:
- `node_modules/`, `dist/`, `build/`
- `.env`, `.env.*` (except `.env.example`)
- `*.log`, `logs/`
- `.cache/`, `*_backup`

### `.dockerignore` — OK
Already ignores:
- `node_modules/`, `dist/`
- `.env`, `.env.local`
- `*.log`

## Infrastructure Notes

- **Build**: Vite + React + TypeScript
- **Styling**: Tailwind CSS
- **Deploy**: GitHub Actions → Docker on VPS
- **Nginx**: `nginx.conf` used inside Docker container for SPA routing
