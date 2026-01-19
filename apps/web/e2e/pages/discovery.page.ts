import { Page, Locator, expect } from '@playwright/test';

/**
 * Discovery Step Page Object
 *
 * Represents the discovery/Q&A phase of the workflow.
 */
export class DiscoveryPage {
  readonly page: Page;

  // Chat elements
  readonly chatContainer: Locator;
  readonly chatMessages: Locator;
  readonly chatInput: Locator;
  readonly sendButton: Locator;

  // Gap analysis
  readonly gapsList: Locator;
  readonly strengthsList: Locator;
  readonly opportunitiesList: Locator;

  // Discovered experiences
  readonly experiencesList: Locator;
  readonly experienceCards: Locator;

  // Progress
  readonly progressIndicator: Locator;
  readonly questionCount: Locator;

  // Actions
  readonly confirmButton: Locator;
  readonly skipButton: Locator;
  readonly skipRemainingLink: Locator;

  constructor(page: Page) {
    this.page = page;

    // Chat elements
    this.chatContainer = page.locator('[data-testid="discovery-chat"]');
    this.chatMessages = page.locator('[data-testid="chat-message"]');
    this.chatInput = page.getByPlaceholder(/share your experience|type your answer/i);
    this.sendButton = page.getByRole('button', { name: /send|submit/i });

    // Gap analysis sections
    this.gapsList = page.locator('[data-testid="gaps-list"]');
    this.strengthsList = page.locator('[data-testid="strengths-list"]');
    this.opportunitiesList = page.locator('[data-testid="opportunities-list"]');

    // Discovered experiences
    this.experiencesList = page.locator('[data-testid="experiences-list"]');
    this.experienceCards = page.locator('[data-testid="experience-card"]');

    // Progress
    this.progressIndicator = page.locator('[data-testid="discovery-progress"]');
    this.questionCount = page.getByText(/question \d+ of/i);

    // Actions
    this.confirmButton = page.getByRole('button', { name: /complete discovery|confirm|continue|proceed/i });
    this.skipButton = page.getByRole('button', { name: /skip/i });
    this.skipRemainingLink = page.getByRole('button', { name: /skip remaining/i });
  }

  async waitForQuestion(timeout = 60000) {
    // Wait for loading to complete (AI indicator disappears)
    await this.page.waitForTimeout(2000);
    // Then wait for input to be visible
    await this.chatInput.waitFor({ state: 'visible', timeout });
  }

  async answerQuestion(answer: string) {
    // Clear any existing text first
    await this.chatInput.click();
    await this.chatInput.clear();
    // Type the answer to ensure React state updates
    await this.chatInput.type(answer, { delay: 10 });
    // Small delay to ensure state sync
    await this.page.waitForTimeout(500);
    // Click send
    await this.sendButton.click();
  }

  async expectChatVisible() {
    // Either chat input or messages should be visible
    const hasInput = await this.chatInput.isVisible().catch(() => false);
    const hasMessages = await this.chatMessages.first().isVisible().catch(() => false);
    expect(hasInput || hasMessages).toBeTruthy();
  }

  async expectGapAnalysisVisible() {
    await expect(this.page.getByText(/gaps|strengths|opportunities/i).first()).toBeVisible();
  }

  async getMessageCount(): Promise<number> {
    return this.chatMessages.count();
  }

  async confirmDiscovery() {
    // Try Complete Discovery button first, fall back to Skip remaining button
    const confirmVisible = await this.confirmButton.isVisible().catch(() => false);
    if (confirmVisible) {
      await this.confirmButton.scrollIntoViewIfNeeded();
      await this.confirmButton.click();
    } else {
      // Try Skip remaining button
      const skipVisible = await this.skipRemainingLink.isVisible().catch(() => false);
      if (skipVisible) {
        await this.skipRemainingLink.click();
      } else {
        // Wait for either to appear
        await Promise.race([
          this.confirmButton.waitFor({ state: 'visible', timeout: 60000 }),
          this.skipRemainingLink.waitFor({ state: 'visible', timeout: 60000 }),
        ]);

        // Click whichever is visible
        if (await this.confirmButton.isVisible().catch(() => false)) {
          await this.confirmButton.click();
        } else {
          await this.skipRemainingLink.click();
        }
      }
    }

    // Wait for transition to drafting step (editor should appear)
    await this.page.waitForTimeout(5000);
    // Wait for the discovery chat to disappear
    await this.chatInput.waitFor({ state: 'hidden', timeout: 60000 }).catch(() => {});
  }

  async completeDiscoveryWithAnswers(answers: string[]) {
    for (const answer of answers) {
      await this.waitForQuestion();
      await this.answerQuestion(answer);
      // Wait for response and next question to load
      await this.page.waitForTimeout(5000);
    }
    // Give extra time for final processing
    await this.page.waitForTimeout(3000);
  }

  async expectDiscoveredExperiences(minCount = 1) {
    const count = await this.experienceCards.count();
    expect(count).toBeGreaterThanOrEqual(minCount);
  }
}
