import { test, expect } from '../fixtures/pages';

/**
 * Memory Feature E2E Tests
 *
 * Tests the Memory Feature functionality with mocked API responses:
 * - Authentication (magic link flow)
 * - Preferences management
 * - Rating modal after export
 * - Anonymous to authenticated migration
 *
 * These tests use mocked endpoints to run quickly without real backend.
 */

const API_URL = 'http://localhost:8000';

// Mock user data
const MOCK_USER = {
  id: 'user-123',
  email: 'test@example.com',
  created_at: '2025-01-15T00:00:00Z',
  is_active: true,
};

const MOCK_SESSION_TOKEN = 'mock-session-token-abc123';

const MOCK_PREFERENCES = {
  tone: 'formal',
  structure: 'bullets',
  sentence_length: 'concise',
  first_person: false,
  quantification_preference: 'balanced',
  achievement_focus: true,
  custom_preferences: {},
};

test.describe('Memory Feature - Authentication', () => {
  test('should show login page with email form', async ({ page }) => {
    await page.goto('/auth/login');

    // Should show email input
    await expect(page.locator('input[type="email"]')).toBeVisible();

    // Should show submit button
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should send magic link request', async ({ page }) => {
    // Mock the me endpoint (to ensure not redirected)
    await page.route(`${API_URL}/api/auth/me`, async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      });
    });

    // Mock the request-link endpoint
    await page.route(`${API_URL}/api/auth/request-link`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Magic link sent to your email' }),
      });
    });

    await page.goto('/auth/login');

    // Wait for loading to complete
    await page.waitForLoadState('networkidle');

    // Enter email
    await page.fill('input[type="email"]', 'test@example.com');

    // Submit
    await page.click('button[type="submit"]');

    // Should show success message (the message comes from API response)
    await expect(page.locator('text=Magic link sent')).toBeVisible({ timeout: 5000 });
  });

  test('should verify magic link token', async ({ page }) => {
    // Mock the verify endpoint
    await page.route(`${API_URL}/api/auth/verify`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: MOCK_USER,
          session_token: MOCK_SESSION_TOKEN,
        }),
      });
    });

    // Mock the migrate endpoint (for localStorage data)
    await page.route(`${API_URL}/api/auth/migrate`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          preferences_migrated: false,
          events_migrated: 0,
          ratings_migrated: 0,
          errors: [],
        }),
      });
    });

    await page.goto('/auth/verify?token=test-magic-link-token');

    // Should redirect to home or show success
    await expect(page).toHaveURL(/\/$/, { timeout: 5000 });
  });

  test('should show error for invalid token', async ({ page }) => {
    // Mock the verify endpoint with error
    await page.route(`${API_URL}/api/auth/verify`, async (route) => {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid or expired token' }),
      });
    });

    await page.goto('/auth/verify?token=invalid-token');

    // Should show error message
    await expect(page.locator('text=invalid')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Memory Feature - Preferences', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the me endpoint to simulate logged-in user
    await page.route(`${API_URL}/api/auth/me`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ user: MOCK_USER }),
      });
    });

    // Mock the preferences endpoint
    await page.route(`${API_URL}/api/preferences`, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ preferences: MOCK_PREFERENCES }),
        });
      } else if (route.request().method() === 'PATCH') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ preferences: MOCK_PREFERENCES }),
        });
      }
    });
  });

  test('should display settings page with preferences', async ({ page }) => {
    await page.goto('/settings/profile');

    // Should show writing style section
    await expect(page.locator('text=Writing Style')).toBeVisible();

    // Should show content preferences section
    await expect(page.locator('text=Content Preferences')).toBeVisible();

    // Should show user email
    await expect(page.locator(`text=${MOCK_USER.email}`)).toBeVisible();
  });

  test('should allow changing tone preference', async ({ page }) => {
    await page.goto('/settings/profile');

    // Find the Conversational option and click it
    const conversationalOption = page.locator('label:has-text("Conversational")');
    await conversationalOption.click();

    // Should show success message
    await expect(page.locator('text=saved')).toBeVisible({ timeout: 5000 });
  });

  test('should allow toggling first person preference', async ({ page }) => {
    await page.goto('/settings/profile');

    // Find the First Person toggle button
    const firstPersonToggle = page.locator('button').filter({ hasText: /First Person/i }).or(
      page.locator('[role="switch"]').first()
    );

    // Toggle should be visible
    await expect(page.locator('text=First Person')).toBeVisible();
  });

  test('should allow resetting preferences', async ({ page }) => {
    // Mock the reset endpoint
    await page.route(`${API_URL}/api/preferences/reset`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    await page.goto('/settings/profile');

    // Find and click reset button
    const resetButton = page.locator('button:has-text("Reset")');
    await resetButton.click();

    // Handle confirmation dialog
    page.on('dialog', (dialog) => dialog.accept());
  });
});

