import { Page, Locator, expect } from '@playwright/test';

/**
 * Human challenge question-answer mappings.
 * These are the bot-protection questions shown on the landing page.
 */
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
  readonly uploadResumeButton: Locator;
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

  // Human verification challenge
  readonly humanChallengeInput: Locator;
  readonly humanChallengeCheckButton: Locator;

  // Error
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;

    // Header elements
    this.logo = page.getByRole('link', { name: /talent promo/i });
    this.heroTitle = page.getByRole('heading', { level: 1 });
    this.heroSubtitle = page.locator('p').filter({ hasText: /transform/i }).first();

    // Mode toggle buttons
    this.pasteResumeButton = page.getByRole('button', { name: /^paste$/i });
    this.uploadResumeButton = page.getByRole('button', { name: /upload/i });
    this.linkedinUrlButton = page.getByRole('button', { name: /linkedin/i });
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

    // Human verification challenge
    this.humanChallengeInput = page.getByPlaceholder(/your answer/i);
    this.humanChallengeCheckButton = page.getByRole('button', { name: /check/i });

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

  async switchToUploadMode() {
    await this.uploadResumeButton.click();
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
    await this.switchToLinkedInMode();
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

  /**
   * Answer the human verification challenge.
   * Reads the question, looks up the answer, fills it in, and clicks Check.
   * Returns early if the challenge is not visible (e.g., in error scenarios).
   */
  async answerHumanChallenge() {
    // Check if the challenge input is visible first
    const isInputVisible = await this.humanChallengeInput.isVisible().catch(() => false);
    if (!isInputVisible) {
      // No challenge visible - likely already passed or not shown
      return;
    }

    // Find the challenge question text (italic text ending with ?)
    const challengeQuestionElement = this.page.locator('.italic').filter({ hasText: /\?$/ });
    const isQuestionVisible = await challengeQuestionElement.isVisible().catch(() => false);

    let answer = 'yes'; // default fallback

    if (isQuestionVisible) {
      const challengeQuestion = (await challengeQuestionElement.textContent())?.toLowerCase().trim() || '';

      // Find the answer from our mapping
      for (const [question, ans] of Object.entries(HUMAN_CHALLENGE_ANSWERS)) {
        if (challengeQuestion.includes(question)) {
          answer = ans;
          break;
        }
      }
    }

    // Fill in the challenge answer
    await this.humanChallengeInput.fill(answer);

    // Click the Check button
    await this.humanChallengeCheckButton.click();

    // Wait for verification to pass
    await this.page.waitForTimeout(500);

    // Verify the "You're human!" message appears
    await expect(this.page.getByText(/you're human/i)).toBeVisible({ timeout: 5000 });
  }

  async startOptimization() {
    await this.startButton.click();
  }

  async expectHeroVisible() {
    await expect(this.heroTitle).toBeVisible();
  }

  async expectFormVisible() {
    // Default mode is paste - shows resume textarea
    await expect(this.resumeTextarea).toBeVisible();
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
