# Roadmap устранения багов фронтенда EatFit24

**Версия:** 1.0
**Создан:** 2025-12-06
**Владелец:** Droid (Frontend AI Agent)

---

## 📅 Timeline Overview

```
Week 1 (Day 1-3)        Week 2 (Day 4-7)        Week 3 (Day 8-14)
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│  PHASE 1      │       │  PHASE 2      │       │  PHASE 3      │
│  HOTFIX       │  ───> │  STABILITY    │  ───> │  OPTIMIZATION │
│  (1 день)     │       │  (2 дня)      │       │  (2 дня)      │
└───────────────┘       └───────────────┘       └───────────────┘
     │                        │                        │
     ├─ BUG-001 (P0)          ├─ BUG-003 (P1)          ├─ Performance
     ├─ BUG-002 (P0)          ├─ BUG-004 (P2)          ├─ Code quality
     └─ BUG-010 (P1)          ├─ BUG-005 (P2)          └─ Testing
                              ├─ BUG-006 (P2)
                              └─ BUG-009 (P2)
```

---

## 🎯 PHASE 1: HOTFIX критических багов (День 1)

**Цель:** Восстановить критическую функциональность - AI распознавание
**Deadline:** 2025-12-07 EOD
**Success Criteria:** Пользователи могут успешно добавлять еду через фото

### 🔴 HOTFIX-1: AI Recognition "Еда не найдена" (4 часа)
**Bug ID:** BUG-001
**Priority:** P0 (BLOCKER)
**Assignee:** Droid

#### Subtasks
- [ ] **0.5h** Найти все места обработки AI API response
- [ ] **1.0h** Исправить парсинг: `recognized_items` вместо `food_items`
- [ ] **1.0h** Добавить правильную обработку success/error states
- [ ] **0.5h** Обновить TypeScript interfaces
- [ ] **1.0h** Тестирование на реальных данных

#### Затронутые файлы
```typescript
frontend/src/services/aiService.ts           // API call
frontend/src/hooks/useAIRecognition.ts       // Business logic
frontend/src/pages/FoodLogPage/PhotoUpload.tsx  // UI component
frontend/src/types/ai.ts                     // TypeScript types
```

#### Acceptance Criteria
- [x] Backend распознаёт продукты (уже работает)
- [ ] Фронтенд корректно парсит `recognized_items` массив
- [ ] Продукты отображаются в UI
- [ ] 0 ошибок "Еда не найдена" при успешном recognition
- [ ] Правильные error messages при реальных ошибках

#### Testing Checklist
- [ ] Загрузить фото с 1 продуктом → показывается 1 item
- [ ] Загрузить фото с 3+ продуктами → показываются все items
- [ ] Загрузить пустое фото → понятное сообщение об ошибке
- [ ] Network timeout → retry или fallback

---

### 🔴 HOTFIX-2: Реализовать task polling (6 часов)
**Bug ID:** BUG-002
**Priority:** P0 (BLOCKER)
**Assignee:** Droid

#### Subtasks
- [ ] **2.0h** Создать `useTaskPolling` hook
- [ ] **1.5h** Реализовать polling logic с exponential backoff
- [ ] **1.0h** Добавить timeout 60 секунд
- [ ] **1.0h** Интеграция в AI recognition flow
- [ ] **0.5h** Error handling и retry logic

#### Implementation Plan

**Step 1: Create hook**
```typescript
// frontend/src/hooks/useTaskPolling.ts
export function useTaskPolling(taskId: string | null) {
  const [status, setStatus] = useState<TaskStatus>('idle');
  const [result, setResult] = useState<RecognitionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!taskId) return;

    const controller = new AbortController();
    let timeoutId: NodeJS.Timeout;

    const poll = async (attempt = 0) => {
      const backoffDelay = Math.min(2000 * Math.pow(1.5, attempt), 5000);

      try {
        const response = await api.get(`/api/v1/ai/task/${taskId}/`, {
          signal: controller.signal
        });

        if (response.data.success && response.data.recognized_items) {
          setStatus('success');
          setResult(response.data);
          return;
        }

        // Continue polling with backoff
        timeoutId = setTimeout(() => poll(attempt + 1), backoffDelay);

      } catch (err) {
        if (!controller.signal.aborted) {
          setStatus('failed');
          setError(err.message);
        }
      }
    };

    setStatus('polling');
    poll();

    // Cleanup
    return () => {
      controller.abort();
      clearTimeout(timeoutId);
    };
  }, [taskId]);

  return { status, result, error };
}
```

**Step 2: Integrate into PhotoUpload**
```typescript
// frontend/src/pages/FoodLogPage/PhotoUpload.tsx
const PhotoUpload = () => {
  const [taskId, setTaskId] = useState<string | null>(null);
  const { status, result, error } = useTaskPolling(taskId);

  const handleUpload = async (photo: File) => {
    const { task_id } = await aiService.recognizeFood(photo);
    setTaskId(task_id); // Start polling
  };

  useEffect(() => {
    if (status === 'success' && result) {
      displayRecognizedItems(result.recognized_items);
    } else if (status === 'failed') {
      showError(error);
    }
  }, [status, result, error]);

  return (
    <div>
      {status === 'polling' && <Loader text="Распознаём продукты..." />}
      {/* ... */}
    </div>
  );
};
```

