# Trainer Panel Restructure - Phase 1: Plan

**Date:** 2025-12-12
**Branch:** `refactor/trainer-panel-structure`
**Goal:** Reorganize Trainer Panel files into feature-based structure for better maintainability

---

## 1. Scope

### What We're Moving (Trainer Panel Only)
- **Pages:** Files used exclusively in `/panel` routes
- **Components:** UI components specific to trainer panel
- **Hooks:** Business logic hooks for trainer panel features
- **Constants:** Trainer-specific constants
- **Types:** Trainer-specific types
- **Utils:** Trainer-specific utilities (if any)

### What We're NOT Moving (Out of Scope)
- Client-side pages (dashboard, food log, meal details, profile, settings)
- Client-side components (ClientLayout, PageHeader, etc.)
- Shared/common components (Avatar, Toast, ErrorBoundary, etc.)
- API layer (`services/api/*`)
- Contexts (AuthContext, AppDataContext, etc.)
- Client-side hooks (useProfile, useDailyMeals, etc.)
- PaymentHistoryPage and SubscriptionDetailsPage (client routes: `/settings/*`)

---

## 2. Current File Inventory

### Pages (Trainer Panel)
- `src/pages/ClientsPage.tsx` → Trainer panel clients list
- `src/pages/ApplicationsPage.tsx` → Trainer panel applications
- `src/pages/InviteClientPage.tsx` → Trainer panel invite functionality
- `src/pages/SubscribersPage.tsx` → Trainer panel subscribers management

### Components (Trainer Panel)
- `src/components/Dashboard.tsx` → Trainer panel main dashboard
- `src/components/Layout.tsx` → Trainer panel layout with auth & navigation
- `src/components/clients/ClientCard.tsx` → Client card component
- `src/components/clients/ClientDetails.tsx` → Client details view
- `src/components/applications/ApplicationCard.tsx` → Application card
- `src/components/applications/ApplicationDetails.tsx` → Application details view
- `src/components/common/InfoItem.tsx` → Shared info item (may be used in both)

### Hooks (Trainer Panel)
- `src/hooks/useClientsList.ts` → Clients list management
- `src/hooks/useApplications.ts` → Applications management

### Constants (Trainer Panel)
- `src/constants/invite.ts` → Invite link constant
- `src/constants/applications.ts` → Application-related constants

### Types (Trainer Panel)
- `src/types/application.ts` → Application types

### Shared/Common (DO NOT MOVE)
- `src/components/common/InfoItem.tsx` → May be used by both trainer and client
- All client-side pages, components, hooks

---

## 3. Target Structure

```
frontend/src/features/trainer-panel/
├── pages/
│   ├── ClientsPage.tsx
│   ├── ApplicationsPage.tsx
│   ├── InviteClientPage.tsx
│   └── SubscribersPage.tsx
├── components/
│   ├── Dashboard.tsx
│   ├── Layout.tsx
│   ├── clients/
│   │   ├── ClientCard.tsx
│   │   └── ClientDetails.tsx
│   └── applications/
│       ├── ApplicationCard.tsx
│       └── ApplicationDetails.tsx
├── hooks/
│   ├── useClientsList.ts
│   └── useApplications.ts
├── constants/
│   ├── invite.ts
│   └── applications.ts
├── types/
│   └── application.ts
└── index.ts (optional barrel export)
```

---

## 4. File Mapping Table

| Old Path | New Path | Notes |
|----------|----------|-------|
| **Pages** |
| `src/pages/ClientsPage.tsx` | `src/features/trainer-panel/pages/ClientsPage.tsx` | ✓ |
| `src/pages/ApplicationsPage.tsx` | `src/features/trainer-panel/pages/ApplicationsPage.tsx` | ✓ |
| `src/pages/InviteClientPage.tsx` | `src/features/trainer-panel/pages/InviteClientPage.tsx` | ✓ |
| `src/pages/SubscribersPage.tsx` | `src/features/trainer-panel/pages/SubscribersPage.tsx` | ✓ |
| **Components** |
| `src/components/Dashboard.tsx` | `src/features/trainer-panel/components/Dashboard.tsx` | ✓ |
| `src/components/Layout.tsx` | `src/features/trainer-panel/components/Layout.tsx` | ✓ |
| `src/components/clients/ClientCard.tsx` | `src/features/trainer-panel/components/clients/ClientCard.tsx` | ✓ |
| `src/components/clients/ClientDetails.tsx` | `src/features/trainer-panel/components/clients/ClientDetails.tsx` | ✓ |
| `src/components/applications/ApplicationCard.tsx` | `src/features/trainer-panel/components/applications/ApplicationCard.tsx` | ✓ |
| `src/components/applications/ApplicationDetails.tsx` | `src/features/trainer-panel/components/applications/ApplicationDetails.tsx` | ✓ |
| **Hooks** |
| `src/hooks/useClientsList.ts` | `src/features/trainer-panel/hooks/useClientsList.ts` | ✓ |
| `src/hooks/useApplications.ts` | `src/features/trainer-panel/hooks/useApplications.ts` | ✓ |
| **Constants** |
| `src/constants/invite.ts` | `src/features/trainer-panel/constants/invite.ts` | ✓ |
| `src/constants/applications.ts` | `src/features/trainer-panel/constants/applications.ts` | ✓ |
| **Types** |
| `src/types/application.ts` | `src/features/trainer-panel/types/application.ts` | ✓ |

