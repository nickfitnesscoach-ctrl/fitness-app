# Ops / Health — EatFit24

Эта папка содержит **операционные скрипты для продакшена**.

> **ВАЖНО:**
> Некоторые скрипты ТОЛЬКО проверяют состояние,
> другие — МЕНЯЮТ систему. Смотри описание ниже.

---

## Безопасные проверки (read-only)

### check-prod-smoke.sh

**Быстрая проверка продакшена после деплоя**

Что делает:
- проверяет, что сайт открывается
- backend жив (`/health`)
- публичный API работает
- CORS настроен для Telegram
- приватный API закрыт без авторизации

Ничего не меняет.
Рекомендуется запускать **после каждого деплоя**.

```bash
./check-prod-smoke.sh
./check-prod-smoke.sh https://eatfit24.ru
./check-prod-smoke.sh https://eatfit24.ru https://web.telegram.org
```

---

## Другие скрипты (в `/scripts`)

| Скрипт | Тип | Описание |
|--------|-----|----------|
| `check-production-health.sh` | read-only | Проверка состояния сервисов |
| `pre-deploy-check.sh` | read-only | Проверки перед деплоем |
| `health-monitor.sh` | read-only | Мониторинг здоровья сервисов |
| `disk-audit.sh` | read-only | Анализ использования диска |
| `check-secrets-leak.sh` | read-only | Проверка утечек секретов |
| `docker-cleanup.sh` | **ОПАСНО** | Удаляет docker-артефакты |
| `disk-cleanup-safe.sh` | **ОПАСНО** | Чистит диск |
| `EXECUTE_NOW.sh` | **ОПАСНО** | Запускать только если понимаешь что внутри |

---

## Рекомендованный порядок после деплоя

1. Деплой
2. `./scripts/ops/health/check-prod-smoke.sh`
3. Если `PASS` — проверить Telegram Mini App вручную
4. Если `FAIL` — смотреть логи backend/nginx
