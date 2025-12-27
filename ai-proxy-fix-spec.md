# ТЗ: AI-Proxy Fixes — Local Implementation

**Файл:** `backend/eatfit24-ai-proxy/app/openrouter_client.py`
**Сервер:** 185.171.80.128 (NL)
**Backup location:** `/opt/eatfit24-ai-proxy/app/openrouter_client.py.backup-2025-12-26`

---

## Проблема

AI-proxy падает с 500 ошибками из-за **Invalid JSON** от OpenRouter модели (`openai/gpt-5-image-mini`).

**Факты:**
- Success rate: **14.3%** (1 из 7 запросов)
- Ошибки: "Unterminated string", "Expecting value: line 1 column 1", "Expecting property name"
- Текущий код делает HTTP retry (429, 5xx), но **НЕ делает JSON validation retry**
- Сервер здоров: CPU 0.09, Memory 48% free, сеть до OpenRouter 257ms

**Root cause:** Модель возвращает невалидный JSON → код сразу бросает OpenRouterError → 500

---

## Решение: 4 обязательных фикса

### Fix 1: Reduce Timeout (P0)

**Файл:** `app/openrouter_client.py`
**Строка:** ~28

**Было:**
```python
OPENROUTER_TIMEOUT = 30.0  # seconds (P1.3)
```

**Стало:**
```python
OPENROUTER_TIMEOUT = 20.0  # seconds (P0: faster failure detection)
```

**Почему:** Уменьшает worst-case время с 90s до 60s (20s × 3 retries).

---

### Fix 2: Add JSON Retry Constant (P0)

**Файл:** `app/openrouter_client.py`
**Где:** После строки с `NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 413, 422}` (~30)

**Добавить:**
```python

# JSON validation retry configuration
JSON_RETRY_MAX_ATTEMPTS = 2  # Retries after initial failed parse (total 3 attempts)
```

---

### Fix 3: Add Fallback JSON Extractor (P1)

**Файл:** `app/openrouter_client.py`
**Функция:** `parse_ai_response(response_text: str)` (~250-300)

**Где:** В блоке `except json.JSONDecodeError as e:` ПЕРЕД строкой `logger.error(f"Failed to parse AI response as JSON: {e}")`

**Добавить:**
```python
        # Fallback: Try to extract JSON from text with garbage
        logger.warning(f"Initial JSON parse failed: {e}. Attempting fallback extraction.")

        # Try to find JSON object in text using regex
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

        if json_match:
            try:
                text = json_match.group(0)
                data = json.loads(text)

                logger.info("Fallback JSON extraction succeeded!")

                # Extract items (same logic as above)
                items = []
                for item_data in data.get("items", []):
                    normalized_item = normalize_item_fields(item_data)
                    items.append(
                        FoodItem(
                            name=normalized_item["name"],
                            grams=float(normalized_item["grams"]),
                            kcal=float(normalized_item["kcal"]),
                            protein=float(normalized_item["protein"]),
                            fat=float(normalized_item["fat"]),
                            carbohydrates=float(normalized_item["carbohydrates"]),
                        )
                    )

                model_notes = data.get("model_notes")
                return items, model_notes

            except (json.JSONDecodeError, KeyError, ValueError, TypeError) as fallback_error:
                logger.error(f"Fallback extraction also failed: {fallback_error}")

        # Both methods failed - continue to raise original error below
```

**Важно:** Добавить `import re` в начало файла, если его там нет (он должен быть на строке ~7).

---

### Fix 4: Strengthen Prompts (P0)

**Файл:** `app/openrouter_client.py`
**Функция:** `build_food_recognition_prompt()` (~60-200)

#### 4a) Russian Prompt

**Найти строку (конец RU промпта, ~180):**
```python
- Используй стандартные базы данных по питанию для расчёта КБЖУ."""
```

**Заменить на:**
```python
- Используй стандартные базы данных по питанию для расчёта КБЖУ.

⚠️ КРИТИЧЕСКИ ВАЖНО — ФОРМАТ ОТВЕТА:
1. Твой ответ должен быть ТОЛЬКО JSON-объект.
2. БЕЗ markdown блоков (```json).
3. БЕЗ текста до или после JSON.
4. БЕЗ комментариев на естественном языке вне поля "model_notes".
5. Проверь синтаксис: все строки закрыты кавычками, нет висящих запятых.