---

## 5. Execution Order

### Group 1: Create Folder Structure
1. Create `src/features/trainer-panel/` base folder
2. Create subfolders: `pages/`, `components/`, `hooks/`, `constants/`, `types/`
3. Create nested component folders: `components/clients/`, `components/applications/`

### Group 2: Move Types & Constants (Dependencies First)
1. Move `types/application.ts`
2. Move `constants/invite.ts`
3. Move `constants/applications.ts`
4. Update imports in these files

### Group 3: Move Hooks
1. Move `hooks/useApplications.ts` (update imports)
2. Move `hooks/useClientsList.ts` (update imports)

### Group 4: Move Components (Bottom-Up)
1. Move `components/clients/ClientCard.tsx`
2. Move `components/clients/ClientDetails.tsx`
3. Move `components/applications/ApplicationCard.tsx`
4. Move `components/applications/ApplicationDetails.tsx`
5. Move `components/Dashboard.tsx`
6. Move `components/Layout.tsx`
7. Update all imports in moved components

### Group 5: Move Pages (Top-Level)
1. Move `pages/InviteClientPage.tsx`
2. Move `pages/ClientsPage.tsx`
3. Move `pages/ApplicationsPage.tsx`
4. Move `pages/SubscribersPage.tsx`
5. Update all imports in moved pages

### Group 6: Update Router
1. Update `App.tsx` to import pages from new paths
2. Test all routes still work

### Group 7: Cleanup
1. Delete empty folders in old locations
2. Verify no broken imports remain

---

## 6. Import Update Rules

### Before:
```typescript
import { Dashboard } from './components/Dashboard';
import ClientsPage from './pages/ClientsPage';
import { useClientsList } from '../hooks/useClientsList';
```

### After:
```typescript
import { Dashboard } from './features/trainer-panel/components/Dashboard';
import ClientsPage from './features/trainer-panel/pages/ClientsPage';
import { useClientsList } from '../hooks/useClientsList';
// Or from within feature:
import { useClientsList } from '../hooks/useClientsList';
```

---

## 7. Testing Checklist

### Build Tests
- [ ] `npm run build` passes without errors
- [ ] `npm run lint` passes (if configured)
- [ ] No TypeScript errors

### Manual Tests (Trainer Panel)
- [ ] `/panel` - Dashboard opens
- [ ] `/panel/clients` - Clients list loads
  - [ ] Search clients works
  - [ ] View client profile works
  - [ ] Open chat works
  - [ ] Remove client works
- [ ] `/panel/invite-client` - Invite page loads
  - [ ] Copy invite link works
- [ ] `/panel/applications` - Applications list loads
  - [ ] Search works
  - [ ] Filter tabs work
  - [ ] View application details works
  - [ ] Make client works
  - [ ] Change status works
  - [ ] Delete application works
- [ ] `/panel/subscribers` - Subscribers page loads
  - [ ] Stats display correctly
  - [ ] Filter tabs work
  - [ ] Refresh works

### Manual Tests (Client Side - Regression)
- [ ] `/` - Client dashboard works (not broken)
- [ ] `/log` - Food log works
- [ ] `/profile` - Profile works
- [ ] `/subscription` - Subscription page works
- [ ] `/settings/subscription` - Subscription details works
- [ ] `/settings/history` - Payment history works

### Navigation
- [ ] Trainer panel bottom nav works
- [ ] Client-side bottom nav works
- [ ] All links and back buttons work

---

## 8. Rollback Plan

### If Imports Break
1. `git status` to see which files changed
2. `git diff` to see what imports changed
3. Fix imports manually or:
4. `git checkout -- <file>` to revert specific file
5. Re-run build test

### If Routes Break
1. Verify `App.tsx` imports are correct
2. Check for typos in paths
3. Ensure all files were moved correctly

### Nuclear Option
```bash
git reset --hard HEAD
git clean -fd
npm install
npm run build
```

---

## 9. Safety Checks

### Before Each Move
1. Read the file first to understand dependencies
2. Search for imports of this file: `grep -r "from.*<filename>" src/`
3. Move the file
4. Update imports in the moved file
5. Update imports in files that import this file

### After All Moves
1. Run `npm run build`
2. Check for any TypeScript errors
3. Manually test affected routes
4. Commit only if build passes

---

## 10. Known Risks & Mitigations

### Risk: Breaking Client-Side Features
**Mitigation:** Only move trainer-panel files. Leave all client-side files untouched.

### Risk: Circular Imports
**Mitigation:** Move dependencies first (types → constants → hooks → components → pages)

### Risk: Shared Components Confusion
**Mitigation:** Keep `InfoItem` in `src/components/common/` as it may be used by both.

### Risk: Lost Git History
**Mitigation:** Use `git mv` instead of manual move where possible. Document moves in commit message.

---

## 11. Success Criteria

- [ ] All trainer panel files grouped under `src/features/trainer-panel/`
- [ ] Build passes: `npm run build` ✓
- [ ] No broken imports or circular dependencies
- [ ] Trainer panel routes work as before
- [ ] Client-side routes not affected
- [ ] Single atomic commit with clear message
- [ ] No unrelated changes included

---

## 12. Next Steps After Phase 1

1. **User Approval:** Wait for user to test and approve merge
2. **Phase 2 (Future):** Client-side feature restructure
3. **Phase 3 (Future):** Shared components library
4. **Phase 4 (Future):** API layer improvements
