import { test, expect } from '../fixtures/pages';

/**
 * Real Workflow E2E Test with LinkedIn URL and Job URL
 *
 * This test runs through the entire resume optimization workflow using:
 * - LinkedIn URL: https://www.linkedin.com/in/vicki-zhang-a373995a
 * - Job URL: https://openai.com/careers/software-engineer-full-stack-new-york-city/
 *
 * This is a real integration test that calls actual APIs.
 * Note: This test takes 5-10 minutes to complete.
 */

// Human challenge question-answer mappings
const HUMAN_CHALLENGE_ANSWERS: Record<string, string> = {
  "what sound does a cat make?": "meow",
  "what color is a ripe banana?": "yellow",
  "how many legs does a dog have?": "4",
  "what do cows drink?": "water",
  "what's the opposite of 'hot'?": "cold",
  "what day comes after monday?": "tuesday",
  "what do you call a baby dog?": "puppy",
  "is water wet? (yes/no)": "yes",
  "what noise does a duck make?": "quack",
  "how many eyes do you have?": "2",
};

test.describe('Real Workflow with URLs', () => {
  test.setTimeout(600000); // 10 minute timeout

  test('complete workflow using LinkedIn URL and Job URL', async ({
    landingPage,
    researchPage,
    discoveryPage,
    draftingPage,
    exportPage,
    page,
  }) => {
    const linkedinUrl = 'https://www.linkedin.com/in/vicki-zhang-a373995a';
    const jobUrl = 'https://openai.com/careers/software-engineer-full-stack-new-york-city/';

    // Capture console errors for debugging
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log('Browser console error:', msg.text());
      }
    });

    // Capture network errors
    page.on('requestfailed', request => {
      console.log('Request failed:', request.url(), request.failure()?.errorText);
    });

    // Log API responses
    page.on('response', response => {
      const url = response.url();
      if (url.includes('/api/optimize')) {
        console.log(`API Response: ${response.status()} ${url}`);
      }
    });

    // Step 1: Landing Page - Enter URLs
    console.log('Step 1: Navigating to landing page and entering URLs...');
    await landingPage.goto();

    // LinkedIn URL is default mode, just fill it
    await landingPage.fillLinkedInUrl(linkedinUrl);

    // Job URL is also default mode, just fill it
    await landingPage.fillJobUrl(jobUrl);

    // Step 2: Pass the human challenge
    console.log('Step 2: Answering human verification challenge...');

    // Find the challenge question text
    const challengeQuestionElement = page.locator('.italic').filter({ hasText: /\?$/ });
    const challengeQuestion = (await challengeQuestionElement.textContent())?.toLowerCase().trim() || '';
    console.log('Challenge question:', challengeQuestion);

    // Find the answer
    let answer = 'yes'; // default fallback
    for (const [question, ans] of Object.entries(HUMAN_CHALLENGE_ANSWERS)) {
      if (challengeQuestion.includes(question)) {
        answer = ans;
        break;
      }
    }
    console.log('Answering with:', answer);

    // Fill in the challenge answer
    const challengeInput = page.getByPlaceholder(/your answer/i);
    await challengeInput.fill(answer);

    // Click the Check button
    const checkButton = page.getByRole('button', { name: /check/i });
    await checkButton.click();

    // Wait for verification to pass
    await page.waitForTimeout(500);

    // Verify the "You're human!" message appears
    await expect(page.getByText(/you're human/i)).toBeVisible({ timeout: 5000 });

    // Step 3: Start optimization
    console.log('Step 3: Starting optimization...');
    await landingPage.startOptimization();
    await landingPage.expectNavigatedToOptimize();

    // Wait a moment for the workflow to initialize
    await page.waitForTimeout(3000);

    // Check for error messages or "No Active Workflow" state
    const noWorkflowText = page.getByText(/no active workflow/i);
    const errorText = page.locator('.bg-red-50, [class*="error"]');

    const hasNoWorkflow = await noWorkflowText.isVisible().catch(() => false);
    const hasError = await errorText.isVisible().catch(() => false);

    if (hasNoWorkflow) {
      console.error('ERROR: Workflow failed to start - "No Active Workflow" displayed');
      // Take a screenshot for debugging
      throw new Error('Workflow failed to start - check rate limits or API errors');
    }

    if (hasError) {
      const errorMessage = await errorText.textContent().catch(() => 'Unknown error');
      console.error('ERROR: Error message displayed:', errorMessage);
      throw new Error(`Workflow error: ${errorMessage}`);
    }

    console.log('Workflow started successfully, waiting for research...');

    // Step 4: Wait for Research to complete
    console.log('Step 4: Waiting for research to complete (this may take a few minutes)...');
    await researchPage.waitForResearchComplete(300000); // 5 minute timeout for research
    await researchPage.expectResearchResultsVisible();

    console.log('Research complete! Continuing to discovery...');
    await researchPage.continueToDiscovery();

    // Step 5: Discovery - Skip questions to proceed faster
    console.log('Step 5: In discovery phase, skipping questions to proceed faster...');
    await discoveryPage.waitForQuestion(120000);

    // Skip questions until we reach drafting or complete discovery button appears
    // The workflow may auto-advance to drafting after some skips
    for (let i = 0; i < 5; i++) {
      console.log(`Attempting to skip question ${i + 1}...`);

      // Check if we're already in drafting (editor visible)
      const editorVisible = await page.locator('.ProseMirror, [contenteditable="true"]').isVisible().catch(() => false);
      if (editorVisible) {
        console.log('Already in drafting phase, editor is visible!');
        break;
      }

      // Check if Complete Discovery button is available
      const completeButton = page.getByRole('button', { name: /complete discovery/i });
      const completeVisible = await completeButton.isVisible().catch(() => false);
      if (completeVisible) {
        console.log('Clicking Complete Discovery...');
        await completeButton.click();
        await page.waitForTimeout(5000);
        break;
      }

      // Look for Skip button and click it
      const skipButton = page.getByRole('button', { name: 'Skip' });
      const skipVisible = await skipButton.isVisible().catch(() => false);
      if (skipVisible) {
        await skipButton.click();
        console.log(`Skipped question ${i + 1}`);
        // Wait for next question or transition
        await page.waitForTimeout(3000);
      } else {
        // No skip button, may have transitioned
        console.log('No Skip button found, checking if workflow transitioned...');
        await page.waitForTimeout(2000);
      }
    }

    // Wait a bit for any transitions
    await page.waitForTimeout(3000);

    // Step 6: Drafting
    console.log('Step 6: Waiting for draft to be generated...');
    await draftingPage.waitForEditor(180000);
    await draftingPage.expectEditorVisible();

    // Make a small edit to verify editing works
    const originalContent = await draftingPage.getEditorContent();
    console.log('Draft generated! Content length:', originalContent.length);

    const testEdit = ` [E2E TEST EDIT ${Date.now()}]`;
    await draftingPage.typeInEditor(testEdit);
    await draftingPage.verifyChangesSaved('[E2E TEST EDIT');

    // Approve the draft
    console.log('Approving draft and proceeding to export...');
    await draftingPage.approve();

    // Step 7: Export
    console.log('Step 7: Waiting for export to complete...');
    await exportPage.waitForExportComplete(120000);
    await exportPage.expectExportResultsVisible();
    await exportPage.expectATSReportVisible();
    await exportPage.expectLinkedInVisible();

    // Verify download links are present
    await expect(exportPage.downloadPdfButton).toBeVisible();
    await expect(exportPage.downloadTxtButton).toBeVisible();

    console.log('Full workflow completed successfully!');
  });
});