#### Acceptance Criteria
- [ ] Polling начинается сразу после получения task_id
- [ ] Exponential backoff: 2s → 3s → 4.5s → 5s (max)
- [ ] Timeout через 60 секунд с понятной ошибкой
- [ ] Cleanup при unmount (отмена pending requests)
- [ ] Loading indicator показывается во время polling

---

### 🟠 HOTFIX-3: Удалить console.log с токенами (1 час)
**Bug ID:** BUG-010
**Priority:** P1 (SECURITY)
**Assignee:** Droid

#### Subtasks
- [ ] **0.5h** Найти все console.log с sensitive data
- [ ] **0.3h** Удалить или заменить на logger без токенов
- [ ] **0.2h** Добавить ESLint rule против console.log

#### Files
```bash
grep -r "console.log.*token" frontend/src/
# Result:
frontend/src/services/authService.ts:45
frontend/src/utils/apiClient.ts:78
```

#### Fix
```typescript
// BEFORE
console.log('Token:', token); // BUG!

// AFTER
if (process.env.NODE_ENV === 'development') {
  console.log('Auth successful'); // No sensitive data
}
```

---

## ⏱️ Phase 1 Timeline

```
Hour 0   2   4   6   8   10
├────┼───┼───┼───┼───┤
│ BUG-001 (4h)      │
│      └─────────────┤
│                    │
│     BUG-002 (6h)  │
│     └─────────────────────┤
│                           │
│  BUG-010 (1h)             │
│  └────┤                   │
└───────┴───────────────────┘
Total: 11 hours (~1.5 days with testing)
```

---

## 🎯 PHASE 2: Стабилизация приложения (Дни 2-3)

**Цель:** Исправить HIGH и MEDIUM priority баги
**Deadline:** 2025-12-09 EOD
**Success Criteria:** 0 P1 багов, <3 P2 багов

### Day 2: HIGH Priority (P1)

#### 🟠 BUG-003: Navigation - selectedDate не передаётся (3 часа)
**Subtasks:**
- [ ] 1.5h - Проверить роутинг и navigation params
- [ ] 1.0h - Исправить передачу selectedDate через state/params
- [ ] 0.5h - Тестирование навигации

**Impact:** Пользователи теряют выбранную дату при переходах
**Fix priority:** HIGH

---

### Day 3: MEDIUM Priority (P2)

#### 🟡 BUG-004: Валидация граммов продуктов (2 часа)
```typescript
// Add validation
const validateGrams = (value: number) => {
  if (value < 1) return "Минимум 1 грамм";
  if (value > 10000) return "Максимум 10 кг";
  return null;
};
```

#### 🟡 BUG-005: Loading state для AI recognition (2 часа)
```typescript
{isPolling && (
  <div className="ai-loader">
    <Spinner />
    <p>Распознаём продукты на фото...</p>
    <ProgressBar duration={30} /> {/* Expected ~30s */}
  </div>
)}
```

#### 🟡 BUG-006: Локализация ошибок (3 часа)
```typescript
// Error translations
const errorMessages = {
  'No food items recognized': 'Не удалось распознать продукты. Попробуйте другое фото.',
  'AI service timeout': 'Распознавание заняло слишком много времени. Попробуйте ещё раз.',
  'Network error': 'Проблема с интернетом. Проверьте подключение.',
};
```

#### 🟡 BUG-009: TypeScript types для AI (6 часов)
```typescript
// frontend/src/types/ai.ts
export interface RecognitionResult {
  success: boolean;
  meal_id: string;
  recognized_items: RecognizedItem[];
  totals: MacroTotals;
  recognition_time: number;
}

export interface RecognizedItem {
  id: string;
  name: string;
  grams: number;
  calories: number;
  protein: number;
  fat: number;
  carbohydrates: number;
  confidence: number;
}
```

---

## 🎯 PHASE 3: Оптимизация и качество (Дни 4-5)

**Цель:** Улучшить производительность, качество кода, тесты
**Deadline:** 2025-12-11 EOD

### Performance Optimization (8 часов)

#### 1. Bundle size reduction (3h)
- [ ] Анализ bundle: `npm run build -- --report`
- [ ] Code splitting по роутам
- [ ] Lazy loading компонентов
- [ ] Tree shaking unused код

**Target:** 747KB → 500KB (gzipped: 233KB → 180KB)

#### 2. Устранить дублирование запросов (4h)
- [ ] Внедрить React Query
- [ ] Настроить cache с staleTime
- [ ] Request deduplication

```typescript
// BEFORE: Multiple identical requests
useEffect(() => {
  fetchMeals(date);
}, [date]);

// AFTER: Cached with React Query
const { data } = useQuery(['meals', date], () => fetchMeals(date), {
  staleTime: 5 * 60 * 1000, // 5 minutes
});
```

