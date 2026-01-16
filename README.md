# EatFit24 — AI-Powered Fitness Platform

EatFit24 is a comprehensive ecosystem for nutrition tracking and fitness management, featuring a Telegram Mini App, an AI-driven image recognition system, and a robust billing engine.

---

## 🔗 Documentation (SSOT)

> [!IMPORTANT]
> This project follows a strict **Single Source of Truth (SSOT)** pattern. All technical documentation, architecture diagrams, and environment configurations are consolidated in the central index.

### 🗺️ [Project Index (docs/INDEX.md)](docs/INDEX.md)

| Key SSOT | Description |
|----------|-------------|
| **[Architecture](docs/ARCHITECTURE.md)** | System design, service interaction, and data flows. |
| **[Environment](docs/ENV_SSOT.md)** | Configuration contract: `.env.local` (dev), `.env` (prod). |
| **[Deployment](docs/DEPLOY.md)** | Quick start, production release, and ops runbook. |
| **[Billing](docs/BILLING.md)** | Payments, subscriptions, and recurring logic. |
| **[AI Proxy](docs/AI_PROXY.md)** | AI recognition contracts and normalization. |

---

## 🚀 Quick Start (Docker)

### 1. Configure
```bash
cp .env.example .env.local
# Edit .env.local with your secrets
```

### 2. Launch (Development)

### Start backend (DEV)
```bash
docker compose -f compose.yml -f compose.dev.yml up -d --force-recreate backend
```

⚠️ Note
If you change .env.local, a simple docker compose restart is NOT enough.
Docker does not reload env_file values on restart.

Always use:
```bash
docker compose -f compose.yml -f compose.dev.yml up -d --force-recreate backend
```


### 3. Initialize
```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```

---

## 🛠️ Tech Stack
- **Backend:** Django 5, DRF, PostgreSQL, Redis, Celery.
- **Frontend:** React, Vite, TailwindCSS (Telegram Mini App).
- **Bot:** Python/aiogram (Push notifications & Gateway).
- **AI:** Internal Proxy + GPT-4o.
- **Ops:** Docker, GitHub Actions.

---

## 👥 Support & License
Proprietary. All rights reserved. For support, refer to [docs/DEPLOY.md](docs/DEPLOY.md).
