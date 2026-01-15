# AI Polling Final Testing Checklist

**Date**: 2026-01-14
**Sprint**: P0 AI Polling Fix (Variant A)
**Status**: Ready for Testing

## Pre-Deploy Verification

### Code Review ✅

- [x] `normalizeTaskStatus()` as SSOT for status mapping
- [x] Backend returns uppercase statuses (SUCCESS/FAILED/PROCESSING)
- [x] Polling has timeout (120s) and max attempts guard
- [x] Anti-duplicate protection (2s window per taskId)
- [x] Refresh triggered on both SUCCESS and FAILED
- [x] No infinite loops (max attempts guard)

### Files Changed

1. `frontend/src/features/ai/api/ai.types.ts` — Added `normalizeTaskStatus()`
2. `frontend/src/features/ai/hooks/useFoodBatchAnalysis.ts` — Use SSOT, dispatch events, add guards
3. `frontend/src/pages/ClientDashboard.tsx` — Anti-duplicate protection, handle SUCCESS/FAILED events
4. `backend/apps/ai_proxy/tasks.py` — Confirmed uppercase statuses

## Browser Testing Scenarios

### Scenario 1: SUCCESS Flow ✅

**Steps**:
1. Open ClientDashboard in browser
2. Navigate to FoodLogPage
3. Upload valid food photo (e.g., meal with visible dishes)
4. Observe "Обработка…" modal
5. Wait for SUCCESS

**Expected**:
- ✅ Modal shows "Обработка…" → "Готово!"
- ✅ Modal closes after 1.5s auto-delay
- ✅ Return to Dashboard → meal card appears immediately (no manual refresh)
- ✅ Meal card shows correct data (title, calories, photo)
- ✅ Console logs show:
  - `[AI] Task <taskId> SUCCESS - mapping result`
  - `[Dashboard] ai:photo-success event: { taskId: ..., mealId: ... }`
  - `[Dashboard] Triggering refresh for taskId: ...`
- ✅ No double refresh (if duplicate event, see "Ignoring duplicate" log)

**Actual**: _[Fill after testing]_

---

### Scenario 2: FAILED Flow ✅

**Steps**:
1. Open ClientDashboard in browser
2. Navigate to FoodLogPage
3. Upload invalid photo (e.g., blank image, non-food object)
4. Observe "Обработка…" modal
5. Wait for FAILED

**Expected**:
- ✅ Modal shows "Обработка…" → error message (e.g., "На фото не удалось распознать блюда")
- ✅ Error displayed in modal (not just console)
- ✅ Return to Dashboard → meal card shows "Ошибка распознавания" (or similar)
- ✅ Console logs show:
  - `[AI] Task <taskId> FAILED: ...`
  - `[Dashboard] ai:photo-failed event: { taskId: ..., error: ... }`
  - `[Dashboard] Triggering refresh for taskId: ...`
- ✅ Dashboard refreshes to show error state

**Actual**: _[Fill after testing]_

---

### Scenario 3: Timeout (Simulated) ⏳

**Steps**:
1. Modify `POLLING_CONFIG.CLIENT_TIMEOUT_MS` to 10000 (10s) in `useFoodBatchAnalysis.ts`
2. Upload photo that takes >10s to process (or mock backend delay)
3. Wait for timeout

**Expected**:
- ✅ Polling stops after ~10s (5 attempts × 2s)
- ✅ Error displayed: "Превышено время ожидания распознавания"
- ✅ Console logs show:
  - `[AI] Task <taskId> still processing (attempt 5/5, ...)`
  - `[AI] Task timeout or error: Превышено время ожидания распознавания`
- ✅ No infinite polling loop
- ✅ Dashboard shows "Обработка…" card (status stuck at PROCESSING)

**Note**: In production, timeout is 120s. This scenario is for testing guard logic only.

**Actual**: _[Fill after testing]_

---

### Scenario 4: Double Event Protection (StrictMode) 🛡️

