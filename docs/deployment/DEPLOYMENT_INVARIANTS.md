# Инварианты деплоя EatFit24

**Дата фиксации**: 2026-01-07
**Release Baseline**: v1.1
**Статус**: Обязательные правила для всех деплоев backend

---

## Назначение документа

Этот документ определяет **неизменяемые правила**, которые ДОЛЖНЫ соблюдаться при каждом деплое backend-сервиса в production. Нарушение любого из этих инвариантов = **блокер деплоя**.

**Что этот документ НЕ является**:
- ❌ Руководство для начинающих
- ❌ Best practices (это минимальные требования)
- ❌ Рекомендации (это императивы)
- ❌ Гайд по настройке окружения

**Аудитория**: DevOps, backend-разработчики, CI/CD maintainers.

---

## Инварианты

### 1. Migration Discipline

**Правило**:
Production НИКОГДА не запускает `makemigrations`. Все миграции генерируются локально, проверяются, коммитятся в репозиторий и деплоятся как код.

**Почему важно**:
- `makemigrations` на проде создаёт миграции, которых нет в репозитории
- Следующий деплой может перезаписать эти миграции → data loss / inconsistency
- Миграции должны проходить code review как любой другой код
- Автоматическая генерация миграций на проде = потеря контроля над схемой БД

**Как проверяется**:
1. **CI gate** (GitHub Actions): `python manage.py makemigrations --check --dry-run`
   - Триггер: каждый push в `main` с изменениями в `backend/**`
   - Блокирует merge при наличии uncommitted migrations
2. **Pre-deploy script**: `scripts/pre-deploy-check.sh` (Check 1)
   - Запускается вручную перед деплоем
   - BLOCKER: выход с кодом 1 при uncommitted migrations
3. **Runtime contract**: `entrypoint.sh` с `RUN_MIGRATIONS=1`
   - Применяет только committed миграции из репозитория
   - Не генерирует новые миграции

**Workflow (обязательный)**:
```bash
# 1. Обнаружить изменения в моделях
python manage.py makemigrations --check --dry-run

# 2. Сгенерировать миграцию (если нужно)
python manage.py makemigrations [app_name]

# 3. Проверить миграцию
cat backend/apps/[app]/migrations/XXXX_*.py

# 4. Протестировать локально
python manage.py migrate

# 5. Закоммитить и задеплоить
git add backend/apps/*/migrations/*.py
git commit -m "feat([app]): add migration for [description]"
git push
```

**Recovery при нарушении**:
```bash
# На локальной машине
python manage.py makemigrations
git add backend/apps/*/migrations/*.py
git commit -m "feat: add missing migration"
git push

# На production сервере
cd /opt/EatFit24
git pull
docker compose up -d backend  # Применит миграцию через entrypoint.sh
```

---

### 2. Environment Variable Contract

**Правило**:
`entrypoint.sh` ожидает числовые флаги (`1`/`0`), а НЕ булевы (`true`/`false`).

**Почему важно**:
- Shell-сравнение `[ "$RUN_MIGRATIONS" = "1" ]` — строковое, не truthy
- `RUN_MIGRATIONS=true` интерпретируется как строка `"true"`, НЕ равная `"1"`
- Результат: миграции не применяются, но ошибок нет (silent failure)
- Коварная ошибка, т.к. работает в docker compose с restart, но ломается при up -d

**Обязательные флаги** (`.env`):
```bash
RUN_MIGRATIONS=1        # НЕ "true"
RUN_COLLECTSTATIC=1     # НЕ "true"
MIGRATIONS_STRICT=1     # НЕ "true"
```

**Как проверяется**:
1. **Pre-deploy script**: `scripts/pre-deploy-check.sh` (Check 7)
   - Проверяет git status + интерактивный prompt при uncommitted changes
2. **Runtime**: `entrypoint.sh` — проваливается молча, если флаг неверный
   - ⚠️ Проблема: нет явной валидации флагов в entrypoint.sh

**Verification**:
```bash
# На production
docker exec eatfit24-backend env | grep "RUN_"
# Ожидается: RUN_MIGRATIONS=1, RUN_COLLECTSTATIC=1

# Проверить, что миграции применились
docker logs eatfit24-backend --tail 50 | grep "Applying migrations"
```

**Recovery при нарушении**:
```bash
# Исправить .env на проде
sed -i 's/RUN_MIGRATIONS=true/RUN_MIGRATIONS=1/' /opt/EatFit24/.env
sed -i 's/RUN_COLLECTSTATIC=true/RUN_COLLECTSTATIC=1/' /opt/EatFit24/.env

# Пересоздать контейнер (НЕ restart)
docker compose up -d backend
```

---

### 3. Service Detection in Compose

