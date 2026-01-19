import { Page, Locator, expect } from '@playwright/test';

/**
 * Landing Page Object
 *
 * Represents the main landing page with the input form.
 * Handles both URL mode and paste mode for profile and job inputs.
 */
export class LandingPage {
  readonly page: Page;

  // Header
  readonly logo: Locator;
  readonly heroTitle: Locator;
  readonly heroSubtitle: Locator;

  // Input Mode Toggles
  readonly pasteResumeButton: Locator;
  readonly linkedinUrlButton: Locator;
  readonly pasteJobButton: Locator;
  readonly jobUrlButton: Locator;

  // URL Inputs (default mode)
  readonly linkedinUrlInput: Locator;
  readonly jobUrlInput: Locator;

  // Text Inputs (paste mode)
  readonly resumeTextarea: Locator;
  readonly jobTextarea: Locator;

  // Submit
  readonly startButton: Locator;

  // Error
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;

    // Header elements
    this.logo = page.getByRole('link', { name: /talent promo/i });
    this.heroTitle = page.getByRole('heading', { level: 1 });
    this.heroSubtitle = page.locator('p').filter({ hasText: /transform/i }).first();

    // Mode toggle buttons
    this.pasteResumeButton = page.getByRole('button', { name: /paste resume/i });
    this.linkedinUrlButton = page.getByRole('button', { name: /linkedin url/i });
    this.pasteJobButton = page.getByRole('button', { name: /paste job description/i });
    this.jobUrlButton = page.getByRole('button', { name: /job url/i });

    // URL inputs (default mode)
    this.linkedinUrlInput = page.getByPlaceholder(/linkedin\.com\/in/i);
    this.jobUrlInput = page.getByPlaceholder(/jobs\.example\.com/i);

    // Text inputs (paste mode)
    this.resumeTextarea = page.getByPlaceholder(/paste your resume/i);
    this.jobTextarea = page.getByPlaceholder(/paste the full job description/i);

    // Submit button
    this.startButton = page.getByRole('button', { name: /start optimization/i });

    // Error message
    this.errorMessage = page.locator('.bg-red-50');
  }

  async goto() {
    // Clear localStorage to get consistent first-visit behavior
    await this.page.goto('/');
    await this.page.waitForLoadState('networkidle');

    // Close onboarding guide if it appears
    await this.dismissOnboardingGuide();
  }

  async dismissOnboardingGuide() {
    // Wait briefly for modal to appear
    await this.page.waitForTimeout(500);

    // Check if onboarding modal is visible and close it
    const closeButton = this.page.locator('.fixed.inset-0.z-50 button').first();
    const isModalVisible = await closeButton.isVisible().catch(() => false);

    if (isModalVisible) {
      await closeButton.click();
      // Wait for modal to close
      await this.page.waitForTimeout(300);
    }
  }

  async switchToResumeTextMode() {
    await this.pasteResumeButton.click();
  }

  async switchToLinkedInMode() {
    await this.linkedinUrlButton.click();
  }

  async switchToJobTextMode() {
    await this.pasteJobButton.click();
  }

  async switchToJobUrlMode() {
    await this.jobUrlButton.click();
  }

  async fillLinkedInUrl(url: string) {
    await this.linkedinUrlInput.click();
    await this.linkedinUrlInput.fill(url);
  }

  async fillResumeText(text: string) {
    await this.switchToResumeTextMode();
    await this.resumeTextarea.click();
    await this.resumeTextarea.fill(text);
  }

  async fillJobUrl(url: string) {
    await this.jobUrlInput.click();
    await this.jobUrlInput.fill(url);
  }

  async fillJobText(text: string) {
    await this.switchToJobTextMode();
    await this.jobTextarea.click();
    await this.jobTextarea.fill(text);
  }

  async startOptimization() {
    await this.startButton.click();
  }

  async expectHeroVisible() {
    await expect(this.heroTitle).toBeVisible();
  }

  async expectFormVisible() {
    // Default mode shows LinkedIn URL input
    await expect(this.linkedinUrlInput).toBeVisible();
  }

  async expectNavigatedToOptimize() {
    await expect(this.page).toHaveURL(/\/optimize/);
  }

  async expectErrorVisible(message?: string) {
    await expect(this.errorMessage).toBeVisible();
    if (message) {
      await expect(this.errorMessage).toContainText(message);
    }
  }
}
