# Server-safe Cancel — Monitoring Checklist

## Pre-Deploy: Staging E2E Tests (5 minutes)

### Scenario A: Partial Success → Cancel → Done
**Steps:**
1. Upload 3 photos
2. Wait for 1st photo SUCCESS
3. Click Cancel
4. Click Done

**Expected:**
- ✅ Diary shows meal with 1 photo (SUCCESS)
- ✅ Cancelled photos not visible

**Verification logs:**
```bash
# Should see finalization as COMPLETE (1 SUCCESS)
docker compose logs celery-worker | grep "Finalized meal_id=.*COMPLETE"
```

---

### Scenario B: All Cancelled
**Steps:**
1. Upload 2 photos
2. Click Cancel immediately (before any SUCCESS)
3. Open diary

**Expected:**
- ✅ Meal does NOT appear in diary

**Verification logs:**
```bash
# Should see finalization as FAILED (0 SUCCESS)
docker compose logs celery-worker | grep "Finalized meal_id=.*FAILED"
```

---

### Scenario C: Cancel Race (Late SUCCESS)
**Steps:**
1. Upload 1 photo
2. Click Cancel during PROCESSING
3. Wait for AI task to complete
4. Open diary

**Expected:**
- ✅ Cancelled photo NOT visible in diary
- ✅ Race guard triggers (see logs)

**Verification logs:**
```bash
# Should see race guard message
docker compose logs celery-worker | grep "is in terminal state.*discarding results"
```

---

## Production Monitoring (First 24 Hours)

### Critical Log Markers

#### 1. Race Guard Triggers
**Pattern:**
```
[AI] Photo <ID> is in terminal state CANCELLED, discarding results (race condition guard)
[AI] Photo <ID> is in terminal state FAILED, discarding results (race condition guard)
```

**How to check:**
```bash
# On prod server
docker logs eatfit24-celery-worker-1 --tail 1000 | grep "is in terminal state"

# With timestamp
docker logs eatfit24-celery-worker-1 --tail 1000 --timestamps | grep "is in terminal state"
```

