"""
Gunicorn configuration for EatFit24 Django application.

Production configuration:
- Used in Docker containers (backend service)
- Logs to stdout/stderr by default (Docker best practice)
- Set GUNICORN_LOG_TO_FILES=1 to write logs to /app/logs/ instead
- Worker count: CPU cores * 2 + 1
- Worker class: sync (standard synchronous workers)
"""
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
# Request timeout set to 140s for long-running API operations
# Note: AI recognition processing is now handled asynchronously via Celery,
# but some API endpoints may still require extended timeout for file uploads
# and complex database operations
timeout = 140
keepalive = 2

# Logging
# Docker best practice: logs to stdout/stderr for container log collection
# Set GUNICORN_LOG_TO_FILES=1 to write to /app/logs/ instead (requires volume mount)
LOG_TO_FILES = os.environ.get("GUNICORN_LOG_TO_FILES", "0") == "1"

if LOG_TO_FILES:
    accesslog = "/app/logs/gunicorn_access.log"
    errorlog = "/app/logs/gunicorn_error.log"
else:
    accesslog = "-"  # stdout
    errorlog = "-"   # stderr

loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "eatfit24"

# Server mechanics
daemon = False
pidfile = "/app/gunicorn.pid"
umask = 0
user = None
group = None
tmp_upload_dir = None

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print("Gunicorn master process starting...")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    print("Gunicorn reloading...")

def when_ready(server):
    """Called just after the server is started."""
    print(f"Gunicorn is ready. Spawning {workers} workers")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"Worker spawned (pid: {worker.pid})")

def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    print(f"Worker received INT or QUIT signal (pid: {worker.pid})")

def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    print(f"Worker received SIGABRT signal (pid: {worker.pid})")
