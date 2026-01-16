# Archive — EatFit24

This directory contains deprecated files kept for reference.

## Files

### compose.prod.yml.deprecated

**Deprecated:** 2026-01-16

**Reason:** Conflicts with SSOT approach. The project now uses:
- `compose.yml` as production SSOT
- `compose.dev.yml` for dev overrides
- `.env` file for all environment variables

**Issues that led to deprecation:**
1. Hardcoded container names (`eatfit24-*`) conflicting with COMPOSE_PROJECT_NAME approach
2. Hardcoded Redis DB indices (`/0`) conflicting with `.env` values (`/1`, `/2`)
3. Hardcoded volume names preventing dev/prod isolation
4. Duplicate env_file reference (`.env.prod` vs `.env`)

**Current approach:** See [RUN_PROD.md](../RUN_PROD.md)
