import { expect, test, type Page } from "@playwright/test";

const originalSummary =
  "Marketing manager with experience launching software products and working with sales teams.";
const generatedSummary =
  "Product marketing leader for B2B AI products, translating customer insight into launches, sales enablement, and measurable pipeline growth.";
const baseSnapshot = `ALEX MORGAN
Product Marketing Manager

SUMMARY
${originalSummary}`;
const compareSnapshot = `ALEX MORGAN
Product Marketing Manager

SUMMARY
${generatedSummary}`;
const threadRecord = {
  createdAt: "2026-05-28T12:00:00Z",
  id: "feedback-existing",
  previousText: null,
  request: {
    baseSnapshot,
    baseVersionId: "original",
    compareSnapshot,
    compareVersionId: "v1",
    createdAt: "2026-05-28T12:00:00Z",
    id: "feedback-existing",
    instruction: "make it shorter and more revenue-specific",
    lineEnd: 5,
    lineStart: 5,
    selectedText: generatedSummary,
    targetVersionId: "v1",
  },
  revision: {
    lineEnd: 5,
    lineStart: 5,
    proposedRevision: "Revenue-focused product marketing leader for B2B AI launches.",
    rationale: "Tightens the line and adds revenue focus.",
    requestId: "feedback-existing",
    targetVersionId: "v1",
  },
  status: "open",
  updatedAt: "2026-05-28T12:00:00Z",
};

async function mockThreads(page: Page, records: unknown[] = []) {
  await page.route("**/api/resume/review-feedback/threads**", (route) =>
    route.fulfill({
      body: JSON.stringify(records),
      contentType: "application/json",
      status: 200,
    }),
  );
}

test("renders the diff review and compares arbitrary versions", async ({ page }) => {
  await mockThreads(page);

  await page.goto("/resume-diff-review");

  await expect(page.getByRole("heading", { name: "Resume diff review" })).toBeVisible();
  await expect(page.getByText("No feedback yet")).toBeVisible();
  await expect(
    page.getByText("Original to Generated v1: Sharper positioning and stronger launch language"),
  ).toBeVisible();

  await page.getByRole("button", { name: "From version: Original" }).click();
  await page.getByRole("menuitem", { name: /Generated v3/ }).click();
  await page.getByRole("button", { name: "To version: Generated v1" }).click();
  await page.getByRole("menuitem", { name: /Generated v5/ }).click();

  await expect(
    page.getByText(
      "Generated v3 to Generated v5: Narrative version that emphasizes customer insight and enablement",
    ),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "From version: Generated v3" })).toBeVisible();
  await expect(page.getByRole("button", { name: "To version: Generated v5" })).toBeVisible();
});

test("creates targeted feedback and sends selected context to the revision API", async ({
  page,
}) => {
  let revisionPayload: Record<string, unknown> | undefined;
  await mockThreads(page);
  await page.route("**/api/resume/review-feedback/revision", async (route) => {
    revisionPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      body: JSON.stringify({
        lineEnd: revisionPayload.lineEnd,
        lineStart: revisionPayload.lineStart,
        proposedRevision: "Revenue-focused product marketing leader for B2B AI launches.",
        rationale: "Tightens the line and adds revenue focus.",
        requestId: revisionPayload.id,
        targetVersionId: revisionPayload.targetVersionId,
      }),
      contentType: "application/json",
      status: 200,
    });
  });

  await page.goto("/resume-diff-review");
  await page.getByRole("button", { name: "Add targeted feedback for compare line 5" }).click();
  await page
    .getByPlaceholder("Ask for a targeted revision")
    .fill("make it shorter and more revenue-specific");
  await page.getByRole("button", { name: "Add feedback" }).click();

  await expect(page.getByText("1 pending · 0 used")).toBeVisible();
  await expect(page.getByText("Current generated text")).toBeVisible();
  await expect(page.getByText("Your feedback")).toBeVisible();
  await expect(page.getByText("New proposed revision")).toBeVisible();
  await expect(
    page.getByText("Revenue-focused product marketing leader for B2B AI launches."),
  ).toBeVisible();

  expect(revisionPayload).toMatchObject({
    baseVersionId: "original",
    compareVersionId: "v1",
    instruction: "make it shorter and more revenue-specific",
    lineEnd: 5,
    lineStart: 5,
    selectedText: generatedSummary,
    targetVersionId: "v1",
  });
  expect(revisionPayload?.baseSnapshot).toContain(originalSummary);
  expect(revisionPayload?.compareSnapshot).toContain(generatedSummary);
});

test("shows a real API error instead of fabricating a local revision", async ({
  page,
}) => {
  await mockThreads(page);
  await page.route("**/api/resume/review-feedback/revision", (route) =>
    route.fulfill({
      body: JSON.stringify({
        detail: "ANTHROPIC_API_KEY is required for real revision generation.",
      }),
      contentType: "application/json",
      status: 503,
    }),
  );

  await page.goto("/resume-diff-review");
  await page.getByRole("button", { name: "Add targeted feedback for compare line 5" }).click();
  await page
    .getByPlaceholder("Ask for a targeted revision")
    .fill("make it shorter and more revenue-specific");
  await page.getByRole("button", { name: "Add feedback" }).click();

  await expect(page.getByText("ANTHROPIC_API_KEY is required")).toBeVisible();
  await expect(page.getByText("New proposed revision")).not.toBeVisible();
  await expect(page.getByText("No feedback yet")).toBeVisible();
});

test("hydrates persisted feedback and updates status on apply and undo", async ({ page }) => {
  const patches: Array<Record<string, unknown>> = [];

  await mockThreads(page, [threadRecord]);
  await page.route(
    "**/api/resume/review-feedback/threads/feedback-existing",
    async (route) => {
      const update = route.request().postDataJSON() as Record<string, unknown>;
      patches.push(update);
      await route.fulfill({
        body: JSON.stringify({
          ...threadRecord,
          previousText: update.previousText ?? null,
          status: update.status,
          updatedAt: "2026-05-28T12:01:00Z",
        }),
        contentType: "application/json",
        status: 200,
      });
    },
  );

  await page.goto("/resume-diff-review");

  await expect(page.getByText("1 pending · 0 used")).toBeVisible();
  await expect(page.getByText("Revenue-focused product marketing leader for B2B AI launches.")).toBeVisible();

  await page.getByRole("button", { name: "Use this revision" }).click();

  await expect(page.getByText("0 pending · 1 used")).toBeVisible();
  await expect(page.getByText("Used revised text on Line 5")).toBeVisible();
  await expect.poll(() => patches.length).toBe(1);
  expect(patches[0]).toMatchObject({
    status: "applied",
  });
  expect(typeof patches[0].previousText).toBe("string");

  await page.getByRole("button", { name: "Undo" }).click();

  await expect(page.getByText("1 pending · 0 used")).toBeVisible();
  await expect(page.getByRole("button", { name: "Use this revision" })).toBeVisible();
  await expect.poll(() => patches.length).toBe(2);
  expect(patches[1]).toEqual({
    previousText: null,
    status: "open",
  });
});
