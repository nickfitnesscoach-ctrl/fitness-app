# 🚀 Quick Start Guide - Debug Mode
## EatFit24 MiniApp

---

## 📝 TL;DR - What Changed

✅ **Debug mode now works correctly:**
- ✅ No flash in production
- ✅ Access debug with `?debug=1` in URL
- ✅ Clean architecture in `shared/config/debug.ts`

---

## 🎯 Quick Test (30 seconds)

### 1. Test Production (No Debug):
```
URL: https://eatfit24.ru/app
Expected: No debug banner, clean UI
```

### 2. Test Production (With Debug):
```
URL: https://eatfit24.ru/app?debug=1
Expected: Red debug banner, debug user ID 999999999
```

### 3. Test Development:
```bash
npm run dev
Expected: Debug banner always visible
```

---

## 📂 New File Structure

```
frontend/src/
├── shared/
│   ├── config/
│   │   └── debug.ts           ← Main debug config
│   └── lib/
│       └── mockTelegram.ts    ← Mock API
└── features/
    └── debug/
        ├── DebugBanner.tsx    ← Debug UI
        └── index.ts
```

---

## 🔑 Key Exports

### Debug Configuration:
```typescript
import { IS_DEBUG, DEBUG_USER } from './shared/config/debug';

// IS_DEBUG = true when:
//   - DEV mode (npm run dev)
//   - OR URL has ?debug=1 parameter

// IS_DEBUG = false when:
//   - Production build without ?debug=1
```

### Mock Telegram:
```typescript
import { setupMockTelegram } from './shared/lib/mockTelegram';

// Auto-initialized in main.tsx when needed
// Creates full Telegram WebApp mock
```

### Debug UI:
```typescript
import { DebugBanner } from './features/debug';

// Only renders when IS_DEBUG is true
```

---

## ⚠️ Breaking Changes

### ❌ Deleted Files:
```
frontend/src/mockTelegram.ts             (use shared/lib/mockTelegram.ts)
frontend/src/components/BrowserDebugBanner.tsx  (use features/debug/DebugBanner.tsx)
```

### 🔄 Updated Imports:
```typescript
// OLD ❌
import { mockTelegramEnv } from './mockTelegram';
import BrowserDebugBanner from './components/BrowserDebugBanner';
import { isBrowserDebugMode } from './lib/telegram';

// NEW ✅
import { setupMockTelegram } from './shared/lib/mockTelegram';
import { DebugBanner } from './features/debug';
import { IS_DEBUG } from './shared/config/debug';
```

---

## 🧪 Testing Checklist

- [ ] **Local dev** - `npm run dev` → Debug banner shows
- [ ] **Prod build** - `npm run build` → No errors
- [ ] **Prod (Telegram)** - Open in Telegram → No debug
- [ ] **Prod (Browser)** - Open without param → No debug
- [ ] **Prod (Debug)** - Open with `?debug=1` → Debug works

---

## 🆘 Troubleshooting

### Problem: Debug banner flashing

**Solution:** Fixed in App.tsx with initialization delay

### Problem: `?debug=1` not working

**Check:**
1. URL has `?debug=1` (not `?debug` or `&debug=1`)
2. Clear browser cache
3. Check console for errors

### Problem: Import errors

**Solution:** Update imports to new paths (see Breaking Changes above)

---

## 📄 Full Documentation

- **Detailed Audit:** `DEBUG_REFACTORING_AUDIT.md`
- **Implementation Summary:** `DEBUG_REFACTORING_SUMMARY.md`
- **This Guide:** `QUICK_START_DEBUG.md`

---

## ✅ Ready to Deploy?

1. Run tests locally
2. Build production (`npm run build`)
3. Deploy to staging
4. Verify all 4 test scenarios
5. Deploy to production

**Questions?** Check the full documentation files listed above.

