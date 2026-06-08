import { test, expect } from '../fixtures/pages';

const THREAD_ID = 'resume-editor-surgical-e2e';
const DUPLICATE_BULLET = 'Maintained backend services for payments.';
const ACME_SECOND_BULLET = 'Improved API reliability by leading incident reviews.';

const initialResumeHtml = `
<h1>Jane Doe</h1>
<p>jane@example.com | New York | LinkedIn</p>
<h2>Summary</h2>
<p>Senior engineer with platform experience.</p>
<h2>Experience</h2>
<h3>Staff Engineer - Platform</h3>
<p>Acme Corp | 2021 - Present</p>
<ul>
  <li>${DUPLICATE_BULLET}</li>
  <li>${ACME_SECOND_BULLET}</li>
</ul>
<h3>Senior Engineer</h3>
<p>Beta Inc | 2018 - 2021</p>
<ul>
  <li>${DUPLICATE_BULLET}</li>
</ul>
<h2>Skills</h2>
<p>Python, TypeScript, AWS</p>
`;

const jobPosting = {
  title: 'Platform Engineer',
  company_name: 'TargetCo',
  location: 'Remote',
  requirements: ['Kubernetes', 'observability', 'reliability'],
};

const gapAnalysis = {
  keywords_to_include: ['Kubernetes', 'observability', 'reliability'],
  strengths: ['Platform engineering'],
  recommended_emphasis: ['Production reliability'],
};

async function bootEditorWorkflow(page: import('@playwright/test').Page) {
  await page.addInitScript(({ threadId }) => {
    localStorage.clear();
    localStorage.setItem(
      'talent_promo:pending_input',
      JSON.stringify({
        resumeText: 'Jane Doe platform engineer resume',
        jobText: 'Platform Engineer job description',
      })
    );
    localStorage.removeItem(`resume_agent:editor_html:${threadId}`);
  }, { threadId: THREAD_ID });

  await page.route('**/api/optimize/start', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        thread_id: THREAD_ID,
        current_step: 'editor',
        status: 'running',
        progress: { editor: 'in_progress' },
      }),
    });
  });

  await page.route(`**/api/optimize/status/${THREAD_ID}**`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        thread_id: THREAD_ID,
        current_step: 'editor',
        status: 'running',
        progress: { editor: 'in_progress' },
        resume_html: initialResumeHtml,
        job_posting: jobPosting,
        gap_analysis: gapAnalysis,
      }),
    });
  });

  await page.goto('/optimize');
  await expect(page.locator('.ProseMirror, [contenteditable="true"]')).toBeVisible({ timeout: 20000 });
  await expect(page.locator('.ProseMirror, [contenteditable="true"]')).toContainText(ACME_SECOND_BULLET);
  await expect(page.getByRole('button', { name: /Improve Writing/i })).toBeVisible();
}

