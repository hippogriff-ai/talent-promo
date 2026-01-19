import { Page, Locator, expect } from '@playwright/test';

/**
 * Export Step Page Object
 *
 * Represents the final export phase with ATS report and downloads.
 */
export class ExportPage {
  readonly page: Page;

  // ATS Report
  readonly atsReportCard: Locator;
  readonly atsScore: Locator;
  readonly keywordsSection: Locator;
  readonly matchedKeywords: Locator;
  readonly missingKeywords: Locator;
  readonly formattingIssues: Locator;
  readonly recommendations: Locator;

  // LinkedIn Suggestions
  readonly linkedinCard: Locator;
  readonly headlineSuggestion: Locator;
  readonly summarySuggestion: Locator;
  readonly copyButtons: Locator;

  // Download buttons
  readonly downloadPdfButton: Locator;
  readonly downloadDocxButton: Locator;
  readonly downloadTxtButton: Locator;
  readonly downloadJsonButton: Locator;
  readonly copyTextButton: Locator;

  // Progress
  readonly exportProgress: Locator;
  readonly exportStatus: Locator;

  // Actions
  readonly reExportButton: Locator;
  readonly startNewButton: Locator;
  readonly completeButton: Locator;

  constructor(page: Page) {
    this.page = page;

    // ATS Report
    this.atsReportCard = page.locator('[data-testid="ats-report"]');
    this.atsScore = page.locator('[data-testid="ats-score"]');
    this.keywordsSection = page.locator('[data-testid="keywords-section"]');
    this.matchedKeywords = page.locator('[data-testid="matched-keywords"]');
    this.missingKeywords = page.locator('[data-testid="missing-keywords"]');
    this.formattingIssues = page.locator('[data-testid="formatting-issues"]');
    this.recommendations = page.locator('[data-testid="recommendations"]');

    // LinkedIn
    this.linkedinCard = page.locator('[data-testid="linkedin-suggestions"]');
    this.headlineSuggestion = page.locator('[data-testid="linkedin-headline"]');
    this.summarySuggestion = page.locator('[data-testid="linkedin-summary"]');
    this.copyButtons = page.getByRole('button', { name: /copy/i });

    // Downloads - these are links in the UI, not buttons
    this.downloadPdfButton = page.getByRole('link', { name: /pdf/i });
    this.downloadDocxButton = page.getByRole('link', { name: /docx|word/i });
    this.downloadTxtButton = page.getByRole('link', { name: /txt|text/i });
    this.downloadJsonButton = page.getByRole('link', { name: /json/i });
    this.copyTextButton = page.getByRole('button', { name: /copy.*text/i });

    // Progress
    this.exportProgress = page.locator('[data-testid="export-progress"]');
    this.exportStatus = page.getByText(/exporting|generating|preparing/i);

    // Actions
    this.reExportButton = page.getByRole('button', { name: /re-export|regenerate/i });
    this.startNewButton = page.getByRole('button', { name: /start new|new session/i });
    this.completeButton = page.getByRole('button', { name: /complete|done|finish/i });
  }

  async waitForExportComplete(timeout = 60000) {
    await this.downloadPdfButton.waitFor({ state: 'visible', timeout });
  }

  async expectExportResultsVisible() {
    await expect(this.downloadPdfButton).toBeVisible();
  }

  async expectATSReportVisible() {
    await expect(this.page.getByText(/ats|keyword|score/i).first()).toBeVisible();
  }

  async expectLinkedInVisible() {
    await expect(this.page.getByText(/linkedin/i).first()).toBeVisible();
  }

  async getATSScore(): Promise<string> {
    return this.atsScore.innerText();
  }

  async downloadPDF() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.downloadPdfButton.click();
    const download = await downloadPromise;
    return download.suggestedFilename();
  }

  async downloadDOCX() {
    const downloadPromise = this.page.waitForEvent('download');
    await this.downloadDocxButton.click();
    const download = await downloadPromise;
    return download.suggestedFilename();
  }

  async copyLinkedInHeadline() {
    await this.copyButtons.first().click();
  }

  async reExport() {
    await this.reExportButton.click();
  }

  async startNew() {
    await this.startNewButton.click();
  }
}
