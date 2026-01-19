import { test, expect } from '@playwright/test';
import { ArenaPage } from '../pages/arena.page';

/**
 * Arena E2E Tests
 *
 * Tests for the admin Arena A/B comparison UI.
 * Note: Some tests require ARENA_ADMIN_TOKEN to be set in the API environment.
 */

const TEST_ADMIN_TOKEN = process.env.ARENA_ADMIN_TOKEN || 'test-admin-token';

test.describe('Arena Page', () => {
  test.describe('Authentication', () => {
    test('should show login form when not authenticated', async ({ page }) => {
      const arena = new ArenaPage(page);
      await arena.goto();
      await arena.expectLoginFormVisible();
    });

    test('should show error for invalid token', async ({ page }) => {
      const arena = new ArenaPage(page);
      await arena.goto();
      await arena.login('invalid-token');
      // Should show error message
      await expect(page.getByText(/invalid admin token/i)).toBeVisible({ timeout: 5000 });
    });

    test('should authenticate with valid token and show dashboard', async ({ page }) => {
      // Skip if no admin token configured
      test.skip(!process.env.ARENA_ADMIN_TOKEN, 'ARENA_ADMIN_TOKEN not configured');

      const arena = new ArenaPage(page);
      await arena.goto();
      await arena.login(TEST_ADMIN_TOKEN);
      await arena.expectDashboardVisible();
    });
  });

  test.describe('Dashboard (with auth)', () => {
    // Skip all tests in this suite if no API configured
    test.skip(!process.env.ARENA_ADMIN_TOKEN, 'ARENA_ADMIN_TOKEN not configured - skipping auth tests');

    test.beforeEach(async ({ page }) => {
      // Store token in localStorage before navigating
      await page.goto('/admin/arena');
      await page.evaluate((token) => {
        localStorage.setItem('arena_admin_token', token);
      }, TEST_ADMIN_TOKEN);
      await page.reload();
      await page.waitForLoadState('networkidle');
    });

    test('should display page title', async ({ page }) => {
      const arena = new ArenaPage(page);
      await arena.expectPageVisible();
    });

    test('should display analytics dashboard', async ({ page }) => {
      const arena = new ArenaPage(page);
      // Wait for analytics to load
      await page.waitForTimeout(1000);
      await arena.expectDashboardVisible();
    });

    test('should display start comparison form', async ({ page }) => {
      const arena = new ArenaPage(page);
      await arena.expectStartFormVisible();
    });

    test('should toggle between URL and text input modes', async ({ page }) => {
      const arena = new ArenaPage(page);

      // Default should show URL inputs
      await expect(arena.linkedinUrlInput).toBeVisible();

      // Switch to text mode
      await arena.switchToTextMode();
      await expect(arena.resumeTextarea).toBeVisible();
      await expect(arena.jobTextarea).toBeVisible();

      // Switch back to URL mode
      await arena.switchToUrlMode();
      await expect(arena.linkedinUrlInput).toBeVisible();
    });

    test('should fill URL inputs', async ({ page }) => {
      const arena = new ArenaPage(page);

      await arena.fillLinkedInUrl('https://linkedin.com/in/testuser');
      await arena.fillJobUrl('https://example.com/job/123');

      await expect(arena.linkedinUrlInput).toHaveValue('https://linkedin.com/in/testuser');
      await expect(arena.jobUrlInput).toHaveValue('https://example.com/job/123');
    });

    test('should fill text inputs in paste mode', async ({ page }) => {
      const arena = new ArenaPage(page);

      await arena.fillResumeText('Test resume content');
      await arena.fillJobText('Test job description');

      await expect(arena.resumeTextarea).toHaveValue('Test resume content');
      await expect(arena.jobTextarea).toHaveValue('Test job description');
    });
  });

  test.describe('Comparison Flow (with auth)', () => {
    // Skip all tests in this suite if no API configured
    test.skip(!process.env.ARENA_ADMIN_TOKEN, 'ARENA_ADMIN_TOKEN not configured - skipping comparison tests');

    test.beforeEach(async ({ page }) => {
      await page.goto('/admin/arena');
      await page.evaluate((token) => {
        localStorage.setItem('arena_admin_token', token);
      }, TEST_ADMIN_TOKEN);
      await page.reload();
      await page.waitForLoadState('networkidle');
    });

    test('should start comparison and show variant panels', async ({ page }) => {
      const arena = new ArenaPage(page);

      // Fill form with text inputs (faster than URL fetching)
      await arena.fillResumeText('John Doe\nSoftware Engineer\n5 years experience in Python and JavaScript');
      await arena.fillJobText('Senior Software Engineer\nRequirements: 5+ years experience, Python, JavaScript');

      // Start comparison
      await arena.startComparison();

      // Wait for comparison to start
      await page.waitForTimeout(2000);

      // Should show active comparison
      await arena.expectActiveComparisonVisible();
      await arena.expectVariantPanelsVisible();
    });

    test('should show Start New button when comparison is active', async ({ page }) => {
      const arena = new ArenaPage(page);

      await arena.fillResumeText('Test resume');
      await arena.fillJobText('Test job');
      await arena.startComparison();

      await page.waitForTimeout(2000);

      // Should show Start New button
      await expect(arena.startNewButton).toBeVisible();
    });

    test('should return to form when clicking Start New', async ({ page }) => {
      const arena = new ArenaPage(page);

      await arena.fillResumeText('Test resume');
      await arena.fillJobText('Test job');
      await arena.startComparison();

      await page.waitForTimeout(2000);

      // Click Start New
      await arena.startNewComparison();

      // Should show form again
      await arena.expectStartFormVisible();
    });
  });

  test.describe('UI Components', () => {
    // Skip all tests in this suite if no API configured
    test.skip(!process.env.ARENA_ADMIN_TOKEN, 'ARENA_ADMIN_TOKEN not configured - skipping UI tests');

    test.beforeEach(async ({ page }) => {
      await page.goto('/admin/arena');
      await page.evaluate((token) => {
        localStorage.setItem('arena_admin_token', token);
      }, TEST_ADMIN_TOKEN);
      await page.reload();
      await page.waitForLoadState('networkidle');
    });

    test('should have proper form labels', async ({ page }) => {
      const arena = new ArenaPage(page);

      // Check URL mode labels
      await expect(page.getByText('LinkedIn URL')).toBeVisible();
      await expect(page.getByText('Job URL')).toBeVisible();

      // Switch to text mode and check labels
      await arena.switchToTextMode();
      await expect(page.getByText('Resume Text')).toBeVisible();
      await expect(page.getByText('Job Description')).toBeVisible();
    });

    test('should have Start Comparison button enabled', async ({ page }) => {
      const arena = new ArenaPage(page);
      await expect(arena.startButton).toBeEnabled();
    });

    test('should show checkbox for input mode toggle', async ({ page }) => {
      const arena = new ArenaPage(page);
      await expect(arena.useTextCheckbox).toBeVisible();
      await expect(page.getByText(/use pasted text/i)).toBeVisible();
    });
  });
});