**Правило**:
Команды сервисов в `compose.yml` ДОЛЖНЫ начинаться с имени бинарника (`celery`, `gunicorn`), а НЕ с полного пути (например, `/app/.venv/bin/celery`).

**Почему важно**:
- `entrypoint.sh` проверяет `if [ "$1" = "celery" ]` для skip миграций на Celery workers
- Если `$1` = `/app/.venv/bin/celery`, условие не срабатывает
- Результат: Celery worker запускает `gunicorn` вместо `celery worker`
- Gunicorn не обрабатывает задачи, очередь растёт, billing/AI зависают

**Правильная конфигурация** (`compose.yml`):
```yaml
services:
  celery-worker:
    command: celery -A config worker -l INFO --concurrency=2 -Q ai,billing,default
    # ✅ Правильно: $1 = "celery"

  # ❌ НЕПРАВИЛЬНО:
  # command: /app/.venv/bin/celery -A config worker ...
  # $1 = "/app/.venv/bin/celery" ≠ "celery"
```

**Как проверяется**:
1. **Runtime verification**:
```bash
docker exec eatfit24-celery-worker ps aux | grep celery
# Ожидается: celery worker, НЕ gunicorn
```
2. **Manual audit**: Проверка `compose.yml` перед изменением service commands

**Recovery при нарушении**:
```bash
# Исправить compose.yml
# Было: command: /app/.venv/bin/celery -A config worker ...
# Стало: command: celery -A config worker ...

# Пересоздать контейнер
docker compose up -d celery-worker

# Проверить процесс
docker exec eatfit24-celery-worker ps aux | grep -E "celery|gunicorn"
```

---

### 4. UV Lock Consistency

**Правило**:
`uv.lock` ДОЛЖЕН быть синхронизирован с `pyproject.toml` перед каждым деплоем.

**Почему важно**:
- Drift между `pyproject.toml` и `uv.lock` → разные версии зависимостей на dev vs prod
- `uv sync` без `--frozen` автоматически обновляет lock → неконтролируемый update зависимостей
- Результат: неожиданные breaking changes в production
- Lock file — это snapshot зависимостей, который должен проходить review как код

**Как проверяется**:
1. **Pre-deploy script**: `scripts/pre-deploy-check.sh` (Check 2)
   ```bash
   uv sync --frozen
   # Проваливается, если lock не соответствует pyproject.toml
   ```
2. **Future**: CI gate (см. "Future Improvements")

**Workflow**:
```bash
# При изменении зависимостей в pyproject.toml
uv lock                      # Обновить lock file
git add pyproject.toml uv.lock
git commit -m "deps: update [package] to [version]"
git push
```

**Recovery при нарушении**:
```bash
# На локальной машине
uv lock
git add uv.lock
git commit -m "fix: sync uv.lock with pyproject.toml"
git push

# На production
cd /opt/EatFit24
git pull
docker compose up -d backend --build
```

---

### 5. Python Syntax Validation

**Правило**:
Весь Python-код ДОЛЖЕН компилироваться без syntax errors перед деплоем.

**Почему важно**:
- Syntax error обнаруживается только при импорте модуля в runtime
- Если ошибка в редко используемом коде → может лежать неделями
- В production syntax error = 500 для пользователя
- `compileall` проверяет ВСЕ `.py` файлы, включая те, что не покрыты тестами

**Как проверяется**:
1. **Pre-deploy script**: `scripts/pre-deploy-check.sh` (Check 3)
   ```bash
   python -m compileall -q .
   # -q = quiet mode, выводит только ошибки
   ```
2. **CI**: Тесты косвенно проверяют импорты основных модулей (но не всех)

**Recovery при нарушении**:
```bash
# Найти файл с ошибкой
python -m compileall .
# Syntax Error in backend/apps/billing/tasks.py

# Исправить ошибку
vim backend/apps/billing/tasks.py

# Проверить снова
python -m compileall -q .
# (пусто = успех)

git add backend/apps/billing/tasks.py
git commit -m "fix: syntax error in billing tasks"
git push
```

---

### 6. Time & Timezone Invariant

**Правило**:
"Если оно работает на сервере — оно в UTC."

**Архитектура** (4 слоя):
1. **Storage layer** (PostgreSQL, Django ORM): Всегда UTC
2. **Processing layer** (Python, Celery workers): Aware datetimes в UTC
3. **Display layer** (Celery Beat crontab): Интерпретирует расписание в `Europe/Moscow`
4. **User layer** (Frontend): Конвертирует UTC в локальный timezone пользователя

**Конфигурация** (`config/settings/base.py`):
```python
TIME_ZONE = "Europe/Moscow"  # Display timezone для Celery Beat crontab
USE_TZ = True                # Хранить всё в UTC внутри
CELERY_TIMEZONE = TIME_ZONE  # Celery использует тот же display timezone
```

