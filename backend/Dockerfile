# Dockerfile for FoodMind Django Application
# Multi-stage build for smaller production images

# ============================================================
# Stage 1: Builder - Install dependencies
# ============================================================
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --user -r requirements.txt && \
    pip install --user gunicorn psycopg2-binary dj-database-url

# ============================================================
# Stage 2: Runtime - Final lightweight image
# ============================================================
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/appuser/.local/bin:$PATH

WORKDIR /app

# Install only runtime dependencies (no gcc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -s /bin/bash appuser

# Copy installed Python packages from builder (to user's local)
COPY --from=builder /root/.local /home/appuser/.local
RUN chown -R appuser:appuser /home/appuser/.local

# Copy project files
COPY --chown=appuser:appuser . .

# Create necessary directories with proper ownership
RUN mkdir -p logs staticfiles media && chown -R appuser:appuser logs staticfiles media

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Use entrypoint script (handles migrations, collectstatic, then starts gunicorn)
ENTRYPOINT ["./entrypoint.sh"]