**What to look for:**
- **Don't use fixed % thresholds** — race guard frequency depends on UX (if Cancel is accessible, 10-30% is normal)
- **Monitor anomalies instead:**
  - Sudden spike: race guard rate x2 within 24h (relative to baseline)
  - CANCELLED growth with stable DAU (users hitting Cancel more)
  - FAILED growth without CANCELLED growth (AI issues, not user behavior)
  - Rising median processing time + rising cancel rate (users cancel because it's slow)

---

#### 2. Meal Finalization
**Pattern:**
```
[MealService] Finalized meal_id=<ID> as COMPLETE
[MealService] Finalized meal_id=<ID> as FAILED (all photos failed/cancelled)
```

**How to check:**
```bash
# Count COMPLETE vs FAILED
docker logs eatfit24-celery-worker-1 --tail 1000 | grep "Finalized meal_id=" | grep -c "COMPLETE"
docker logs eatfit24-celery-worker-1 --tail 1000 | grep "Finalized meal_id=" | grep -c "FAILED"

# Show both with context
docker logs eatfit24-celery-worker-1 --tail 1000 --timestamps | grep "Finalized meal_id="
```

**What to look for:**
- COMPLETE: Normal flow, at least 1 SUCCESS photo
- FAILED: All photos cancelled/failed (meal hidden from diary)
- Ratio: FAILED should be <5% unless many users testing cancel

---

#### 3. Unexpected Statuses (Alerting)
**Pattern to ALERT on:**
```
# Any MealPhoto stuck in PROCESSING after 60 seconds
SELECT id, status, created_at
FROM nutrition_mealphoto
WHERE status = 'PROCESSING'
AND created_at < NOW() - INTERVAL '60 seconds';

# Any Meal stuck in PROCESSING
SELECT id, status, date
FROM nutrition_meal
WHERE status = 'PROCESSING';
```

**How to check:**
```bash
# Via Django shell
docker exec eatfit24-backend-1 python manage.py shell -c "
from django.utils import timezone
from datetime import timedelta
from apps.nutrition.models import MealPhoto, Meal

stuck_photos = MealPhoto.objects.filter(
    status='PROCESSING',
    created_at__lt=timezone.now() - timedelta(seconds=60)
)
print(f'Stuck photos: {stuck_photos.count()}')
for p in stuck_photos:
    print(f'  Photo {p.id}: {p.status} since {p.created_at}')

stuck_meals = Meal.objects.filter(status='PROCESSING')
print(f'Stuck meals: {stuck_meals.count()}')
for m in stuck_meals:
    print(f'  Meal {m.id}: {m.status} on {m.date}')
"
```

**What to look for:**
- Should be 0 stuck photos/meals
- If >0 → check celery worker health, task queue

---

#### 4. Logical Impossibility: SUCCESS with CANCELLED Status (P0 Alert)
**Pattern to ALERT on:**
```
# MealPhoto with CANCELLED status but has nutrition items attached
# OR appears in API response (serializer leak)
# This should be IMPOSSIBLE — indicates race guard failure
```

**How to check:**
```bash
# Via Django shell (run every 6 hours)
docker exec eatfit24-backend-1 python manage.py shell -c "
from apps.nutrition.models import MealPhoto, NutritionItem

# Check: CANCELLED photos with nutrition items (race guard failed)
leaked = MealPhoto.objects.filter(status='CANCELLED').exclude(items__isnull=True).distinct()
if leaked.exists():
    print(f'🚨 P0 ALERT: {leaked.count()} CANCELLED photos have items attached!')
    for p in leaked[:5]:
        print(f'  Photo {p.id}: status={p.status}, items={p.items.count()}')
else:
    print('✅ No CANCELLED photos with items (race guard working)')

# Check: FAILED photos with nutrition items
failed_leaked = MealPhoto.objects.filter(status='FAILED').exclude(items__isnull=True).distinct()
if failed_leaked.exists():
    print(f'⚠️ Warning: {failed_leaked.count()} FAILED photos have items attached')
"
```

**Via API (spot check):**
```bash
# Fetch meals for today
curl -H "Authorization: Bearer <token>" \
     "https://eatfit24.ru/api/v1/meals/?date=$(date +%Y-%m-%d)" | \
  jq '.[] | .photos[] | select(.status != "SUCCESS") | {id, status, has_items: (.items | length > 0)}'

# Expected: empty output (no non-SUCCESS photos in response)
# If ANY output appears → serializer leak (P0 bug)
```

**What to do if triggered:**
- **IMMEDIATE**: This is a P0 regression — race guard is not working
- Check recent code changes to `apps/ai/tasks.py` (race guard logic)
- Check `apps/nutrition/serializers.py` (filter logic)
- Consider emergency rollback if widespread

---

#### 5. API Response (Serializer Filter)
**Pattern:**
```
# GET /api/v1/meals/?date=2026-01-15
# Should only return SUCCESS photos in "photos" array
# Should NOT return meals with status=FAILED
```

**How to check:**
```bash
# Via curl (replace token/date)
curl -H "Authorization: Bearer <token>" \
     "https://eatfit24.ru/api/v1/meals/?date=2026-01-15" | jq '.[] | {id, status, photos: [.photos[] | {id, status}]}'

# Expected: All photos have status="SUCCESS", no meals with status="FAILED"
```

---

#### 6. Cancel Event Logging (NEW: POST /api/v1/ai/cancel/)
**Pattern:**
```
[AI][Cancel] RECEIVED user=<ID> client_cancel_id=<UUID> run_id=<N> meal_id=<ID> meal_photo_ids=<N> task_ids=<N> request_id=<UUID> reason=<reason>
[AI][Cancel] EVENT_SAVED id=<ID> user=<ID> client_cancel_id=<UUID> noop=<bool>
[AI][Cancel] NOOP user=<ID> client_cancel_id=<UUID> (no active tasks/photos to cancel)
[AI][Cancel] PROCESSED user=<ID> client_cancel_id=<UUID> cancelled_tasks=<N> updated_photos=<N>
[AI][Cancel] DUPLICATE client_cancel_id=<UUID> (already processed), returning cached result
[AI][Cancel] UPDATED_PHOTOS count=<N> meal_photo_ids=[...] user=<ID>
[AI][Cancel] REVOKED task_id=<ID>
```

**How to check:**
```bash
# All cancel events (new endpoint)
docker logs eatfit24-backend-1 --tail 1000 --timestamps | grep "\[AI\]\[Cancel\]"

# Only noop cancels (user clicked Cancel before any photos uploaded)
docker logs eatfit24-backend-1 --tail 1000 | grep "\[AI\]\[Cancel\] NOOP"

# Count cancel events by reason
docker logs eatfit24-backend-1 --tail 1000 | grep "\[AI\]\[Cancel\] RECEIVED" | \
  grep -oP "reason=\K\w+" | sort | uniq -c

# Check idempotency (duplicates)
docker logs eatfit24-backend-1 --tail 1000 | grep "\[AI\]\[Cancel\] DUPLICATE"

# Via database (CancelEvent table)
docker exec eatfit24-backend-1 python manage.py shell -c "
from apps.nutrition.models import CancelEvent
from django.utils import timezone
from datetime import timedelta

# Count cancel events in last 24h
recent = CancelEvent.objects.filter(created_at__gte=timezone.now() - timedelta(hours=24))
total = recent.count()
noop_count = recent.filter(noop=True).count()
print(f'Cancel events (24h): {total}')
print(f'  - Noop: {noop_count} ({noop_count/total*100:.1f}%)')
print(f'  - With action: {total - noop_count} ({(total-noop_count)/total*100:.1f}%)')
print(f'  - Avg photos/event: {recent.aggregate(avg=models.Avg(\"updated_photos\"))[\"avg\"] or 0:.1f}')
"
```

**What to look for:**
- **High noop rate (>50%)**: Users clicking Cancel too early → UX issue (loading spinner not clear?)
- **Low noop rate (<10%)**: Users clicking Cancel after uploads started → expected behavior
- **Duplicates**: Should be rare (<1%), indicates race conditions on frontend
- **CancelEvent table growth**: ~100-500 events/day expected (depends on DAU and Cancel button usage)

**Alerts:**
- 🚨 **P0**: Cancel event saved but photos not updated (updated_photos=0 when meal_photo_ids present)
- ⚠️ **P1**: High duplicate rate (>5% duplicates) → frontend sending multiple cancel requests
- ℹ️ **P2**: Noop rate spike (x2 in 24h) → investigate UX or frontend race condition

---

### Quick Grep Cheatsheet

```bash
# ==== All cancel-related logs ====
docker logs eatfit24-celery-worker-1 --tail 1000 --timestamps | \
  grep -E "(Finalized meal_id|is in terminal state|MealPhoto.*updated to)"

# ==== Race guard only ====
docker logs eatfit24-celery-worker-1 --tail 1000 --timestamps | \
  grep "is in terminal state"

# ==== Finalization stats (last 1000 lines) ====
echo "COMPLETE: $(docker logs eatfit24-celery-worker-1 --tail 1000 | grep -c 'Finalized.*COMPLETE')"
echo "FAILED: $(docker logs eatfit24-celery-worker-1 --tail 1000 | grep -c 'Finalized.*FAILED')"

# ==== Watch live (follow mode) ====
docker logs eatfit24-celery-worker-1 -f --tail 50 | \
  grep --line-buffered -E "(Finalized|terminal state|Cancel)"

# ==== Check for errors during cancel ====
docker logs eatfit24-celery-worker-1 --tail 1000 | \
  grep -i -E "(error|exception|traceback)" | \
  grep -A 5 -B 5 -i cancel

# ==== NEW: Cancel endpoint logs (backend) ====
# All cancel events
docker logs eatfit24-backend-1 --tail 1000 --timestamps | grep "\[AI\]\[Cancel\]"

# Cancel endpoint stats
echo "Total cancel events: $(docker logs eatfit24-backend-1 --tail 1000 | grep -c '\[AI\]\[Cancel\] RECEIVED')"
echo "Noop cancels: $(docker logs eatfit24-backend-1 --tail 1000 | grep -c '\[AI\]\[Cancel\] NOOP')"
echo "Duplicates: $(docker logs eatfit24-backend-1 --tail 1000 | grep -c '\[AI\]\[Cancel\] DUPLICATE')"

# Watch cancel events live
docker logs eatfit24-backend-1 -f --tail 20 | grep --line-buffered "\[AI\]\[Cancel\]"
```

---

## Alert Thresholds

### Immediate Action Required (P0)
- 🚨 **SUCCESS with CANCELLED status**: Race guard failure, consider rollback
- 🚨 **Non-SUCCESS photos in API response**: Serializer leak, immediate investigation
- 🚨 **Cancel event saved but photos not updated**: CancelEvent.updated_photos=0 when meal_photo_ids present → service layer bug
- ✅ **Stuck photos** (PROCESSING >60s): Check celery worker, restart if needed
- ✅ **Exception in finalization**: Check logs, may need rollback

### Monitor Closely (Anomaly Detection)
- ⚠️ **Race guard spike**: x2 increase within 24h (relative to baseline) → investigate timing
- ⚠️ **CANCELLED growth with stable DAU**: Users hitting Cancel more → UX issue?
- ⚠️ **FAILED growth without CANCELLED**: AI service degradation, not user behavior
- ⚠️ **Rising processing time + cancel rate**: Users cancelling due to slowness
- ⚠️ **High duplicate rate (>5%)**: Frontend sending multiple cancel requests → race condition or retry loop
- ⚠️ **Noop rate spike (x2 in 24h)**: Users clicking Cancel too early → UX issue or frontend race condition

### Baseline Expectations (Context-Dependent)
- ✅ **Race guard rate**: Depends on Cancel button UX (5-30% can be normal)
- ✅ **FAILED meals**: Depends on user behavior (5-15% acceptable if Cancel is used)
- ✅ **COMPLETE meals**: Should be majority (70-95% depending on UX)
- ✅ **Cancel noop rate**: 10-50% normal (depends on when Cancel button appears)
- ✅ **Cancel duplicate rate**: <1% expected (idempotency working correctly)
- ✅ **CancelEvent growth**: ~100-500 events/day (depends on DAU and Cancel usage)

---

## Rollback Plan

If critical issues detected in first 24 hours:

```bash
# 1. Stop processing new AI tasks
docker exec eatfit24-celery-worker-1 pkill -f "celery worker"

# 2. Check affected meals
docker exec eatfit24-backend-1 python manage.py shell -c "
from apps.nutrition.models import Meal, MealPhoto
affected = Meal.objects.filter(status='PROCESSING')
print(f'Affected meals: {affected.count()}')
"

# 3. Git rollback
cd /opt/eatfit24
git log --oneline | head -5  # Find commit before cancel feature
git revert <commit-hash>     # Or git reset --hard <prev-commit>

# 4. Rebuild and restart
docker compose up -d --build --force-recreate backend celery-worker

# 5. Manual cleanup (if needed)
docker exec eatfit24-backend-1 python manage.py shell -c "
from apps.nutrition.models import Meal, MealPhoto
MealPhoto.objects.filter(status='PROCESSING').update(status='FAILED')
Meal.objects.filter(status='PROCESSING').update(status='FAILED')
"
```

---

## Success Criteria (After 24 Hours)

- ✅ No stuck photos/meals in PROCESSING
- ✅ **P0 check passed**: Zero CANCELLED photos with items attached (race guard working)
- ✅ **P0 check passed**: Zero non-SUCCESS photos in API responses (serializer working)
- ✅ No anomalous spikes in race guard rate (stable baseline established)
- ✅ No exceptions in finalization logs
- ✅ Frontend shows correct photos (only SUCCESS)
- ✅ Cancelled meals not visible in diary
- ✅ No user complaints about "photos disappearing"

---

## Contact

If issues detected:
1. Check this monitoring guide
2. Run quick grep commands
3. Check `backend/docs/CANCEL_IMPLEMENTATION.md` for architecture
4. Check `backend/docs/CANCEL_FIXES_P0.md` for known fixes
5. Consider rollback if critical
