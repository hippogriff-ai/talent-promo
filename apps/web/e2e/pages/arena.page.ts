import { Page, Locator, expect } from '@playwright/test';

/**
 * Arena Page Object
 *
 * Represents the admin Arena page for A/B comparison testing.
 * Requires admin authentication via token.
 */
export class ArenaPage {
  readonly page: Page;

  // Auth
  readonly tokenInput: Locator;
  readonly verifyButton: Locator;
  readonly logoutButton: Locator;

  // Header
  readonly pageTitle: Locator;

  // Analytics Dashboard
  readonly analyticsDashboard: Locator;
  readonly totalComparisons: Locator;
  readonly variantAWins: Locator;
  readonly variantBWins: Locator;

  // Start Comparison Form
  readonly startComparisonForm: Locator;
  readonly useTextCheckbox: Locator;
  readonly linkedinUrlInput: Locator;
  readonly jobUrlInput: Locator;
  readonly resumeTextarea: Locator;
  readonly jobTextarea: Locator;
  readonly startButton: Locator;

  // Active Comparison
  readonly arenaIdText: Locator;
  readonly statusText: Locator;
  readonly startNewButton: Locator;

  // Variant Panels
  readonly variantAPanel: Locator;
  readonly variantBPanel: Locator;

  // Live Progress
  readonly liveProgress: Locator;

  // Metrics Panel
  readonly metricsPanel: Locator;

  // Rating Panel
  readonly ratingPanel: Locator;
  readonly rateAButton: Locator;
  readonly rateBButton: Locator;
  readonly rateTieButton: Locator;

  // Comparison History
  readonly comparisonHistory: Locator;

  // Error
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;

    // Auth elements
    this.tokenInput = page.getByPlaceholder('Enter admin token');
    this.verifyButton = page.getByRole('button', { name: 'Verify' });
    this.logoutButton = page.getByRole('button', { name: 'Logout' });

    // Header
    this.pageTitle = page.getByRole('heading', { name: /agent arena/i });

    // Analytics Dashboard
    this.analyticsDashboard = page.locator('.border.rounded-lg').filter({ hasText: /total comparisons/i });
    this.totalComparisons = page.locator('text=/Total Comparisons/i').locator('..').locator('.text-2xl');
    this.variantAWins = page.locator('text=/Variant A/i').locator('..').locator('.text-2xl');
    this.variantBWins = page.locator('text=/Variant B/i').locator('..').locator('.text-2xl');

    // Start Comparison Form
    this.startComparisonForm = page.locator('.border.rounded-lg').filter({ hasText: /start new comparison/i });
    this.useTextCheckbox = page.getByRole('checkbox');
    this.linkedinUrlInput = page.getByPlaceholder(/linkedin\.com\/in/i);
    this.jobUrlInput = page.getByPlaceholder(/https:\/\//i);
    this.resumeTextarea = page.getByPlaceholder(/paste resume content/i);
    this.jobTextarea = page.getByPlaceholder(/paste job description/i);
    this.startButton = page.getByRole('button', { name: /start comparison/i });

    // Active Comparison
    this.arenaIdText = page.locator('text=/Arena ID:/i');
    this.statusText = page.locator('text=/Status:/i');
    this.startNewButton = page.getByRole('button', { name: /start new/i });

    // Variant Panels
    this.variantAPanel = page.locator('.border.rounded-lg').filter({ hasText: /variant a/i }).first();
    this.variantBPanel = page.locator('.border.rounded-lg').filter({ hasText: /variant b/i }).first();

    // Live Progress
    this.liveProgress = page.locator('.border.rounded-lg').filter({ hasText: /live progress/i });

    // Metrics Panel
    this.metricsPanel = page.locator('.border.rounded-lg').filter({ hasText: /performance metrics/i });

    // Rating Panel
    this.ratingPanel = page.locator('.border.rounded-lg').filter({ hasText: /rate this step/i });
    this.rateAButton = page.getByRole('button', { name: /^a$/i });
    this.rateBButton = page.getByRole('button', { name: /^b$/i });
    this.rateTieButton = page.getByRole('button', { name: /tie/i });

    // Comparison History
    this.comparisonHistory = page.locator('.border.rounded-lg').filter({ hasText: /comparison history/i });

    // Error
    this.errorMessage = page.locator('.text-red-500');
  }

  async goto() {
    await this.page.goto('/admin/arena');
    await this.page.waitForLoadState('networkidle');
  }

  async login(token: string) {
    await this.tokenInput.fill(token);
    await this.verifyButton.click();
    // Wait for verification to complete
    await this.page.waitForTimeout(1000);
  }

  async logout() {
    await this.logoutButton.click();
  }

  async switchToTextMode() {
    await this.useTextCheckbox.check();
  }

  async switchToUrlMode() {
    await this.useTextCheckbox.uncheck();
  }

  async fillLinkedInUrl(url: string) {
    await this.linkedinUrlInput.fill(url);
  }

  async fillJobUrl(url: string) {
    await this.jobUrlInput.fill(url);
  }

  async fillResumeText(text: string) {
    await this.switchToTextMode();
    await this.resumeTextarea.fill(text);
  }

  async fillJobText(text: string) {
    await this.jobTextarea.fill(text);
  }

  async startComparison() {
    await this.startButton.click();
  }

  async startNewComparison() {
    await this.startNewButton.click();
  }

  async rateVariantA() {
    await this.rateAButton.click();
  }

  async rateVariantB() {
    await this.rateBButton.click();
  }

  async rateTie() {
    await this.rateTieButton.click();
  }

  async selectComparisonFromHistory(index: number) {
    const historyItems = this.comparisonHistory.locator('button');
    await historyItems.nth(index).click();
  }

  // Assertions
  async expectPageVisible() {
    await expect(this.pageTitle).toBeVisible();
  }

  async expectLoginFormVisible() {
    await expect(this.tokenInput).toBeVisible();
    await expect(this.verifyButton).toBeVisible();
  }

  async expectDashboardVisible() {
    await expect(this.analyticsDashboard).toBeVisible();
  }

  async expectStartFormVisible() {
    await expect(this.startComparisonForm).toBeVisible();
  }

  async expectActiveComparisonVisible() {
    await expect(this.arenaIdText).toBeVisible();
    await expect(this.statusText).toBeVisible();
  }

  async expectVariantPanelsVisible() {
    await expect(this.variantAPanel).toBeVisible();
    await expect(this.variantBPanel).toBeVisible();
  }

  async expectRatingPanelVisible() {
    await expect(this.ratingPanel).toBeVisible();
  }

  async expectHistoryVisible() {
    await expect(this.comparisonHistory).toBeVisible();
  }

  async expectErrorVisible(message?: string) {
    await expect(this.errorMessage).toBeVisible();
    if (message) {
      await expect(this.errorMessage).toContainText(message);
    }
  }
}
