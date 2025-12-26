# Используем официальный Python образ
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости системы
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    dos2unix \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаём non-root пользователя для безопасности
RUN useradd -m -s /bin/bash appuser

# Копируем весь проект с правильными правами
COPY --chown=appuser:appuser . .

# Создаём директорию для логов
RUN mkdir -p logs && chown -R appuser:appuser logs

# Копируем и делаем исполняемым entrypoint скрипт
COPY entrypoint.sh /entrypoint.sh
RUN dos2unix /entrypoint.sh && chmod +x /entrypoint.sh

# Переключаемся на non-root пользователя
USER appuser

# Используем ENTRYPOINT для запуска
ENTRYPOINT ["/entrypoint.sh"]
