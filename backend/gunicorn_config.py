"""
Gunicorn configuration для backend сервиса EatFit24.

ЗАЧЕМ НУЖЕН ЭТОТ ФАЙЛ
────────────────────
Gunicorn — это HTTP-сервер, который запускает Django в продакшене.
Этот файл описывает:
- на каком порту слушать запросы
- сколько воркеров запускать
- куда писать логи
- где хранить pid процесса
- как сервер ведёт себя при старте и перезапуске

Файл используется ТОЛЬКО в Docker-контейнере backend.

ВАЖНО ПРО БЕЗОПАСНОСТЬ
─────────────────────
Контейнер backend запускается НЕ под root, а под пользователем `appuser`.
Поэтому:
- нельзя писать файлы в /app
- pidfile и временные файлы должны быть в /tmp (он writable)

Именно для этого pidfile перенесён в /tmp.
"""

import os

# --------------------------------------------------------------------
# СЕТЬ И ПОРТ
# --------------------------------------------------------------------

# Gunicorn слушает все интерфейсы внутри контейнера на порту 8000
# Docker / Nginx проксируют трафик дальше
bind = "0.0.0.0:8000"

# Максимальное количество соединений в очереди
backlog = 2048


# --------------------------------------------------------------------
# ВОРКЕРЫ
# --------------------------------------------------------------------

# ВАЖНО: НЕ использовать cpu_count() как default!
# В Docker cpu_count() возвращает CPU хоста, не контейнера.
# Это может привести к OOM, если контейнеру выделено меньше памяти.
#
# Приоритет настройки:
# 1. WEB_CONCURRENCY (env) — стандарт для Heroku/Docker
# 2. GUNICORN_WORKERS (env) — альтернатива
# 3. _DEFAULT_WORKERS (2) — безопасный fallback
#
# Hard cap: _MAX_WORKERS (4) — защита от случайных OOM

_DEFAULT_WORKERS = 2
_MAX_WORKERS = 4


def _get_workers() -> int:
    """Get worker count from env with safe defaults and hard cap."""
    env_val = os.environ.get("WEB_CONCURRENCY") or os.environ.get("GUNICORN_WORKERS")
    if env_val:
        try:
            requested = int(env_val)
            if requested < 1:
                print(
                    f"[gunicorn] WARNING: Invalid workers={requested}, using default={_DEFAULT_WORKERS}"
                )
                return _DEFAULT_WORKERS
            if requested > _MAX_WORKERS:
                print(
                    f"[gunicorn] WARNING: Requested workers={requested} exceeds cap, using max={_MAX_WORKERS}"
                )
                return _MAX_WORKERS
            return requested
        except ValueError:
            print(
                f"[gunicorn] WARNING: Invalid WEB_CONCURRENCY/GUNICORN_WORKERS='{env_val}', using default={_DEFAULT_WORKERS}"
            )
            return _DEFAULT_WORKERS
    return _DEFAULT_WORKERS


workers = _get_workers()

# Обычные синхронные воркеры
# Подходят для Django + Celery (AI обрабатывается асинхронно)
worker_class = "sync"

# Максимальное количество одновременных соединений (для sync почти не влияет)
worker_connections = 1000

# Таймаут запроса (секунды)
# Нужен с запасом для загрузки файлов и тяжёлых API-операций
timeout = 140

# Keep-alive соединений
keepalive = 2


# --------------------------------------------------------------------
# ЛОГИ
# --------------------------------------------------------------------

"""
По умолчанию логи пишутся в stdout / stderr.
Это правильный вариант для Docker — логи читаются через `docker logs`.

Если нужно писать логи в файлы (например, для локальной отладки),
можно включить переменную окружения:

GUNICORN_LOG_TO_FILES=1
"""

LOG_TO_FILES = os.environ.get("GUNICORN_LOG_TO_FILES", "0") == "1"

if LOG_TO_FILES:
    # Требует writable /app/logs (обычно через volume)
    accesslog = "/app/logs/gunicorn_access.log"
    errorlog = "/app/logs/gunicorn_error.log"
else:
    # stdout / stderr
    accesslog = "-"
    errorlog = "-"

loglevel = "info"

access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'


# --------------------------------------------------------------------
# ПРОЦЕСС
# --------------------------------------------------------------------

# Имя процесса (удобно для логов и мониторинга)
proc_name = "eatfit24-backend"

# Gunicorn работает в foreground (норма для Docker)
daemon = False

"""
PID FILE
────────
Gunicorn при старте создаёт временный файл рядом с pidfile.

Если pidfile лежит в /app → PermissionError,
потому что контейнер работает под non-root.

Поэтому pidfile ВСЕГДА должен быть в /tmp.
"""
pidfile = "/tmp/gunicorn.pid"

# Маска прав — оставляем стандартную
umask = 0

# Пользователь и группа НЕ задаются здесь,
# они уже заданы на уровне Dockerfile (USER appuser)
user = None
group = None

# Не используем tmp_upload_dir — Django сам управляет загрузками
tmp_upload_dir = None


# --------------------------------------------------------------------
# ХУКИ (логирование жизненного цикла)
# --------------------------------------------------------------------


def on_starting(server):
    """Вызывается перед инициализацией master-процесса."""
    print("Gunicorn master process starting...")


def when_ready(server):
    """Вызывается когда сервер полностью готов."""
    print(f"Gunicorn is ready. Spawning {workers} workers")


def on_reload(server):
    """Вызывается при перезагрузке (SIGHUP)."""
    print("Gunicorn reloading...")


def post_fork(server, worker):
    """Вызывается после запуска каждого воркера."""
    print(f"Worker spawned (pid: {worker.pid})")


def worker_int(worker):
    """SIGINT / SIGQUIT — корректное завершение воркера."""
    print(f"Worker received INT or QUIT signal (pid: {worker.pid})")


def worker_abort(worker):
    """SIGABRT — аварийное завершение воркера."""
    print(f"Worker received SIGABRT signal (pid: {worker.pid})")
