# Mock Safety Guidelines

## Incident: P0 Mock Imports in Production (2026-01-13)

**Problem**: Mock data (`subscriptionPlans`) was accidentally bundled into production main bundle, causing potential runtime issues.

**Root cause**: Static import of mock file without proper tree-shaking guards.

**Impact**: Production application loaded dev-only mock code (file present but not executed).

---

## Prevention Rules (MUST FOLLOW)

### 1. DEV mocks must be imported ONLY via dynamic import inside `import.meta.env.DEV`

**✅ CORRECT:**
```typescript
// hooks/useSubscriptionPlans.ts
if (import.meta.env.DEV) {
  const { mockSubscriptionPlans } = await import('../__mocks__/subscriptionPlans');
  return mockSubscriptionPlans;
}
```

**❌ WRONG:**
```typescript
// This will bundle mock into production!
import { mockSubscriptionPlans } from './__mocks__/subscriptionPlans';
```

**Why**: Static imports are always bundled regardless of `if` conditions. Vite cannot tree-shake them.

---

### 2. Never throw on module init for env checks

**✅ CORRECT:**
```typescript
// __mocks__/data.ts
if (import.meta.env.PROD) {
  console.warn('Mock imported in PROD (should not happen)');
}
```

**❌ WRONG:**
```typescript
// This will crash production if mock is accidentally imported!
if (import.meta.env.PROD) {
  throw new Error('Mock imported in production');
}
```

**Why**: Defensive programming. If mock accidentally gets imported, app should gracefully warn, not crash.

---

### 3. All mocks MUST live in `__mocks__/` directories

**Convention**:
```
src/features/billing/
  __mocks__/
    subscriptionPlans.ts  ← Mock data
  hooks/
    useSubscriptionPlans.ts  ← Uses mock via dynamic import
```

**Why**: ESLint rule (`no-restricted-imports`) blocks static imports from `__mocks__/**`.

---

## CI/CD Guards (3 layers)

### Layer 1: ESLint Rule (Development)
```javascript
// eslint.config.js
'no-restricted-imports': ['error', {
  patterns: [{
    group: ['**/__mocks__/*', '**/__mocks__/**'],
    message: 'Use dynamic import() inside import.meta.env.DEV guard',
  }],
}],
```

**Catches**: Static imports from `__mocks__` during `npm run lint`

---

### Layer 2: CI Bundle Check (Pre-Deploy)
```yaml
# .github/workflows/frontend.yml
- name: Guard — Check for mocks in production bundle
  run: |
    grep -q "mockSubscriptionPlans" dist/assets/index-*.js && exit 1
    grep -q "was imported in PROD" dist/assets/index-*.js && exit 1
    grep -q "__mocks__" dist/assets/index-*.js && exit 1
```

**Catches**: Mock code that slipped into production bundle after build

---

### Layer 3: Runtime Warning (Production Safety)
```typescript
// __mocks__/subscriptionPlans.ts
if (import.meta.env.PROD) {
  console.warn('mockSubscriptionPlans was imported in PROD (should not happen)');
}
```

**Catches**: If mock somehow executes in production, logs warning to console (visible in DevTools)

---

## Quick Reference

| Scenario | Action |
|----------|--------|
| Need mock data for dev/tests | ✅ Use dynamic import inside `import.meta.env.DEV` |
| Mock found in production bundle | ❌ CI will block deployment |
| ESLint error on static import | ❌ Fix: use dynamic import |
| Console warning in prod DevTools | 🚨 Report to team immediately |

---

## Related Files

- [frontend/.github/workflows/frontend.yml](../../.github/workflows/frontend.yml#L73-L127) — CI bundle guard
- [frontend/eslint.config.js](../eslint.config.js#L28-L35) — ESLint rule
- [frontend/src/features/billing/__mocks__/subscriptionPlans.ts](../src/features/billing/__mocks__/subscriptionPlans.ts) — Example mock with runtime guard

---

**Last updated**: 2026-01-13
**Incident resolution**: P0 closed, all guards in place
