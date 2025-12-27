# NL AI-Proxy Actions — Fix Implementation
**Server:** 185.171.80.128 (NL)
**Date:** 2025-12-26
**Objective:** Stabilize AI-proxy by fixing Invalid JSON errors

---

## Quick Summary

**Problems Found:**
1. 🔴 Model returns invalid JSON ~85% of the time → 500 errors
2. 🔴 No retry on JSON validation errors (only HTTP retries)
3. 🟡 30s timeout too high → slow failures (up to 87s total)
4. 🟡 Prompt not strict enough about JSON format

**Fixes Applied:**
1. ✅ Add JSON validation retry with stricter re-prompting
2. ✅ Reduce timeout from 30s to 20s
3. ✅ Strengthen prompt with explicit JSON-only instructions
4. ✅ Add fallback JSON extractor for partial responses

---

## Implementation Plan

### Phase 1: Code Fixes (P0)

#### Fix 1: Add JSON Validation Retry

**File:** `app/openrouter_client.py`

**Current Behavior:**
- `parse_ai_response()` raises `OpenRouterError` on JSON parse failure
- Caller doesn't retry → immediate 500 response

**New Behavior:**
- Catch JSON parse errors
- Retry with stricter prompt: "CRITICAL: Previous response was invalid JSON. Return ONLY valid JSON, no markdown, no commentary."
- Max 2 JSON retries (total 3 attempts including first try)

**Code Changes:**

```python
# Add new constant at top of file
JSON_RETRY_MAX_ATTEMPTS = 2  # Retries after initial failed parse

# Modify recognize_food_with_bytes() function
async def recognize_food_with_bytes(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    user_comment: Optional[str] = None,
    locale: str = "ru",
) -> tuple[List[FoodItem], TotalNutrition, Optional[str]]:
    """
    Call OpenRouter API to recognize food in image and return nutritional info

    Now includes JSON validation retry logic.
    """

    # ... existing setup code ...

    # JSON validation retry loop
    for json_attempt in range(1, JSON_RETRY_MAX_ATTEMPTS + 2):  # +2 = initial + 2 retries
        try:
            # Build prompt (stricter on retries)
            if json_attempt == 1:
                prompt = build_food_recognition_prompt(user_comment, locale)
            else:
                # Stricter prompt for retries
                base_prompt = build_food_recognition_prompt(user_comment, locale)
                prompt = f"""CRITICAL: Previous response was INVALID JSON.

You MUST return ONLY a valid JSON object with NO TEXT BEFORE OR AFTER.
DO NOT use markdown code blocks (```json).
DO NOT add any commentary outside the JSON.

{base_prompt}"""

            # ... make API request ...

            # Try to parse response
            items, model_notes = parse_ai_response(ai_response_text)

            # Success! Return immediately
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
            if "Invalid JSON" in str(e) or "parse" in str(e).lower():
                if json_attempt <= JSON_RETRY_MAX_ATTEMPTS + 1:
                    logger.warning(
                        f"JSON parse failed (attempt {json_attempt}), retrying with stricter prompt: {e}"
                    )
                    await asyncio.sleep(0.5)  # Brief pause before retry
                    continue
                else:
                    # Final attempt failed
                    logger.error(
                        f"JSON parsing failed after {json_attempt} attempts: {e}"
                    )
                    raise
            else:
                # Non-JSON error (HTTP, network, etc.) - don't retry at this level
                raise

    # Should not reach here
    raise OpenRouterError("Unexpected JSON retry loop exit")
```

---

#### Fix 2: Reduce Timeout

**File:** `app/openrouter_client.py`

**Change:**
```python
# OLD
OPENROUTER_TIMEOUT = 30.0  # seconds

# NEW
OPENROUTER_TIMEOUT = 20.0  # seconds (P0: faster failure detection)
```

**Rationale:**
- 20s is still plenty for vision models
- Reduces worst-case time: 20s × 3 retries = 60s max (vs 90s)
- Faster detection of hung requests

---

#### Fix 3: Strengthen Prompt

**File:** `app/openrouter_client.py`

**Function:** `build_food_recognition_prompt()`

**Add to end of both RU and EN prompts:**

```python
# Russian version - add before final return
base_prompt += """

⚠️ КРИТИЧЕСКИ ВАЖНО — ФОРМАТ ОТВЕТА:
1. Твой ответ должен быть ТОЛЬКО JSON-объект.
2. БЕЗ markdown блоков (```json).
3. БЕЗ текста до или после JSON.
4. БЕЗ комментариев на естественном языке вне поля "model_notes".
5. Проверь синтаксис: все строки закрыты кавычками, нет висящих запятых.

Пример ПРАВИЛЬНОГО ответа:
{"items":[{"name":"куриная грудка","grams":150,"kcal":165,"protein":31,"fat":3.6,"carbohydrates":0}],"total":{"kcal":165,"protein":31,"fat":3.6,"carbohydrates":0},"model_notes":"блюдо выглядит как запечённая куриная грудка"}

Пример НЕПРАВИЛЬНОГО ответа:
```json
{"items":...}
```
Это блюдо содержит...

Начинай ответ сразу с открывающей фигурной скобки {"""

# English version - similar addition
base_prompt += """

⚠️ CRITICAL — RESPONSE FORMAT:
1. Your response MUST be ONLY a JSON object.
2. NO markdown blocks (```json).
3. NO text before or after JSON.
4. NO natural language comments outside "model_notes" field.
5. Verify syntax: all strings closed with quotes, no trailing commas.

Example CORRECT response:
{"items":[{"name":"chicken breast","grams":150,"kcal":165,"protein":31,"fat":3.6,"carbohydrates":0}],"total":{"kcal":165,"protein":31,"fat":3.6,"carbohydrates":0},"model_notes":"dish looks like baked chicken breast"}