test.describe('Resume editor surgical AI workflow', () => {
  test('syncs unsaved editor changes before applying a targeted duplicate-bullet revision', async ({ page }) => {
    const syncHtmlPayloads: string[] = [];
    let applySawSyncedManualEdit = false;
    const revisionPayloads: Record<string, any>[] = [];

    await page.route(`**/api/optimize/${THREAD_ID}/editor/sync`, async (route) => {
      const body = route.request().postDataJSON();
      syncHtmlPayloads.push(body.html);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    await page.route(`**/api/resume/documents/${THREAD_ID}/revision`, async (route) => {
      revisionPayloads.push(route.request().postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          documentId: THREAD_ID,
          revisionId: 'revision-beta-payments',
          documentRevisionId: 'rev-before',
          targetUnit: {
            id: 'section.experience.role.1.bullet.0',
            kind: 'bullet',
            label: 'Experience > Senior Engineer > Bullet 1',
            text: DUPLICATE_BULLET,
            textPreview: DUPLICATE_BULLET,
          },
          editPlan: {
            id: 'plan-beta',
            goal: 'Improve the selected resume text.',
            targetUnitId: 'section.experience.role.1.bullet.0',
            targetLabel: 'Experience > Senior Engineer > Bullet 1',
            scope: 'single_unit',
            assertions: [{ id: 'scope', description: 'Only target bullet changes.', status: 'passed' }],
            todos: [
              { id: 'resolve', label: 'Resolve target unit', status: 'done' },
              { id: 'propose', label: 'Generate scoped patch', status: 'done' },
              { id: 'verify', label: 'Verify requested intent and scope', status: 'done' },
              { id: 'apply', label: 'Commit accepted edit', status: 'pending' },
            ],
          },
          proposedText: 'Maintained Kubernetes-backed payment services with production reliability.',
          patch: 'targetUnitId: section.experience.role.1.bullet.0\n<<<<<<< SEARCH\nMaintained backend services for payments.\n=======\nMaintained Kubernetes-backed payment services with production reliability.\n>>>>>>> REPLACE',
          verification: {
            passed: true,
            summary: 'Verification passed.',
            evidence: 'Maintained Kubernetes-backed payment services with production reliability.',
            checks: [{ id: 'changed', passed: true, reason: 'Changed target text.' }],
          },
          canApply: true,
          overrideRequired: false,
        }),
      });
    });

    await page.route(`**/api/resume/documents/${THREAD_ID}/apply`, async (route) => {
      applySawSyncedManualEdit = syncHtmlPayloads.some((html) => html.includes('Manual unsynced edit'));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          documentId: THREAD_ID,
          documentRevisionId: 'rev-after',
          resumeHtml: initialResumeHtml
            .replace('Senior engineer with platform experience.', 'Senior engineer with platform experience. Manual unsynced edit.')
            .replace(
              `<li>${DUPLICATE_BULLET}</li>\n</ul>\n<h2>Skills</h2>`,
              '<li>Maintained Kubernetes-backed payment services with production reliability.</li>\n</ul>\n<h2>Skills</h2>'
            ),
          resumeMarkdown: '',
          commit: { sha: 'abc123', message: 'Apply resume edit to section.experience.role.1.bullet.0' },
          changedUnitIds: ['section.experience.role.1.bullet.0'],
        }),
      });
    });

    await bootEditorWorkflow(page);

    const editor = page.locator('.ProseMirror, [contenteditable="true"]');
    await editor.click();
    await page.keyboard.press('End');
    await page.keyboard.type(' Manual unsynced edit');

    await page.locator('.ProseMirror li').filter({ hasText: DUPLICATE_BULLET }).nth(1).selectText();
    await expect(page.getByText(/characters selected/)).toBeVisible();

    await page.getByRole('button', { name: /Improve Writing/i }).click();
    await expect(
      page.getByText('Maintained Kubernetes-backed payment services with production reliability.', { exact: true })
    ).toBeVisible();
    await page.getByRole('button', { name: 'Use this revision' }).click();

    await expect(editor).toContainText('Manual unsynced edit');
    await expect(editor).toContainText('Maintained Kubernetes-backed payment services with production reliability.');
    await expect(editor.locator('li').filter({ hasText: DUPLICATE_BULLET })).toHaveCount(1);
    expect(applySawSyncedManualEdit).toBe(true);
    expect(revisionPayloads[0].selected_text).toBe(DUPLICATE_BULLET);
    expect(revisionPayloads[0].editor_selection).toMatchObject({
      context_before: expect.stringContaining('Beta Inc'),
    });
  });

  test('preserves multi-turn chat context and applies only the selected Acme bullet', async ({ page }) => {
    const revisionPayloads: Record<string, any>[] = [];

    await page.route(`**/api/optimize/${THREAD_ID}/editor/sync`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    await page.route(`**/api/resume/documents/${THREAD_ID}/revision`, async (route) => {
      const body = route.request().postDataJSON();
      revisionPayloads.push(body);
      const secondTurn = revisionPayloads.length === 2;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          documentId: THREAD_ID,
          revisionId: secondTurn ? 'revision-acme-observability-2' : 'revision-acme-observability-1',
          documentRevisionId: 'rev-before',
          targetUnit: {
            id: 'section.experience.role.0.bullet.1',
            kind: 'bullet',
            label: 'Experience > Staff Engineer - Platform > Bullet 2',
            text: ACME_SECOND_BULLET,
            textPreview: ACME_SECOND_BULLET,
          },
          editPlan: {
            id: secondTurn ? 'plan-acme-2' : 'plan-acme-1',
            goal: body.user_message,
            targetUnitId: 'section.experience.role.0.bullet.1',
            targetLabel: 'Experience > Staff Engineer - Platform > Bullet 2',
            scope: 'single_unit',
            assertions: [{ id: 'scope', description: 'Only target bullet changes.', status: 'passed' }],
            todos: [],
          },
          proposedText: secondTurn
            ? 'Improved API reliability with observability-led incident reviews and calmer rollout practices.'
            : 'Improved API reliability with observability-led incident reviews.',
          patch: '',
          verification: {
            passed: true,
            summary: 'Verification passed.',
            evidence: 'Improved API reliability with observability-led incident reviews.',
            checks: [{ id: 'changed', passed: true, reason: 'Changed target text.' }],
          },
          canApply: true,
          overrideRequired: false,
        }),
      });
    });

    await page.route(`**/api/resume/documents/${THREAD_ID}/apply`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          documentId: THREAD_ID,
          documentRevisionId: 'rev-after-chat',
          resumeHtml: initialResumeHtml.replace(
            `<li>${ACME_SECOND_BULLET}</li>`,
            '<li>Improved API reliability with observability-led incident reviews and calmer rollout practices.</li>'
          ),
          resumeMarkdown: '',
          commit: { sha: 'def456', message: 'Apply resume edit to section.experience.role.0.bullet.1' },
          changedUnitIds: ['section.experience.role.0.bullet.1'],
        }),
      });
    });

    await bootEditorWorkflow(page);

    await page.locator('.ProseMirror li').filter({ hasText: ACME_SECOND_BULLET }).selectText();
    await expect(page.getByText(/characters selected/)).toBeVisible();
    await page.getByRole('button', { name: 'Chat' }).click();

    const chatBox = page.getByPlaceholder('Ask about the selected text...');
    await chatBox.fill('Add observability, but keep it concise.');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(page.getByText('Improved API reliability with observability-led incident reviews.')).toBeVisible();

    await chatBox.fill('Make that less formal.');
    await page.getByRole('button', { name: 'Send' }).click();
    await expect(
      page.getByText('Improved API reliability with observability-led incident reviews and calmer rollout practices.')
    ).toBeVisible();

    await page.getByRole('button', { name: 'Use this revision' }).last().click();

    const editor = page.locator('.ProseMirror, [contenteditable="true"]');
    await expect(editor).toContainText('Improved API reliability with observability-led incident reviews and calmer rollout practices.');
    await expect(editor).toContainText(DUPLICATE_BULLET);
    expect(revisionPayloads).toHaveLength(2);
    expect(revisionPayloads[1].chat_history).toEqual([
      expect.objectContaining({ role: 'user', content: 'Add observability, but keep it concise.' }),
      expect.objectContaining({
        role: 'assistant',
        content: 'Improved API reliability with observability-led incident reviews.',
      }),
    ]);
    expect(revisionPayloads[1].editor_selection.context_before).toContain('Acme Corp');
  });
});
