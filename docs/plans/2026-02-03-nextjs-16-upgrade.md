# Next.js 14 → 16 Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade Next.js from 14.2.5 to 16.x, React from 18.3.1 to 19.x, and pass all Playwright E2E tests.

**Architecture:** The app uses App Router with all `"use client"` pages, no server-side request APIs (cookies/headers/params), no middleware, no API routes. The upgrade is primarily a dependency version bump with one incompatible package to remove. React 18 → 19 is the biggest change (required by Next.js 16).

**Tech Stack:** Next.js 16, React 19, pnpm, Playwright, TipTap, Tailwind CSS 3

---

### Task 1: Remove unused `react-json-view` dependency

**Files:**
- Modify: `apps/web/package.json`

**Step 1: Remove the package**

`react-json-view` is declared in `package.json` but never imported in source code. It is incompatible with React 19 and must be removed.

```bash
cd /Users/claudevcheval/Hanalei/talent-promo/apps/web && pnpm remove react-json-view
```

**Step 2: Verify no imports exist**

```bash
grep -r "react-json-view\|ReactJson\|JsonView" apps/web/app/ --include="*.ts" --include="*.tsx"
```

Expected: No matches.

**Step 3: Commit**

```bash
git add apps/web/package.json apps/web/pnpm-lock.yaml
git commit -m "chore: remove unused react-json-view dependency (incompatible with React 19)"
```

---

### Task 2: Upgrade Next.js, React, and related dependencies

**Files:**
- Modify: `apps/web/package.json`
- Modify: `pnpm-lock.yaml` (auto-updated)

**Step 1: Run the Next.js upgrade codemod**

The codemod handles: updating next, react, react-dom, @types/react, @types/react-dom, eslint-config-next, and applying codemods for breaking API changes.

```bash
cd /Users/claudevcheval/Hanalei/talent-promo/apps/web && npx @next/codemod upgrade 16
```

Accept all prompts. This will:
- Update `next` to 16.x
- Update `react` and `react-dom` to 19.x
- Update `@types/react` and `@types/react-dom` to latest
- Update `eslint-config-next` to 16.x
- Apply any necessary codemods (async request APIs, etc.)

**Step 2: If codemod doesn't handle everything, manually update**

```bash
cd /Users/claudevcheval/Hanalei/talent-promo/apps/web && pnpm add next@latest react@latest react-dom@latest
cd /Users/claudevcheval/Hanalei/talent-promo/apps/web && pnpm add -D @types/react@latest @types/react-dom@latest eslint-config-next@latest
```

**Step 3: Install dependencies**

```bash
cd /Users/claudevcheval/Hanalei/talent-promo && pnpm install
```

**Step 4: Commit**

```bash
git add -A apps/web/package.json apps/web/pnpm-lock.yaml pnpm-lock.yaml
git commit -m "feat: upgrade Next.js 14→16, React 18→19"
```

---

### Task 3: Fix `next.config.js` for Next.js 16

**Files:**
- Modify: `apps/web/next.config.js`

**Step 1: Review and update config**

Next.js 16 changes:
- `module.exports` → can stay (still supported) or convert to ESM default export
- `webpack` config callback is still supported
- No `experimental.turbopack` needed (Turbopack is now default)
- `next build` no longer runs linter automatically

Current config uses `rewrites()` and `webpack` — both are still supported. The config should work as-is, but verify by building.

**Step 2: Verify build compiles**

```bash
cd /Users/claudevcheval/Hanalei/talent-promo/apps/web && pnpm build
```

If build fails, fix issues. Common issues:
- TypeScript errors from React 19 type changes (e.g., `ref` prop changes, removed `ReactNode` children auto-prop)
- Import changes

**Step 3: Fix any TypeScript errors**

React 19 removes implicit `children` from `React.FC`. If any component uses `React.FC` without explicitly declaring children, add `children` to props. Check build output for specific errors.

**Step 4: Commit if changes were needed**

```bash
git add apps/web/
git commit -m "fix: update config and fix type errors for Next.js 16"
```

---

### Task 4: Verify dev server starts

**Step 1: Start the dev server**

```bash
cd /Users/claudevcheval/Hanalei/talent-promo/apps/web && PORT=3001 pnpm dev
```

**Step 2: Verify it responds**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001
```

Expected: 200

**Step 3: Check for console errors**

Open browser, check DevTools console for React 19 warnings or errors.

---

### Task 5: Run Playwright E2E tests — landing tests

**Step 1: Run landing page tests**

```bash
cd /Users/claudevcheval/Hanalei/talent-promo/apps/web && pnpm test:e2e:landing
```

**Step 2: If failures, fix them**

Common issues:
- Hydration mismatches from React 19
- `<a>` inside `<Link>` (Next.js 15+ auto-renders anchor — no child `<a>` needed)
- Changed default behaviors

**Step 3: Commit fixes if any**

```bash
git add apps/web/
git commit -m "fix: resolve landing page test failures after Next.js 16 upgrade"
```

---

### Task 6: Run Playwright E2E tests — mocked workflow tests

**Step 1: Run the mocked full workflow tests**

```bash
cd /Users/claudevcheval/Hanalei/talent-promo/apps/web && npx playwright test full-workflow-mocked
```

These are the most comprehensive tests (6 active tests) with mocked API responses.

**Step 2: If failures, fix them**

Look at the Playwright HTML report for details:
```bash
npx playwright show-report
```

**Step 3: Commit fixes if any**

```bash
git add apps/web/
git commit -m "fix: resolve mocked workflow test failures after Next.js 16 upgrade"
```

---

### Task 7: Run ALL Playwright E2E tests

**Step 1: Run the full test suite (excluding real-workflow which needs live APIs)**

```bash
cd /Users/claudevcheval/Hanalei/talent-promo/apps/web && npx playwright test --ignore-snapshots
```

**Step 2: Verify all non-skipped tests pass**

Check output for pass/fail counts.

**Step 3: Commit any final fixes**

```bash
git add apps/web/
git commit -m "fix: all Playwright E2E tests passing with Next.js 16"
```

---

## Risk Assessment

**Low risk:**
- No async request APIs (cookies/headers/params) used — the biggest v15/v16 breaking change doesn't apply
- All pages are `"use client"` — minimal server component changes
- No middleware, no API routes, no pages router patterns

**Medium risk:**
- `react-json-view` removal (unused, so zero risk)
- React 19 type changes (FC children, ref forwarding)
- TipTap compatibility with React 19 (core supports it since v2.10)

**Dependencies compatibility:**
- `@tiptap/*` v2.27.1 — React 19 supported since v2.10 ✅
- `dompurify` — no React dependency ✅
- `mammoth` — no React dependency ✅
- `pdfjs-dist` — no React dependency ✅
- `idb` — no React dependency ✅
- `react-json-view` — INCOMPATIBLE, but unused → remove ✅
