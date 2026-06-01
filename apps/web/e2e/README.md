# Web Playwright Tests

Playwright covers browser behavior for the web app. The resume diff review spec verifies the user-facing comparison workflow and the API contract for targeted resume feedback.

## Local Setup

Install workspace dependencies from the repo root:

```bash
pnpm install
```

Create the API virtual environment that the Playwright config starts automatically:

```bash
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install --upgrade pip
apps/api/.venv/bin/pip install -r apps/api/requirements.txt -r apps/api/requirements-dev.txt
```

Install the Chromium browser runtime once:

```bash
pnpm --filter web exec playwright install chromium
```

On Linux CI runners, install browser system dependencies too:

```bash
pnpm --filter web exec playwright install --with-deps chromium
```

## Run Tests

Run all web E2E tests from the repo root:

```bash
pnpm test:e2e
```

Run only the resume diff review spec:

```bash
pnpm --filter web test:e2e resume-diff-review.spec.ts
```

Run with the browser visible:

```bash
pnpm --filter web test:e2e --headed
```

Open the last HTML report:

```bash
pnpm --filter web exec playwright show-report
```

## Servers

`apps/web/playwright.config.ts` starts both local services before the tests:

- FastAPI on `http://localhost:8000`
- Next.js on `http://localhost:3001`

The config reuses already-running servers on those ports. If a test run fails before cleanup, stop those processes before trying again:

```bash
lsof -tiTCP:8000 -sTCP:LISTEN | xargs -r kill
lsof -tiTCP:3001 -sTCP:LISTEN | xargs -r kill
```

## Resume Diff Review Coverage

`apps/web/e2e/resume-diff-review.spec.ts` checks that:

- the diff review page renders and can compare arbitrary generated versions
- highlighted/generated-line feedback sends selected text, line range, version ids, and resume snapshots to the API
- API failures are shown to the user instead of fabricating a local revision
- persisted feedback threads hydrate on page load
- applying and undoing a proposed revision updates thread status

## CI

CI can include Playwright after Node dependencies, the API venv, and Chromium are installed. A minimal web E2E step can run:

```bash
pnpm --filter web exec playwright install --with-deps chromium
pnpm --filter web test:e2e resume-diff-review.spec.ts
```

For the full suite, use `pnpm --filter web test:e2e` and upload `apps/web/playwright-report/` plus `apps/web/test-results/` on failure.
