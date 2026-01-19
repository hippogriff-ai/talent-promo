import { Page, Locator, expect } from '@playwright/test';

/**
 * Research Step Page Object
 *
 * Represents the research phase of the workflow.
 */
export class ResearchPage {
  readonly page: Page;

  // Progress indicators
  readonly progressContainer: Locator;
  readonly progressMessages: Locator;
  readonly researchStatus: Locator;

  // Research results
  readonly profileCard: Locator;
  readonly jobCard: Locator;
  readonly gapAnalysisCard: Locator;
  readonly researchInsightsCard: Locator;

  // Actions
  readonly continueButton: Locator;
  readonly showMoreButtons: Locator;
  readonly editProfileButton: Locator;
  readonly editJobButton: Locator;

  constructor(page: Page) {
    this.page = page;

    // Progress elements
    this.progressContainer = page.locator('[data-testid="research-progress"]');
    this.progressMessages = page.locator('[data-testid="progress-message"]');
    this.researchStatus = page.getByText(/researching|analyzing|fetching/i);

    // Result cards
    this.profileCard = page.locator('[data-testid="profile-card"]');
    this.jobCard = page.locator('[data-testid="job-card"]');
    this.gapAnalysisCard = page.locator('[data-testid="gap-analysis"]');
    this.researchInsightsCard = page.locator('[data-testid="research-insights"]');

    // Actions
    this.continueButton = page.getByRole('button', { name: /continue to discovery/i });
    this.showMoreButtons = page.getByRole('button', { name: /show more/i });
    this.editProfileButton = page.locator('[data-testid="edit-profile"]');
    this.editJobButton = page.locator('[data-testid="edit-job"]');
  }

  async waitForResearchComplete(timeout = 120000) {
    await this.continueButton.waitFor({ state: 'visible', timeout });
  }

  async expectProgressVisible() {
    // Either progress messages or status text should be visible
    const hasProgress = await this.progressMessages.first().isVisible().catch(() => false);
    const hasStatus = await this.researchStatus.isVisible().catch(() => false);
    expect(hasProgress || hasStatus).toBeTruthy();
  }

  async expectResearchResultsVisible() {
    // Wait for at least one card to be visible
    await expect(this.page.locator('h2, h3').filter({ hasText: /profile|job|gap|research/i }).first()).toBeVisible();
  }

  async continueToDiscovery() {
    await this.continueButton.click();
  }

  async openProfileEdit() {
    await this.showMoreButtons.first().click();
  }

  async verifyProfileData(expectedName: string) {
    const profileText = await this.page.locator('text=' + expectedName).isVisible();
    expect(profileText).toBeTruthy();
  }
}