Example INCORRECT response:
```json
{"items":...}
```
This dish contains...

Start your response immediately with opening curly brace {"""
```

---

#### Fix 4: Add Fallback JSON Extractor

**File:** `app/openrouter_client.py`

**Function:** `parse_ai_response()`

**Add before raising JSONDecodeError:**

```python
def parse_ai_response(response_text: str) -> tuple[List[FoodItem], Optional[str]]:
    """Parse AI model response into structured format"""

    try:
        # Existing code...
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Parse JSON
        data = json.loads(text)

        # ... rest of existing code ...

    except json.JSONDecodeError as e:
        # NEW: Try fallback extraction
        logger.warning(f"Initial JSON parse failed: {e}. Attempting fallback extraction.")

        # Try to find JSON object in text using regex
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

        if json_match:
            try:
                text = json_match.group(0)
                data = json.loads(text)

                logger.info("Fallback JSON extraction succeeded!")

                # Extract items (same as above)
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

        # Both methods failed - raise original error
        logger.error(f"Failed to parse AI response as JSON: {e}")
        raise OpenRouterError(f"Invalid JSON response from AI model: {e}")
```

---

### Phase 2: Deploy & Verify

#### Step 1: Backup Current Code
```bash
ssh root@185.171.80.128
cd /opt/eatfit24-ai-proxy
cp app/openrouter_client.py app/openrouter_client.py.backup-2025-12-26
```

#### Step 2: Apply Changes
```bash
# Edit the file with fixes
nano app/openrouter_client.py

# Verify syntax
python3 -m py_compile app/openrouter_client.py
```

#### Step 3: Restart Service
```bash
cd /opt/eatfit24-ai-proxy
docker compose restart ai-proxy

# Wait 10 seconds
sleep 10

# Verify health
curl http://localhost:8001/health
```

#### Step 4: Test with Real Request
```bash
cd /opt/eatfit24-ai-proxy
API_KEY=$(grep "^API_PROXY_SECRET=" .env | cut -d= -f2-)

time curl -X POST http://localhost:8001/api/v1/ai/recognize-food \
  -H "X-API-Key: $API_KEY" \
  -H "X-Request-ID: test-$(date +%s)" \
  -F "image=@tests/assets/test_food_image.jpg" \
  -F "locale=ru" \
  | jq .
```

**Expected Result:**
- ✅ Status 200
- ✅ Valid JSON response
- ✅ Duration < 30s
- ✅ Russian names

#### Step 5: Monitor Logs
```bash
# Watch logs in real-time
docker logs -f eatfit24-ai-proxy

# In another terminal, check for errors in last 10 minutes
docker logs eatfit24-ai-proxy --since 10m | grep -i "error\|fail\|invalid"
```

---

### Phase 3: Monitoring (Next 24h)

#### Metrics to Track:
1. **Success rate:** Should improve from 16% to >80%
2. **Average duration:** Should stay <25s for successes
3. **JSON retry frequency:** Log "JSON parsing succeeded on attempt X"
4. **Timeout frequency:** Should decrease

#### Check Commands:
```bash
# Count 200 vs 500 responses
docker logs eatfit24-ai-proxy --since 1h | grep "recognize-food" | grep -c " 200 "
docker logs eatfit24-ai-proxy --since 1h | grep "recognize-food" | grep -c " 500 "

# Average duration for successful requests
docker logs eatfit24-ai-proxy --since 1h | grep "recognize-food.*200" | grep -oP 'duration_ms":\K[0-9.]+' | awk '{sum+=$1; n++} END {print sum/n "ms"}'

# Check JSON retry effectiveness
docker logs eatfit24-ai-proxy --since 1h | grep "JSON parsing succeeded on attempt" | wc -l
```

---

## Rollback Plan

If fixes cause issues:

```bash
ssh root@185.171.80.128
cd /opt/eatfit24-ai-proxy

# Restore backup
cp app/openrouter_client.py.backup-2025-12-26 app/openrouter_client.py

# Restart
docker compose restart ai-proxy

# Verify
curl http://localhost:8001/health
```

---

## Optional: Model Switch (If JSON Issues Persist)

If after 24h success rate is still <80%, consider switching models:

**Current:** `openai/gpt-5-image-mini`
**Alternative:** `google/gemini-2.0-flash-exp` (free, faster, better structured output)

**Change in .env:**
```bash
# OLD
OPENROUTER_MODEL=openai/gpt-5-image-mini

# NEW
OPENROUTER_MODEL=google/gemini-2.0-flash-exp
```

Then restart:
```bash
docker compose restart ai-proxy
```

---

## Summary of Actions

| Action | Priority | Status | Impact |
|--------|----------|--------|--------|
| Add JSON validation retry | P0 | ⏳ To implement | 🟢 High — should fix 80%+ of failures |
| Reduce timeout 30s→20s | P0 | ⏳ To implement | 🟡 Medium — faster failure detection |
| Strengthen prompt | P1 | ⏳ To implement | 🟢 High — prevent malformed JSON |
| Add fallback JSON extractor | P2 | ⏳ To implement | 🟡 Medium — salvage partial responses |
| Monitor 24h | P1 | ⏳ After deploy | 🟢 High — verify fixes work |
| Consider model switch | P3 | ⏳ If needed | 🟢 High — nuclear option if all else fails |

---

## Expected Outcome

**Before Fixes:**
- Success rate: 16.7% (1/6 requests)
- Average failed duration: 57s
- Error: "Invalid JSON response"

**After Fixes:**
- Success rate: >80% (target: 90%+)
- Average success duration: <25s
- JSON retry hits: 10-20% of requests
- Timeout reduction: worst case 60s (down from 90s)

---

**End of Actions Document**