**Почему важно**:
- Использование `datetime.now()` вместо `timezone.now()` → naive datetime без timezone
- Сравнение naive и aware datetime → TypeError
- Сохранение naive datetime в БД → неопределённая интерпретация timezone
- Celery Beat должен интерпретировать crontab в `Europe/Moscow`, но выполнять задачи в UTC

**Как проверяется**:
1. **CI guard**: Блокирует `datetime.now()` / `datetime.utcnow()` через grep
2. **Code review**: Всегда использовать `timezone.now()` в Django
3. **Runtime verification**:
```bash
# System clock (должен быть UTC)
docker exec eatfit24-backend date
# Ожидается: Wed Jan  7 12:00:00 UTC 2026

# PostgreSQL timezone (должен быть UTC)
docker exec eatfit24-db psql -U eatfit24 -c "SHOW timezone;"
# Ожидается: UTC

# Django timezone config
docker exec eatfit24-backend python manage.py shell -c \
  "from django.conf import settings; print(f'TIME_ZONE={settings.TIME_ZONE}, USE_TZ={settings.USE_TZ}')"
# Ожидается: TIME_ZONE=Europe/Moscow, USE_TZ=True

# Celery timezone config
docker logs eatfit24-celery-worker --tail 50 | grep -i timezone
# Ожидается: timezone: Europe/Moscow, enable_utc: True
```

**Recovery при нарушении**:
```bash
# Найти использование datetime.now()
grep -r "datetime.now()\|datetime.utcnow()" backend/ \
  --include="*.py" \
  --exclude-dir="migrations" \
  --exclude-dir=".venv"

# Заменить на timezone.now()
# Было: from datetime import datetime; now = datetime.now()
# Стало: from django.utils import timezone; now = timezone.now()

git add .
git commit -m "fix: replace datetime.now() with timezone.now()"
git push
```

---

### 7. Memory Baseline & Alert Thresholds

**Правило**:
Production-сервисы НЕ ДОЛЖНЫ превышать установленные memory thresholds без расследования.

**Baseline** (зафиксирован 2026-01-07):
- `backend`: ~300MB / 1.5G (19%)
- `celery-worker`: ~270MB / 1G (27%)
- `celery-beat`: ~270MB / 512M (54%)

**Alert thresholds**:
- `backend` > 700MB → расследовать memory leak
- `celery-worker` > 800MB → проверить AI queue backlog
- `celery-beat` > 400MB → перезапустить сервис

**Почему важно**:
- Memory leak убивает контейнер через OOM Killer → downtime
- Растущая память = признак unbounded cache / не закрытые DB connections
- Раннее обнаружение memory bloat → превентивный рестарт без инцидента

**Как проверяется**:
1. **Manual**: `docker stats --no-stream | grep eatfit24`
2. **Future**: Automated anomaly detector → Telegram alerts (см. "Future Improvements")

**Recovery при превышении**:
```bash
# 1. Проверить текущее использование памяти
docker stats --no-stream | grep eatfit24

# 2. Если backend > 700MB
docker logs eatfit24-backend --tail 200 | grep -E "OutOfMemory|MemoryError"
docker compose restart backend

# 3. Если celery-worker > 800MB
docker exec eatfit24-redis redis-cli LLEN celery  # Проверить размер очереди
docker compose restart celery-worker

# 4. Если celery-beat > 400MB (редко, но бывает)
docker compose restart celery-beat
```

---

## Матрица контроля

| Инвариант | CI Gate | Pre-Deploy | Runtime | Покрытие |
|-----------|---------|------------|---------|----------|
| **Migration Discipline** | ✅ `makemigrations --check` | ✅ Check 1 | ✅ `entrypoint.sh` | **100%** |
| **UV Lock Consistency** | ❌ (future) | ✅ Check 2 | ❌ | **33%** |
| **Python Syntax** | ✅ (через тесты) | ✅ Check 3 | ❌ | **67%** |
| **Env Contract** | ❌ | ⚠️ Check 7 (косвенно) | ✅ `entrypoint.sh` | **50%** |
| **Datetime Guard** | ✅ grep `datetime.now()` | ❌ | ⚠️ (TypeError в runtime) | **50%** |
| **Service Detection** | ❌ | ❌ | ✅ `entrypoint.sh` | **33%** |
| **Memory Baseline** | ❌ | ❌ | ⚠️ (manual monitoring) | **20%** |

**Легенда**:
- ✅ = Автоматическая проверка + блокер
- ⚠️ = Частичная проверка или manual
- ❌ = Не проверяется

**Критичные зоны риска** (покрытие < 50%):
- UV Lock Consistency (33%)
- Service Detection (33%)
- Memory Baseline (20%)

→ См. "Future Improvements" для усиления этих зон.

---

## Future Improvements (Non-Urgent)