Начинай ответ сразу с открывающей фигурной скобки {"""
```

#### 4b) English Prompt

**Найти строку (конец EN промпта, ~240):**
```python
- Use standard nutrition databases for calculating calories and macros."""
```

**Заменить на:**
```python
- Use standard nutrition databases for calculating calories and macros.

⚠️ CRITICAL — RESPONSE FORMAT:
1. Your response MUST be ONLY a JSON object.
2. NO markdown blocks (```json).
3. NO text before or after JSON.
4. NO natural language comments outside "model_notes" field.
5. Verify syntax: all strings closed with quotes, no trailing commas.

Start your response immediately with opening curly brace {"""
```

**ВАЖНО:** Не используй f-string для этих изменений — это обычная часть строки внутри существующего base_prompt.

---

### Fix 5: Add JSON Validation Retry Loop (P0) — КРИТИЧЕСКИЙ

**Файл:** `app/openrouter_client.py`
**Функция:** `recognize_food_with_bytes()` (~430-509)

**Текущая структура:**
```python
async def recognize_food_with_bytes(...):
    # Setup code (base64, prompt, headers, payload)

    try:
        async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
            response = await _make_openrouter_request(...)

            # ... status check, result.json(), token logging ...

            # Extract AI response
            ai_response_text = result["choices"][0]["message"]["content"]

            # Parse the response
            items, model_notes = parse_ai_response(ai_response_text)

            # Calculate totals
            total = TotalNutrition(...)

            return items, total, model_notes

    except httpx.TimeoutException:
        ...
    except httpx.RequestError as e:
        ...
    except KeyError as e:
        ...
```

**Новая структура с JSON retry:**

```python
async def recognize_food_with_bytes(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    user_comment: Optional[str] = None,
    locale: str = "ru",
) -> tuple[List[FoodItem], TotalNutrition, Optional[str]]:
    """
    Call OpenRouter API to recognize food in image and return nutritional info

    Now includes JSON validation retry logic (P0 fix).
    """

    # Convert bytes to base64 data URL
    b64_image = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{content_type};base64,{b64_image}"

    logger.debug(f"Converted image to base64 data URL (length: {len(data_url)} chars)")

    # JSON validation retry loop
    for json_attempt in range(1, JSON_RETRY_MAX_ATTEMPTS + 2):  # 1 initial + 2 retries = 3 total
        try:
            # Build prompt (stricter on retries)
            if json_attempt == 1:
                prompt = build_food_recognition_prompt(user_comment, locale)
            else:
                # Stricter prompt for retries
                logger.warning(f"JSON retry attempt {json_attempt} with enhanced prompt")
                base_prompt = build_food_recognition_prompt(user_comment, locale)
                prompt = f"""CRITICAL: Previous response was INVALID JSON.

You MUST return ONLY a valid JSON object with NO TEXT BEFORE OR AFTER.
DO NOT use markdown code blocks (```json).
DO NOT add any commentary outside the JSON.

{base_prompt}"""

            headers = {
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://eatfit24.com",
                "X-Title": "EatFit24",
            }

            payload = {
                "model": settings.openrouter_model,
                "max_tokens": OPENROUTER_MAX_TOKENS,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": data_url,
                                    "detail": OPENROUTER_IMAGE_DETAIL,
                                },
                            },
                        ],
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
                response = await _make_openrouter_request(
                    client,
                    f"{settings.openrouter_base_url}/chat/completions",
                    headers,
                    payload,
                )

                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(
                        f"OpenRouter API error: {response.status_code} - {error_detail}"
                    )
                    raise OpenRouterError(
                        f"OpenRouter API returned {response.status_code}: {error_detail}"
                    )

                result = response.json()

                # Log token usage if available
                usage = result.get("usage")
                if usage:
                    logger.info(
                        f"OpenRouter token usage: "
                        f"prompt={usage.get('prompt_tokens', 'N/A')}, "
                        f"completion={usage.get('completion_tokens', 'N/A')}, "
                        f"total={usage.get('total_tokens', 'N/A')}"
                    )

                # Extract AI response text
                ai_response_text = result["choices"][0]["message"]["content"]

                # Try to parse the response
                items, model_notes = parse_ai_response(ai_response_text)

                # Success! Calculate totals and return
                total = TotalNutrition(
                    kcal=sum(item.kcal for item in items),
                    protein=sum(item.protein for item in items),
                    fat=sum(item.fat for item in items),
                    carbohydrates=sum(item.carbohydrates for item in items),
                )

                if json_attempt > 1:
                    logger.info(f"JSON parsing succeeded on attempt {json_attempt}")

                return items, total, model_notes

        except OpenRouterError as e:
            # Check if it's a JSON parse error
            error_str = str(e).lower()
            is_json_error = "json" in error_str or "parse" in error_str

            if is_json_error and json_attempt < JSON_RETRY_MAX_ATTEMPTS + 1:
                # Retry with stricter prompt
                logger.warning(
                    f"JSON parse failed (attempt {json_attempt}/{JSON_RETRY_MAX_ATTEMPTS + 1}), "
                    f"retrying with stricter prompt: {e}"
                )
                await asyncio.sleep(0.5)  # Brief pause before retry
                continue
            else:
                # Final attempt failed OR non-JSON error
                if is_json_error:
                    logger.error(
                        f"JSON parsing failed after {json_attempt} attempts: {e}"
                    )
                raise

        except httpx.TimeoutException:
            logger.error("OpenRouter API request timed out")
            raise OpenRouterError("Request to OpenRouter API timed out")
        except httpx.RequestError as e:
            logger.error(f"OpenRouter API request failed: {e}")
            raise OpenRouterError(f"Failed to connect to OpenRouter API: {e}")
        except KeyError as e:
            logger.error(f"Unexpected response structure from OpenRouter: {e}")
            raise OpenRouterError(f"Unexpected response structure from OpenRouter: {e}")

    # Should not reach here
    raise OpenRouterError("Unexpected JSON retry loop exit")
```

**Ключевые изменения:**
1. Обернул весь блок в `for json_attempt in range(1, JSON_RETRY_MAX_ATTEMPTS + 2):`
2. На повторных попытках (attempt > 1) добавляю в начало промпта строгое предупреждение
3. В `except OpenRouterError` проверяю, является ли это JSON ошибкой
4. Если да и ещё есть попытки → `continue` (retry)
5. Если нет или попытки кончились → `raise`

---

## Deployment Steps

После локальных правок:

```bash
# 1. Upload modified file to server
scp -i ~/.ssh/id_ed25519 app/openrouter_client.py root@185.171.80.128:/opt/eatfit24-ai-proxy/app/

# 2. SSH to server
ssh root@185.171.80.128

# 3. Verify syntax
cd /opt/eatfit24-ai-proxy
python3 -m py_compile app/openrouter_client.py

# 4. Restart service
docker compose restart ai-proxy

# 5. Wait and check health
sleep 10
curl http://localhost:8001/health

# 6. Test with real image
API_KEY=$(grep "^API_PROXY_SECRET=" .env | cut -d= -f2-)
time curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $API_KEY" \
  -H "X-Request-ID: test-$(date +%s)" \
  -F "image=@tests/assets/test_food_image.jpg" \
  -F "locale=ru" | jq .

# 7. Monitor logs
docker logs -f eatfit24-ai-proxy
```

---

## Expected Results

**Before:**
- Success rate: 14.3%
- Failed requests: 85.7% with "Invalid JSON"
- Duration: 25-87s

**After:**
- Success rate: >80% (target: 90%+)
- JSON retry hits: 10-20% of requests
- Duration: <25s for success, max 60s for failures
- Logs: "JSON parsing succeeded on attempt 2" / "JSON parsing succeeded on attempt 3"

---

## Rollback

If needed:
```bash
ssh root@185.171.80.128
cd /opt/eatfit24-ai-proxy
cp app/openrouter_client.py.backup-2025-12-26 app/openrouter_client.py
docker compose restart ai-proxy
```

---

**Приоритет:** P0 (CRITICAL)
**Estimated Impact:** Fixes 70-80% of current 500 errors