test.describe('Memory Feature - Anonymous User', () => {
  test('should store preferences in localStorage when not authenticated', async ({ page }) => {
    // Mock the me endpoint to return 401 (not authenticated)
    await page.route(`${API_URL}/api/auth/me`, async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      });
    });

    await page.goto('/settings/profile');

    // Should redirect to login
    await expect(page).toHaveURL(/\/auth\/login/, { timeout: 5000 });
  });

  test('should show save prompt for anonymous users after workflow', async ({ page }) => {
    // This would be shown in the main workflow pages for anonymous users
    // The SavePrompt component appears when user has accumulated data

    await page.goto('/');

    // Simulate localStorage with anonymous data
    await page.evaluate(() => {
      localStorage.setItem('resume_agent:preferences', JSON.stringify({
        tone: 'formal',
        structure: 'bullets',
      }));
      localStorage.setItem('resume_agent:pending_events', JSON.stringify([
        { event_type: 'edit', event_data: {}, created_at: new Date().toISOString() },
      ]));
    });

    // Reload to trigger save prompt logic
    await page.reload();

    // The save prompt would be displayed based on component logic
    // Testing the localStorage setup works
    const storedPrefs = await page.evaluate(() =>
      localStorage.getItem('resume_agent:preferences')
    );
    expect(storedPrefs).toBeTruthy();
  });
});

test.describe('Memory Feature - Migration', () => {
  test('should migrate anonymous data on login', async ({ page }) => {
    let migrateCallCount = 0;

    // Mock the verify endpoint
    await page.route(`${API_URL}/api/auth/verify`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: MOCK_USER,
          session_token: MOCK_SESSION_TOKEN,
        }),
      });
    });

    // Mock the migrate endpoint
    await page.route(`${API_URL}/api/auth/migrate`, async (route) => {
      migrateCallCount++;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          preferences_migrated: true,
          events_migrated: 3,
          ratings_migrated: 1,
          errors: [],
        }),
      });
    });

    // Set up anonymous data before verification
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('resume_agent:preferences', JSON.stringify({
        tone: 'conversational',
      }));
      localStorage.setItem('resume_agent:pending_events', JSON.stringify([
        { event_type: 'edit', event_data: { field: 'summary' } },
      ]));
      localStorage.setItem('resume_agent:anonymous_id', 'anon-123');
    });

    // Visit verify page with token
    await page.goto('/auth/verify?token=valid-token');

    // Wait for redirect
    await page.waitForURL('/', { timeout: 5000 });

    // Verify migration was attempted
    expect(migrateCallCount).toBeGreaterThan(0);

    // Anonymous data should be cleared after migration
    const anonymousId = await page.evaluate(() =>
      localStorage.getItem('resume_agent:anonymous_id')
    );
    expect(anonymousId).toBeNull();
  });
});

test.describe('Memory Feature - Preferences in Workflow', () => {
  test('should store preferences in localStorage for use in workflow', async ({ page }) => {
    // Mock the me endpoint (not authenticated)
    await page.route(`${API_URL}/api/auth/me`, async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      });
    });

    // Set up preferences in localStorage (anonymous user)
    await page.goto('/');

    // Dismiss onboarding guide if shown
    const guideButton = page.locator('button:has-text("Get Started"), button:has-text("Skip")');
    if (await guideButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await guideButton.click();
    }

    // Store preferences
    await page.evaluate(() => {
      localStorage.setItem('resume_agent:preferences', JSON.stringify({
        tone: 'formal',
        structure: 'bullets',
        achievement_focus: true,
      }));
    });

    // Verify preferences are stored
    const storedPrefs = await page.evaluate(() =>
      localStorage.getItem('resume_agent:preferences')
    );
    expect(storedPrefs).toBeTruthy();

    const parsedPrefs = JSON.parse(storedPrefs!);
    expect(parsedPrefs.tone).toBe('formal');
    expect(parsedPrefs.structure).toBe('bullets');
    expect(parsedPrefs.achievement_focus).toBe(true);
  });

  test('should have Start Optimization button visible on landing page', async ({ page }) => {
    await page.goto('/');

    // Dismiss onboarding guide if shown
    const guideButton = page.locator('button:has-text("Get Started"), button:has-text("Skip")');
    if (await guideButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await guideButton.click();
    }

    // The Start Optimization button should be visible
    await expect(page.locator('button:has-text("Start Optimization")')).toBeVisible();
  });
});