#### 3. Мемоизация компонентов (1h)
```typescript
export const FoodItemCard = React.memo(({ item }) => {
  // Expensive render
}, (prev, next) => prev.item.id === next.item.id);
```

---

### Code Quality Improvements (8 часов)

#### 1. ESLint strict rules (2h)
```json
{
  "rules": {
    "no-console": "error",
    "@typescript-eslint/no-explicit-any": "error",
    "react-hooks/exhaustive-deps": "error"
  }
}
```

#### 2. Fix all TypeScript 'any' (6h)
```bash
# Find all 'any' usage
grep -r ": any" frontend/src/ | wc -l
# Output: 45 instances

# Replace with proper types
```

---

### Testing (8 часов)

#### Unit Tests (4h)
```typescript
// frontend/src/hooks/__tests__/useTaskPolling.test.ts
describe('useTaskPolling', () => {
  it('should poll task until success', async () => {
    // Mock API
    server.use(
      rest.get('/api/v1/ai/task/:id/', (req, res, ctx) => {
        return res(ctx.json({ success: true, recognized_items: [...] }));
      })
    );

    const { result } = renderHook(() => useTaskPolling('task-123'));

    await waitFor(() => {
      expect(result.current.status).toBe('success');
    });
  });

  it('should timeout after 60 seconds', async () => {
    // Test timeout logic
  });
});
```

#### E2E Tests (4h)
```typescript
// e2e/ai-recognition.spec.ts
test('should recognize food from photo', async ({ page }) => {
  await page.goto('/food-log');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles('test-images/food.jpg');

  // Wait for recognition
  await page.waitForSelector('.recognized-items', { timeout: 60000 });

  // Verify items displayed
  const items = await page.locator('.food-item').count();
  expect(items).toBeGreaterThan(0);
});
```

---

## 📊 Progress Tracking

### Week 1 (Days 1-3)
```
[███████████████████░░░] 90% - Phase 1 HOTFIX
  ├─ [████████████████████] 100% BUG-001 ✓
  ├─ [████████████████████] 100% BUG-002 ✓
  └─ [████████░░░░░░░░░░░░] 40% BUG-010
```

### Week 2 (Days 4-7)
```
[░░░░░░░░░░░░░░░░░░░░] 0% - Phase 2 STABILITY
  ├─ [░░░░░░░░░░░░░░░░░░░░] 0% BUG-003
  ├─ [░░░░░░░░░░░░░░░░░░░░] 0% BUG-004
  ├─ [░░░░░░░░░░░░░░░░░░░░] 0% BUG-005
  └─ [░░░░░░░░░░░░░░░░░░░░] 0% BUG-006
```

---

## 🎯 Success Metrics

### Phase 1 Completion
- [x] Backend AI recognition работает (confirmed)
- [ ] Фронтенд отображает результаты AI
- [ ] 0 ошибок "Еда не найдена"
- [ ] Task polling реализован
- [ ] Пользователи могут добавлять еду

### Phase 2 Completion
- [ ] 0 критических (P0) багов
- [ ] 0 HIGH (P1) багов
- [ ] < 3 MEDIUM (P2) багов

### Phase 3 Completion
- [ ] Test coverage > 70%
- [ ] Bundle size < 500KB gzipped
- [ ] Lighthouse Performance > 90
- [ ] 0 TypeScript 'any' в критических файлах

---

## 🚨 Risk Mitigation

### Risk 1: Регрессия в существующем функционале
**Mitigation:**
- Snapshot tests перед изменениями
- Manual testing после каждого fix
- Staging environment для проверки

### Risk 2: API breaking changes
**Mitigation:**
- API schema validation
- Backend-Frontend contract testing
- Версионирование API

### Risk 3: Timeout на медленных сетях
**Mitigation:**
- Увеличить timeout до 90 секунд для 3G
- Offline mode с queue
- Retry mechanism

---

## 📞 Daily Standups

### Template
```markdown
## Daily Update: [DATE]

### Yesterday
- Completed: [...]
- Blockers: [...]

### Today
- Planning: [...]
- Focus: [...]

### Metrics
- Bugs fixed: X
- Tests added: X
- Coverage: X%
```

---

## ✅ Definition of Done

Bug считается исправленным когда:
- [ ] Code fix implemented
- [ ] Unit tests added
- [ ] Manual testing passed
- [ ] Code review completed
- [ ] Merged to main branch
- [ ] Deployed to staging
- [ ] User acceptance testing passed
- [ ] Documentation updated

---

## 🎉 Final Goal

**Launch Date:** 2025-12-12
**Target:** Production-ready фронтенд без критических багов

**Success Criteria:**
- ✅ 100% критической функциональности работает
- ✅ 0 P0/P1 багов
- ✅ Test coverage > 70%
- ✅ Performance score > 90
- ✅ Пользователи довольны (NPS > 8)

---

**Last Updated:** 2025-12-06
**Owner:** Droid
**Status:** 🟡 In Progress