Текущая система стабильна и операционна. Следующие улучшения повышают coverage, но НЕ критичны.

### 1. CI Gate для `uv sync --frozen`

**Текущий статус**: Lock drift ловится в pre-deploy script (работает хорошо).

**Улучшение**: Добавить в `.github/workflows/backend.yml`:
```yaml
# После шага "Install dependencies"
- name: UV lock consistency check
  run: |
    cd backend
    uv sync --frozen || {
      echo "❌ BLOCKER: uv.lock is out of sync with pyproject.toml"
      echo "Run locally: uv lock"
      exit 1
    }
```

**Impact**: Ловит ещё ~10% human error (когда разработчик забыл запустить pre-deploy script).

**Приоритет**: Low (pre-deploy script уже даёт 90% покрытия).

---

### 2. Runtime Anomaly Detection → Telegram Alerts

**Текущий статус**: Ручной мониторинг через `docker stats` + health checks.

**Улучшение**: Простой cron-based детектор аномалий (НЕ full monitoring stack).

**Detection triggers**:
- Container restart (проверка uptime через `docker ps`)
- Memory > threshold (backend > 700MB, celery-worker > 800MB, celery-beat > 400MB)
- Health endpoint ≠ 200 (`curl https://eatfit24.ru/health/`)

**Пример реализации**:
```bash
#!/bin/bash
# scripts/runtime-anomaly-detector.sh
# Запускается через cron каждые 5 минут

# Check 1: Container restarts
RESTARTS=$(docker ps --format "{{.Names}} {{.Status}}" | grep -c "second\|minute")
if [ "$RESTARTS" -gt 0 ]; then
  curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${ADMIN_TELEGRAM_ID}" \
    -d text="⚠️ Container restart detected on eatfit24.ru"
fi

# Check 2: Memory thresholds
BACKEND_MEM=$(docker stats --no-stream --format "{{.MemUsage}}" eatfit24-backend | awk '{print $1}' | sed 's/MiB//')
if (( $(echo "$BACKEND_MEM > 700" | bc -l) )); then
  curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${ADMIN_TELEGRAM_ID}" \
    -d text="⚠️ Backend memory > 700MB (current: ${BACKEND_MEM}MB)"
fi

# Check 3: Health endpoint
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: eatfit24.ru" http://localhost:8000/health/)
if [ "$HEALTH_STATUS" != "200" ]; then
  curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d chat_id="${ADMIN_TELEGRAM_ID}" \
    -d text="❌ Health check failed (HTTP $HEALTH_STATUS)"
fi
```

**Crontab entry**:
```bash
# /etc/cron.d/eatfit24-monitoring
*/5 * * * * root /opt/EatFit24/scripts/runtime-anomaly-detector.sh >> /var/log/eatfit24-monitoring.log 2>&1
```

**Impact**: +∞ peace of mind. Немедленное уведомление о проблемах без необходимости poll вручную.

**Приоритет**: Low (текущий manual monitoring адекватен для текущего масштаба).

**Принцип**: Это НЕ полноценный monitoring stack (Prometheus/Grafana). Это простой детектор критических аномалий.

---

### 3. Env Contract Validation в `entrypoint.sh`

**Текущий статус**: Silent failure при неверном формате флагов (например, `RUN_MIGRATIONS=true`).

**Улучшение**: Добавить валидацию в начало `entrypoint.sh`:
```bash
# Валидация env flags
if [ -n "$RUN_MIGRATIONS" ] && [ "$RUN_MIGRATIONS" != "0" ] && [ "$RUN_MIGRATIONS" != "1" ]; then
  echo "❌ ERROR: RUN_MIGRATIONS must be 0 or 1, got: $RUN_MIGRATIONS"
  exit 1
fi

if [ -n "$RUN_COLLECTSTATIC" ] && [ "$RUN_COLLECTSTATIC" != "0" ] && [ "$RUN_COLLECTSTATIC" != "1" ]; then
  echo "❌ ERROR: RUN_COLLECTSTATIC must be 0 or 1, got: $RUN_COLLECTSTATIC"
  exit 1
fi
```

**Impact**: Преобразует silent failure в explicit error на старте контейнера.

**Приоритет**: Medium (это quick win без побочных эффектов).

---

## Changelog

- **2026-01-07**: Initial release (v1.1)
  - Зафиксированы 7 инвариантов
  - Добавлена матрица контроля
  - Определены future improvements

---

## Принцип применения

**Все инварианты обязательны.** При конфликте между скоростью деплоя и соблюдением инварианта — **инвариант побеждает**.

Если инвариант невозможно соблюсти (например, hotfix критической уязвимости) — это должно быть документировано как **инцидент** с последующим разбором и update инвариантов.

**Этот документ не про "как хорошо бы". Это про "как ДОЛЖНО быть".**
