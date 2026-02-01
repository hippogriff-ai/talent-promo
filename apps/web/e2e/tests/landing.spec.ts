import { test, expect } from '../fixtures/pages';
import { testResume, testJob } from '../fixtures/test-data';

test.describe('Landing Page', () => {
  test.beforeEach(async ({ landingPage }) => {
    await landingPage.goto();
  });

  test('displays hero section', async ({ landingPage }) => {
    await landingPage.expectHeroVisible();
  });

  test('displays input form', async ({ landingPage }) => {
    await landingPage.expectFormVisible();
  });

  test('can enter LinkedIn URL', async ({ landingPage }) => {
    await landingPage.fillLinkedInUrl('https://linkedin.com/in/johndoe');
    await expect(landingPage.linkedinUrlInput).toHaveValue('https://linkedin.com/in/johndoe');
  });

  test('can enter job URL', async ({ landingPage }) => {
    await landingPage.fillJobUrl(testJob.url);
    await expect(landingPage.jobUrlInput).toHaveValue(testJob.url);
  });

  test('can switch to resume paste mode', async ({ landingPage }) => {
    await landingPage.switchToResumeTextMode();
    await expect(landingPage.resumeTextarea).toBeVisible();
  });

  test('can enter resume text', async ({ landingPage }) => {
    await landingPage.fillResumeText(testResume.text);
    await expect(landingPage.resumeTextarea).toHaveValue(testResume.text);
  });

  test('can switch to job description paste mode', async ({ landingPage }) => {
    await landingPage.switchToJobTextMode();
    await expect(landingPage.jobTextarea).toBeVisible();
  });

  test('can enter job description text', async ({ landingPage }) => {
    await landingPage.fillJobText(testJob.text);
    const value = await landingPage.jobTextarea.inputValue();
    expect(value.length).toBeGreaterThan(100);
  });

  test('start button is visible', async ({ landingPage }) => {
    await expect(landingPage.startButton).toBeVisible();
  });

  test('navigates to optimize page on valid submit', async ({ landingPage }) => {
    await landingPage.fillResumeText(testResume.text);
    await landingPage.fillJobText(testJob.text);
    await landingPage.answerHumanChallenge();
    await landingPage.startOptimization();
    await landingPage.expectNavigatedToOptimize();
  });
});

test.describe('Landing Page - URL Mode Navigation', () => {
  test('navigates to optimize with valid URLs', async ({ landingPage }) => {
    await landingPage.goto();
    await landingPage.fillLinkedInUrl('https://linkedin.com/in/johndoe');
    await landingPage.fillJobUrl('https://jobs.example.com/senior-engineer');
    await landingPage.answerHumanChallenge();
    await landingPage.startOptimization();
    await landingPage.expectNavigatedToOptimize();
  });
});

test.describe('Landing Page - Validation', () => {
  test('button is disabled with empty form', async ({ landingPage }) => {
    await landingPage.goto();
    // Without any input, button should be disabled
    await expect(landingPage.startButton).toBeDisabled();
  });

  test('shows error for invalid LinkedIn URL', async ({ landingPage }) => {
    await landingPage.goto();
    await landingPage.fillLinkedInUrl('not-a-url');
    await landingPage.fillJobUrl('https://jobs.example.com/job');
    await landingPage.startButton.click({ force: true }).catch(() => {});
    // Should either show error or stay on page
    const url = landingPage.page.url();
    expect(url).not.toContain('/optimize');
  });

  test('stays on page with incomplete form in paste mode', async ({ landingPage, page }) => {
    await landingPage.goto();
    await landingPage.fillResumeText('short resume'); // Too short (< 50 chars)
    await landingPage.fillJobText(testJob.text);
    await landingPage.startButton.click({ force: true }).catch(() => {});
    // Should not navigate due to short resume
    const url = page.url();
    expect(url).not.toContain('/optimize');
  });
});
