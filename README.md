# FoodMind - AI Fitness Platform

**Monorepo** containing Backend (Django), Telegram Bot (aiogram), and Frontend (React/Vite) services for an AI-powered fitness lead generation and management platform.

---

## 📁 Project Structure

```
fitness-app/
├── backend/              # Django REST API
│   ├── apps/            # Django applications
│   │   ├── users/       # User management
│   │   ├── billing/     # Subscription & payments
│   │   ├── nutrition/   # Nutrition tracking
│   │   ├── telegram/    # Telegram integration
│   │   └── ai/          # AI services
│   ├── config/          # Django settings
│   ├── docs/            # Backend documentation
│   ├── Dockerfile
│   └── requirements.txt
│
├── bot/                 # Telegram Bot
│   ├── app/            # Bot application code
│   │   ├── handlers/   # Message handlers
│   │   ├── services/   # Business logic
│   │   ├── models/     # Database models
│   │   └── utils/      # Utilities
│   ├── alembic/        # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/            # React Frontend (Vite + TypeScript)
│   ├── src/
│   │   ├── components/ # React components
│   │   ├── pages/      # Page components
│   │   ├── services/   # API services
│   │   └── contexts/   # React contexts
│   ├── docs/           # Frontend documentation
│   ├── Dockerfile
│   └── package.json
│
├── docs/                # Project-wide documentation
│   ├── infra/          # Infrastructure & debug docs
│   ├── API_DOCS.md     # API documentation
│   └── project_overview.md
│
├── deploy/              # Deployment configs
│   ├── scripts/        # Deploy scripts
│   └── nginx-eatfit24.ru.conf
│
├── .github/
│   └── workflows/       # CI/CD pipelines
│       ├── backend.yml  # Backend CI/CD
│       ├── bot.yml      # Bot CI/CD
│       └── frontend.yml # Frontend CI/CD
│
├── docker-compose.yml   # Unified compose for all services
└── .editorconfig        # Code style configuration
```

### Documentation Structure

| Path | Description |
|------|-------------|
| `docs/` | Project-wide documentation |
| `docs/infra/` | Debug mode, deployment, bugfix reports |
| `backend/docs/` | Backend-specific docs, cleanup changelog |
| `frontend/docs/` | Frontend structure, archived docs |
| `deploy/` | Nginx configs, deploy scripts |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **Node.js 20+**
- **PostgreSQL 15+** (or use Docker)
- **Docker & Docker Compose** (recommended)

---

## 🐳 Run with Docker (Recommended)

### 1. Clone the repository

```bash
git clone <repo-url>
cd fitness-app
```

### 2. Setup environment variables

Create `.env` files in each service directory:

```bash
# backend/.env
cp backend/.env.example backend/.env

# bot/.env
cp bot/.env.example bot/.env
```

Edit the `.env` files with your credentials.

### 3. Start all services

```bash
docker compose up -d
```

This will start:
- **PostgreSQL** on port `5432`
- **Backend** on port `8001`
- **Bot** (no exposed port)
- **Frontend** on port `3000`

### 4. Access the services

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8001/api/v1/
- **Admin Panel:** http://localhost:8001/admin/

### 5. View logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f bot
docker compose logs -f frontend
```

### 6. Stop services

```bash
docker compose down

# Stop and remove volumes (database data)
docker compose down -v
```

---

## 💻 Local Development

### Backend (Django)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup database
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

**Access:** http://localhost:8000

### Bot (Telegram)

```bash
cd bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Apply migrations
alembic upgrade head

