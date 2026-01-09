# EatFit24 Operations Runbook

**Last Updated:** 2025-12-25
**Maintainer:** DevOps Team
**Server:** eatfit24.ru (85.198.81.133)

---

## Quick Reference

### SSH Access
```bash
ssh deploy@eatfit24.ru
# Or using alias:
ssh eatfit24
```

### Project Location
```bash
/opt/eatfit24
```

### Service Status
```bash
cd /opt/eatfit24
sudo docker compose ps
```

---

## Manual Deployment (Without CI/CD)

### Prerequisites
- SSH access to `deploy@eatfit24.ru`
- Sudo password for deploy user
- Familiarity with Docker Compose

### Step-by-Step Deployment

#### 1. Connect to Server
```bash
ssh eatfit24
cd /opt/eatfit24
```

#### 2. Backup Current State
```bash
# Backup .env
cp .env .env.backup.$(date +%F_%H%M%S)

# Backup database (if needed)
mkdir -p backups
sudo docker exec eatfit24-db pg_dump -U foodmind foodmind | gzip > backups/postgres_backup_$(date +%F_%H%M%S).sql.gz

# Save current commit
git rev-parse HEAD > .last_deploy_commit
```

#### 3. Update Code
```bash
# Fetch latest changes
git fetch origin main

# Update to latest main branch
git reset --hard origin/main
```

#### 4. Verify Configuration
```bash
# Check .env exists and is valid
ls -la .env

# Check compose file
ls -la compose.yml
```

#### 5. Deploy Services
```bash
# Rebuild and restart all services
sudo docker compose up -d --build

# Monitor logs during startup
sudo docker compose logs -f
# Press Ctrl+C when services are up
```

#### 6. Verify Deployment
```bash
# Check container status (all should be "Up" and "healthy")
sudo docker compose ps

# Test backend from host
curl -i http://127.0.0.1:8000/health/

# Test public website
curl -I https://eatfit24.ru/health/
curl -I https://eatfit24.ru/
```

**Expected Results:**
- All containers: `Up X minutes (healthy)`
- `http://127.0.0.1:8000/health/` → `200 OK`
- `https://eatfit24.ru/health/` → `200 OK`
- `https://eatfit24.ru/` → `200 OK`

---

## Verification Commands (3-Command Health Check)

```bash
# 1. Container status
cd /opt/eatfit24 && sudo docker compose ps

# 2. Backend health (internal)
curl -s http://127.0.0.1:8000/health/ | jq

# 3. Public website health
curl -s https://eatfit24.ru/health/ | jq
```

**All must return healthy/200 status.**

---

## Viewing Logs

### All Services
```bash
cd /opt/eatfit24
sudo docker compose logs -f
```

### Specific Service
```bash
# Backend
sudo docker logs -f eatfit24-backend

# Bot
sudo docker logs -f eatfit24-bot

# Celery Worker
sudo docker logs -f eatfit24-celery-worker

# Celery Beat
sudo docker logs -f eatfit24-celery-beat

# Database
sudo docker logs -f eatfit24-db

# Redis
sudo docker logs -f eatfit24-redis

# Frontend
sudo docker logs -f eatfit24-frontend
```

### Last N Lines
```bash
sudo docker logs --tail 100 eatfit24-backend
```

### Nginx Logs (Host-Level)
```bash
# Error log
sudo tail -f /var/log/nginx/error.log

# Access log
sudo tail -f /var/log/nginx/access.log
```

---

## Rollback Procedure

### If Deployment Failed (Services Won't Start)

#### 1. Check Last Working Commit
```bash
cd /opt/eatfit24
cat .last_deploy_commit
# Output: <commit-hash>
```

#### 2. Rollback Code
```bash
git reset --hard <commit-hash>
```

#### 3. Restart Services
```bash
sudo docker compose up -d --build
```

#### 4. Verify
```bash
sudo docker compose ps
curl -I https://eatfit24.ru/health/
```

### If Database Issue
```bash
# List backups
ls -lh /opt/eatfit24/backups/

# Restore from backup
gunzip < backups/postgres_backup_2025-12-25_010946.sql.gz | sudo docker exec -i eatfit24-db psql -U foodmind -d foodmind
```

---

## Common Issues & Fixes

### Issue: Backend Returns 502
**Symptom:** `https://eatfit24.ru/health/` returns 502 Bad Gateway

**Diagnosis:**
```bash
# Check if backend is listening
curl -i http://127.0.0.1:8000/health/

# Check backend logs
sudo docker logs --tail 100 eatfit24-backend

# Check backend container status
sudo docker compose ps backend
```

