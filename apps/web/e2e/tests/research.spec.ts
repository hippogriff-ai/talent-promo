import { test, expect } from '../fixtures/pages';
import { testResume, testJob } from '../fixtures/test-data';

test.describe('Research Step', () => {
  // Skip these tests - they duplicate the full-workflow.spec.ts test
  // Full workflow test already validates research completion
  test.describe.configure({ mode: 'serial' });
  test.setTimeout(600000); // 10 minute timeout for research

  test.beforeEach(async ({ landingPage }) => {
    // Start a workflow from landing page
    await landingPage.goto();
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.startOptimization();
  });

  test.skip('shows progress during research', async ({ researchPage }) => {
    // Covered by full-workflow.spec.ts
    await researchPage.expectProgressVisible();
  });

  test.skip('research completes and shows results', async ({ researchPage }) => {
    // Covered by full-workflow.spec.ts
    await researchPage.waitForResearchComplete(180000);
    await researchPage.expectResearchResultsVisible();
  });

  test.skip('continue button appears after research', async ({ researchPage }) => {
    await researchPage.waitForResearchComplete(180000);
    await expect(researchPage.continueButton).toBeVisible();
  });

  test.skip('can view profile details', async ({ researchPage }) => {
    await researchPage.waitForResearchComplete(180000);
    await researchPage.openProfileEdit();
    // Verify profile data is shown
    await researchPage.verifyProfileData('JOHN DOE');
  });
});

test.describe('Research Step - Quick Tests', () => {
  // These tests use shorter timeouts and may fail if research takes too long
  test.skip('progress messages update during research', async ({ landingPage, researchPage, page }) => {
    await landingPage.goto();
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.startOptimization();

    // Check for progress updates within first 30 seconds
    let messageCount = 0;
    for (let i = 0; i < 6; i++) {
      await page.waitForTimeout(5000);
      const newCount = await researchPage.progressMessages.count();
      if (newCount > messageCount) {
        messageCount = newCount;
      }
    }

    expect(messageCount).toBeGreaterThan(0);
  });
});