**Steps**:
1. Enable React StrictMode in `main.tsx`:
   ```tsx
   <React.StrictMode>
       <App />
   </React.StrictMode>
   ```
2. Upload valid photo
3. Wait for SUCCESS
4. Check console logs for duplicate events

**Expected**:
- ✅ Only ONE refresh triggered per SUCCESS event
- ✅ If duplicate detected, see console log:
  ```
  [Dashboard] Ignoring duplicate event for taskId: <taskId>
  ```
- ✅ No UI flickering or double API calls

**Actual**: _[Fill after testing]_

---

### Scenario 5: Batch Upload (Multiple Photos) 📸

**Steps**:
1. Upload 2-3 photos in quick succession
2. Observe multiple "Обработка…" cards in modal
3. Wait for all to complete (SUCCESS or FAILED)

**Expected**:
- ✅ Each photo gets its own taskId
- ✅ Each SUCCESS triggers separate refresh (anti-duplicate prevents same taskId)
- ✅ Final state: all meals visible in Dashboard
- ✅ No race conditions (meals appear in order)

**Note**: Current implementation does not debounce batch refreshes. If this causes issues, see P1.5 plan.

**Actual**: _[Fill after testing]_

---

## Production Smoke Test 🔥

**Prerequisites**:
- Deploy to production
- Test with real Telegram Mini App (not debug mode)

**Steps**:
1. Open bot in Telegram
2. Click "Открыть приложение"
3. Navigate to FoodLogPage
4. Upload real food photo
5. Verify SUCCESS flow (same as Scenario 1)

**Expected**:
- ✅ All flows work same as browser testing
- ✅ No console errors
- ✅ Meal appears in diary after SUCCESS

**Actual**: _[Fill after production deploy]_

---

## Rollback Plan 🔄

If critical issues found:

1. **Revert commit**: `git revert <commit-hash>`
2. **Redeploy**: `docker compose up -d --build frontend`
3. **Known fallback**: Previous version (before normalizeTaskStatus) had working polling but lacked anti-duplicate protection

**Rollback trigger**:
- Infinite polling loop (max attempts guard broken)
- Double refresh causing API overload
- SUCCESS meals not appearing in diary

---

## Sign-Off

### Developer
- **Tested locally**: ☐ Yes ☐ No
- **StrictMode verified**: ☐ Yes ☐ No
- **All scenarios passed**: ☐ Yes ☐ No
- **Signature**: _______________ Date: ___________

### Tech Lead / Reviewer
- **Code reviewed**: ☐ Yes ☐ No
- **P1.5 plan acknowledged**: ☐ Yes ☐ No
- **Approved for production**: ☐ Yes ☐ No
- **Signature**: _______________ Date: ___________

---

## Post-Deploy Monitoring

### First 24 Hours
- [ ] Check Sentry for new errors (AI_TASK_TIMEOUT, duplicate refresh)
- [ ] Monitor backend logs: `docker logs eatfit24-backend-1 | grep "ai_proxy"`
- [ ] Check Redis for stuck tasks: `docker exec eatfit24-redis-1 redis-cli KEYS "ai:task:*"`
- [ ] User feedback: any reports of "stuck processing"?

### Week 1
- [ ] Review P1.5 backlog (is refactoring urgent?)
- [ ] Collect metrics: SUCCESS rate, FAILED rate, timeout rate
- [ ] Performance: refresh latency, API load

---

## Notes

**Current mitigations (P0-3)**:
- Anti-duplicate protection (2s window per taskId)
- Comprehensive logging (every event, every status change)
- Max attempts guard (prevents infinite loop)
- Refresh on both SUCCESS and FAILED

**Known technical debt (P1.5)**:
- Global window events (see `P1.5_REFACTORING_PLAN.md`)
- No debouncing for batch uploads (can add if needed)

**Architecture decision**:
- Chose Variant A (normalize on frontend) over Variant B (backend dict mapping)
- Rationale: Backend already correct, frontend had fragile logic
