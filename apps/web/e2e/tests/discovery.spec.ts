import { test, expect } from '../fixtures/pages';
import { testDiscoveryAnswers } from '../fixtures/test-data';

test.describe('Discovery Step', () => {
  // These tests assume we're already at the discovery step
  // In a real scenario, you'd either:
  // 1. Run through research first (slow)
  // 2. Use a fixture/mock to set up discovery state
  // 3. Use a test API to create a discovery session

  test.skip('displays chat interface', async ({ discoveryPage, page }) => {
    // Navigate to a workflow in discovery state
    await page.goto('/optimize?thread_id=test-discovery-thread');
    await discoveryPage.expectChatVisible();
  });

  test.skip('displays gap analysis', async ({ discoveryPage, page }) => {
    await page.goto('/optimize?thread_id=test-discovery-thread');
    await discoveryPage.expectGapAnalysisVisible();
  });

  test.skip('user can answer questions', async ({ discoveryPage, page }) => {
    await page.goto('/optimize?thread_id=test-discovery-thread');
    await discoveryPage.waitForQuestion();

    await discoveryPage.answerQuestion(testDiscoveryAnswers[0]);

    // Verify message was added
    const count = await discoveryPage.getMessageCount();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test.skip('multiple answers lead to more questions', async ({ discoveryPage, page }) => {
    await page.goto('/optimize?thread_id=test-discovery-thread');

    for (const answer of testDiscoveryAnswers) {
      await discoveryPage.waitForQuestion();
      await discoveryPage.answerQuestion(answer);
      await page.waitForTimeout(2000); // Wait for next question
    }

    const count = await discoveryPage.getMessageCount();
    expect(count).toBeGreaterThanOrEqual(testDiscoveryAnswers.length * 2);
  });

  test.skip('confirm button appears after minimum exchanges', async ({ discoveryPage, page }) => {
    await page.goto('/optimize?thread_id=test-discovery-thread');

    // Complete required number of exchanges
    await discoveryPage.completeDiscoveryWithAnswers(testDiscoveryAnswers);

    await expect(discoveryPage.confirmButton).toBeVisible();
  });

  test.skip('discovered experiences are extracted', async ({ discoveryPage, page }) => {
    await page.goto('/optimize?thread_id=test-discovery-thread');
    await discoveryPage.completeDiscoveryWithAnswers(testDiscoveryAnswers);

    await discoveryPage.expectDiscoveredExperiences(1);
  });

  test.skip('confirming discovery moves to drafting', async ({ discoveryPage, draftingPage, page }) => {
    await page.goto('/optimize?thread_id=test-discovery-thread');
    await discoveryPage.completeDiscoveryWithAnswers(testDiscoveryAnswers);

    await discoveryPage.confirmDiscovery();
    await page.waitForTimeout(2000);

    // Should now be on drafting step
    await draftingPage.expectEditorVisible();
  });
});