**Fix:**
```bash
# Restart backend
sudo docker compose restart backend

# If that doesn't work, rebuild
sudo docker compose up -d --build backend
```

---

### Issue: Healthcheck Failing (Container Shows "unhealthy")
**Symptom:** `docker compose ps` shows backend as "(unhealthy)"

**Diagnosis:**
```bash
# Check healthcheck command inside container
sudo docker exec eatfit24-backend curl -f -H "Host: eatfit24.ru" http://localhost:8000/health/

# Check backend logs for errors
sudo docker logs --tail 200 eatfit24-backend | grep -i error
```

**Fix:**
Healthcheck requires Host header and `SECURE_SSL_REDIRECT=False`. Verify `.env`:
```bash
grep SECURE_SSL_REDIRECT .env
# Should output: SECURE_SSL_REDIRECT=False
```

---

### Issue: Database Connection Failed
**Symptom:** Backend logs show "could not connect to server"

**Diagnosis:**
```bash
# Check database container is running
sudo docker compose ps db

# Check database credentials match
sudo docker exec eatfit24-db psql -U foodmind -d foodmind -c '\conninfo'
```

**Fix:**
Ensure `.env` has correct credentials:
```bash
POSTGRES_DB=foodmind
POSTGRES_USER=foodmind
POSTGRES_PASSWORD=<actual-password>
```

Restart services:
```bash
sudo docker compose restart backend celery-worker celery-beat
```

---

### Issue: Port Already in Use
**Symptom:** `docker compose up` fails with "port is already allocated"

**Diagnosis:**
```bash
# Check what's using port 8000
sudo ss -lntp | grep :8000

# Check what's using port 3000
sudo ss -lntp | grep :3000
```

**Fix:**
```bash
# Stop conflicting service
sudo docker compose down

# Remove any stale containers
sudo docker ps -a | grep eatfit24

# Start fresh
sudo docker compose up -d
```

---

## Maintenance Tasks

### Update System Packages
```bash
# Update package lists
sudo apt update

# Upgrade packages
sudo apt upgrade -y

# Reboot if kernel updated
sudo reboot
```

### Clean Docker Resources
```bash
# Remove unused containers
sudo docker container prune -f

# Remove unused images
sudo docker image prune -a -f

# Remove unused volumes (⚠️ CAUTION: Don't remove active volumes!)
sudo docker volume prune -f

# Check disk usage
sudo docker system df
```

### Backup Database (Manual)
```bash
cd /opt/eatfit24
mkdir -p backups
sudo docker exec eatfit24-db pg_dump -U foodmind foodmind | gzip > backups/postgres_backup_$(date +%F_%H%M%S).sql.gz
```

---

## Security Checks

### Verify SSH Hardening
```bash
# Check SSH config
sudo grep -E "PermitRootLogin|PasswordAuthentication|PubkeyAuthentication" /etc/ssh/sshd_config

# Expected:
# PermitRootLogin no
# PasswordAuthentication no
# PubkeyAuthentication yes
```

### Check Firewall Status
```bash
sudo ufw status verbose

# Expected rules:
# 22/tcp (LIMIT)
# 80/tcp (ALLOW)
# 443/tcp (ALLOW)
```

### Check Fail2Ban
```bash
sudo fail2ban-client status sshd
```

---

## Emergency Contacts

**If you cannot resolve an issue:**
1. Check logs first (`sudo docker compose logs`)
2. Check audit report: `/opt/eatfit24/docs/audit.md`
3. Contact DevOps team with:
   - Error message
   - Relevant logs
   - Steps taken

---

## Service Restart Order (If Needed)

If you need to restart services in specific order:

```bash
cd /opt/eatfit24

# 1. Stop all
sudo docker compose down

# 2. Start infrastructure
sudo docker compose up -d db redis

# 3. Wait for health
sleep 10

# 4. Start backend
sudo docker compose up -d backend

# 5. Wait for backend health
sleep 15

# 6. Start dependent services
sudo docker compose up -d celery-worker celery-beat bot frontend
```

---

## Important Files & Locations

| File/Directory | Purpose |
|---------------|---------|
| `/opt/eatfit24/.env` | **CRITICAL** - Environment variables (secrets) |
| `/opt/eatfit24/compose.yml` | Docker Compose configuration |
| `/opt/eatfit24/backups/` | Database and .env backups |
| `/etc/nginx/sites-enabled/eatfit24.ru` | Nginx site configuration |
| `/var/log/nginx/` | Nginx logs |

---

## Notes

- **Never delete `.env` file** - it contains production secrets
- **Always backup before deploy** - use the backup commands above
- **Monitor logs during deploy** - catch issues early
- **Test both internal and public URLs** - ensure full stack works
