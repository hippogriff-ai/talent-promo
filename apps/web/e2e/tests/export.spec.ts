import { test, expect } from '../fixtures/pages';

test.describe('Export Step', () => {
  test.skip('displays export options', async ({ exportPage, page }) => {
    await page.goto('/optimize?thread_id=test-export-thread');
    await exportPage.waitForExportComplete();
    await exportPage.expectExportResultsVisible();
  });

  test.skip('displays ATS report', async ({ exportPage, page }) => {
    await page.goto('/optimize?thread_id=test-export-thread');
    await exportPage.waitForExportComplete();
    await exportPage.expectATSReportVisible();
  });

  test.skip('displays LinkedIn suggestions', async ({ exportPage, page }) => {
    await page.goto('/optimize?thread_id=test-export-thread');
    await exportPage.waitForExportComplete();
    await exportPage.expectLinkedInVisible();
  });

  test.skip('can download PDF', async ({ exportPage, page }) => {
    await page.goto('/optimize?thread_id=test-export-thread');
    await exportPage.waitForExportComplete();

    const filename = await exportPage.downloadPDF();
    expect(filename).toMatch(/\.pdf$/i);
  });

  test.skip('can download DOCX', async ({ exportPage, page }) => {
    await page.goto('/optimize?thread_id=test-export-thread');
    await exportPage.waitForExportComplete();

    const filename = await exportPage.downloadDOCX();
    expect(filename).toMatch(/\.docx$/i);
  });

  test.skip('can copy LinkedIn headline', async ({ exportPage, page }) => {
    await page.goto('/optimize?thread_id=test-export-thread');
    await exportPage.waitForExportComplete();

    await exportPage.copyLinkedInHeadline();
    // Verify copy was successful (would need clipboard API access)
  });

  test.skip('can start new session', async ({ exportPage, page }) => {
    await page.goto('/optimize?thread_id=test-export-thread');
    await exportPage.waitForExportComplete();

    await exportPage.startNew();
    await expect(page).toHaveURL('/');
  });
});