# Run bot
python main.py
```

### Frontend (React + Vite)

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

**Access:** http://localhost:5173

---

## 🔧 Technology Stack

| Service | Tech Stack |
|---------|-----------|
| **Backend** | Django 5.x, Django REST Framework, PostgreSQL, Gunicorn, Celery |
| **Bot** | Python 3.12, aiogram 3.x, SQLAlchemy 2.x, Alembic, OpenRouter AI |
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, React Router |
| **Database** | PostgreSQL 16 |
| **Deployment** | Docker, Docker Compose, GitHub Actions, Nginx |

---

## 🔄 CI/CD Pipeline

### Workflow Triggers

All CI/CD pipelines are located in `.github/workflows/`:

1. **Backend CI/CD** (`backend.yml`)
   - Triggers on: `backend/**` changes
   - Steps: Python setup → Tests → Docker build → Deploy to VPS
   
2. **Bot CI/CD** (`bot.yml`)
   - Triggers on: `bot/**` changes
   - Steps: Python setup → Lint → Tests → Migrations check → Deploy
   
3. **Frontend CI/CD** (`frontend.yml`)
   - Triggers on: `frontend/**` changes
   - Steps: Node setup → Build → Tests → Deploy

### Required GitHub Secrets

Add these secrets in your repository settings:

```
VPS_HOST              # Your VPS IP address
VPS_USERNAME          # SSH username (e.g., root)
VPS_SSH_KEY           # SSH private key for authentication
TELEGRAM_ADMIN_ID     # Telegram ID for deployment notifications
TELEGRAM_NOTIFICATION_TOKEN  # Bot token for sending notifications
```

---

## 🚢 Deployment

### Production Deployment on VPS

1. **SSH into your VPS:**

```bash
ssh root@your-vps-ip
```

2. **Clone the repository:**

```bash
cd /opt
git clone <repo-url> foodmind
cd foodmind
```

3. **Setup environment variables:**

```bash
# Create .env files for each service
nano backend/.env
nano bot/.env
```

4. **Start services:**

```bash
docker compose up -d --build
```

5. **Verify deployment:**

```bash
docker ps
docker compose logs -f
```

### Auto-deployment via GitHub Actions

On every push to `main` branch:
1. CI runs tests and builds
2. If tests pass, code is deployed to VPS
3. Docker containers are rebuilt and restarted
4. Telegram notification is sent

---

## 📊 Database Migrations

### Backend (Django)

```bash
# Create migration
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Rollback migration
python manage.py migrate <app_name> <migration_name>
```

### Bot (Alembic)

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## 🧪 Testing

### Backend

```bash
cd backend
python manage.py test
```

### Bot

```bash
cd bot
pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm test
```

---

## 🛠️ Useful Commands

### Docker Compose

```bash
# Build without cache
docker compose build --no-cache

# Restart specific service
docker compose restart backend

# View resource usage
docker stats

# Clean up unused images
docker system prune -a
```

### Database Access

```bash
# Access PostgreSQL inside container
docker compose exec db psql -U foodmind_user -d foodmind_db

# Backup database
docker compose exec db pg_dump -U foodmind_user foodmind_db > backup.sql

# Restore database
docker compose exec -T db psql -U foodmind_user foodmind_db < backup.sql
```

---

## 🔐 Security

- **Never commit `.env` files** - they are in `.gitignore`
- Use `.env.example` as templates
- Rotate secrets regularly
- Use strong passwords for production
- Enable HTTPS in production (use Nginx with Let's Encrypt)

---

## 📝 Environment Variables

### Backend (.env)

```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_SETTINGS_MODULE=config.settings.production
DATABASE_URL=postgres://user:password@db:5432/dbname
ALLOWED_HOSTS=your-domain.com
```

### Bot (.env)

```env
TELEGRAM_BOT_TOKEN=your-bot-token
OPENROUTER_API_KEY=your-ai-key
DB_HOST=db
DB_PORT=5432
DB_NAME=foodmind_db
DB_USER=foodmind_user
DB_PASSWORD=your-password
```

See `.env.example` files in each service for complete list.

---

## 🤝 Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes and test locally
3. Commit: `git commit -m "Add feature"`
4. Push: `git push origin feature/my-feature`
5. Create Pull Request

---

## 📄 License

Proprietary - All rights reserved

---

## 👥 Team

Developed for FoodMind AI Fitness Platform

---

## 🐛 Troubleshooting

### Port already in use

```bash
# Find process using port
lsof -i :8001  # or :3000, :5432

# Kill process
kill -9 <PID>
```

### Database connection issues

```bash
# Check database is running
docker compose ps db

# View database logs
docker compose logs db
```

### Bot not responding

```bash
# Check bot logs
docker compose logs bot

# Restart bot
docker compose restart bot
```

---

## 📞 Support

For issues, contact: support@foodmind.com
