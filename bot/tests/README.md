# Tests for FoodMind Bot

Тесты для критических багов бота (P1 приоритет).

## Установка зависимостей

```bash
pip install -r tests/requirements-test.txt
```

## Запуск тестов

### Запустить все тесты
```bash
pytest tests/
```

### Запустить с подробным выводом
```bash
pytest tests/ -v
```

### Запустить с coverage
```bash
pytest tests/ --cov=bot --cov-report=html
```

### Запустить конкретный тест
```bash
pytest tests/test_critical_bugs.py::test_process_gender_invalid_callback_data_missing_value -v
```

## Структура тестов

- `tests/conftest.py` - Pytest fixtures (bot, user, message, callback_query, state)
- `tests/test_critical_bugs.py` - Тесты для всех критических багов P1

## Покрытие тестами

### BUG-2025-001: Валидация callback_data
- ✅ `test_process_gender_invalid_callback_data_missing_value`
- ✅ `test_process_gender_invalid_callback_data_wrong_value`
- ✅ `test_process_gender_valid_callback_data`
- ✅ `test_process_activity_invalid_callback_data`
- ✅ `test_process_activity_invalid_value`
- ✅ `test_process_body_now_invalid_variant_id`
- ✅ `test_process_body_ideal_missing_colon`
- ✅ `test_process_tz_button_invalid_format`

### BUG-2025-002: Отсутствие callback.from_user
- ✅ `test_confirm_and_generate_missing_from_user`

### BUG-2025-003: DB exceptions
- ✅ `test_confirm_and_generate_db_failure_after_ai_generation`

### BUG-2025-005: Race condition
- ✅ `test_confirm_and_generate_prevents_double_click`
- ✅ `test_confirm_and_generate_state_change_immediate`

## Примечания

- Все тесты используют mock объекты для изоляции
- Тесты асинхронные (используют `pytest.mark.asyncio`)
- БД и внешние API (OpenRouter) полностью замоканы
- Для BUG-2025-004 (progress updates) требуется ручное тестирование с задержкой AI
