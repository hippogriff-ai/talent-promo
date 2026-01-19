import { Page, Locator, expect } from '@playwright/test';

/**
 * Drafting Step Page Object
 *
 * Represents the interactive resume editing canvas.
 * This is the most complex page with rich text editing and suggestions.
 */
export class DraftingPage {
  readonly page: Page;

  // Editor (Tiptap)
  readonly editorContainer: Locator;
  readonly editorContent: Locator;
  readonly editorToolbar: Locator;

  // Toolbar buttons
  readonly boldButton: Locator;
  readonly italicButton: Locator;
  readonly underlineButton: Locator;
  readonly bulletListButton: Locator;
  readonly undoButton: Locator;
  readonly redoButton: Locator;

  // Suggestions panel
  readonly suggestionsPanel: Locator;
  readonly suggestionCards: Locator;
  readonly acceptSuggestionButtons: Locator;
  readonly declineSuggestionButtons: Locator;

  // Version history
  readonly versionHistoryButton: Locator;
  readonly versionHistoryPanel: Locator;
  readonly versionItems: Locator;
  readonly restoreVersionButton: Locator;

  // Validation
  readonly validationPanel: Locator;
  readonly validationWarnings: Locator;
  readonly validationErrors: Locator;

  // Actions
  readonly saveButton: Locator;
  readonly approveButton: Locator;
  readonly regenerateButton: Locator;
  readonly editorAssistButton: Locator;

  constructor(page: Page) {
    this.page = page;

    // Editor elements (Tiptap uses .ProseMirror class)
    this.editorContainer = page.locator('[data-testid="resume-editor"]');
    this.editorContent = page.locator('.ProseMirror, [contenteditable="true"]');
    this.editorToolbar = page.locator('[data-testid="editor-toolbar"]');

    // Toolbar buttons
    this.boldButton = page.getByRole('button', { name: /bold/i });
    this.italicButton = page.getByRole('button', { name: /italic/i });
    this.underlineButton = page.getByRole('button', { name: /underline/i });
    this.bulletListButton = page.getByRole('button', { name: /bullet|list/i });
    this.undoButton = page.getByRole('button', { name: /undo/i });
    this.redoButton = page.getByRole('button', { name: /redo/i });

    // Suggestions panel
    this.suggestionsPanel = page.locator('[data-testid="suggestions-panel"]');
    this.suggestionCards = page.locator('[data-testid="suggestion-card"]');
    this.acceptSuggestionButtons = page.getByRole('button', { name: /accept/i });
    this.declineSuggestionButtons = page.getByRole('button', { name: /decline/i });

    // Version history
    this.versionHistoryButton = page.getByRole('button', { name: /version|history/i });
    this.versionHistoryPanel = page.locator('[data-testid="version-history"]');
    this.versionItems = page.locator('[data-testid="version-item"]');
    this.restoreVersionButton = page.getByRole('button', { name: /restore/i });

    // Validation
    this.validationPanel = page.locator('[data-testid="validation-panel"]');
    this.validationWarnings = page.locator('[data-testid="validation-warning"]');
    this.validationErrors = page.locator('[data-testid="validation-error"]');

    // Action buttons
    this.saveButton = page.getByRole('button', { name: /save/i });
    // Match "Approve & Export" but not "Export - locked" (which is the nav button)
    this.approveButton = page.getByRole('button', { name: /approve.*export/i });
    this.regenerateButton = page.getByRole('button', { name: /regenerate/i });
    this.editorAssistButton = page.getByRole('button', { name: /assist|ai|help/i });
  }

  async waitForEditor(timeout = 120000) {
    // First wait for workflow to transition to drafting step
    const draftingStepActive = this.page.getByRole('button', { name: /drafting.*active/i });
    await draftingStepActive.waitFor({ state: 'visible', timeout }).catch(() => {
      // Step indicator might have different format, continue to wait for editor
    });
    // Then wait for the editor to appear
    await this.editorContent.waitFor({ state: 'visible', timeout });
  }

  async expectEditorVisible() {
    await expect(this.editorContent).toBeVisible();
  }

  async getEditorContent(): Promise<string> {
    return this.editorContent.innerText();
  }

  async getEditorHTML(): Promise<string> {
    return this.editorContent.innerHTML();
  }

  /**
   * Type text into the editor at current cursor position
   */
  async typeInEditor(text: string) {
    await this.editorContent.click();
    await this.editorContent.pressSequentially(text, { delay: 50 });
  }

  /**
   * Select all content and replace with new text
   */
  async replaceAllContent(newContent: string) {
    await this.editorContent.click();
    await this.page.keyboard.press('Meta+a'); // Select all
    await this.editorContent.pressSequentially(newContent, { delay: 20 });
  }

  /**
   * Select text in editor and apply formatting
   */
  async selectAndFormat(text: string, format: 'bold' | 'italic' | 'underline') {
    await this.editorContent.click();
    // Find and select the text
    await this.page.keyboard.press('Meta+f'); // Open find (if available)
    await this.page.keyboard.type(text);
    await this.page.keyboard.press('Escape');

    // Apply formatting
    switch (format) {
      case 'bold':
        await this.page.keyboard.press('Meta+b');
        break;
      case 'italic':
        await this.page.keyboard.press('Meta+i');
        break;
      case 'underline':
        await this.page.keyboard.press('Meta+u');
        break;
    }
  }

  /**
   * Apply bold to selected text using keyboard shortcut
   */
  async applyBold() {
    await this.page.keyboard.press('Meta+b');
  }

  /**
   * Apply italic to selected text using keyboard shortcut
   */
  async applyItalic() {
    await this.page.keyboard.press('Meta+i');
  }

  /**
   * Undo last action
   */
  async undo() {
    await this.page.keyboard.press('Meta+z');
  }

  /**
   * Redo last undone action
   */
  async redo() {
    await this.page.keyboard.press('Meta+Shift+z');
  }

  /**
   * Verify content contains expected text
   */
  async expectContentContains(text: string) {
    const content = await this.getEditorContent();
    expect(content).toContain(text);
  }

  /**
   * Verify content does not contain text
   */
  async expectContentNotContains(text: string) {
    const content = await this.getEditorContent();
    expect(content).not.toContain(text);
  }

  /**
   * Verify changes are saved (content matches expected)
   */
  async verifyChangesSaved(expectedText: string) {
    // Refresh or wait and check if content persists
    await this.page.waitForTimeout(500);
    const content = await this.getEditorContent();
    expect(content).toContain(expectedText);
  }

  // === Suggestions ===

  async expectSuggestionsVisible() {
    await expect(this.suggestionCards.first()).toBeVisible();
  }

  async getSuggestionCount(): Promise<number> {
    return this.suggestionCards.count();
  }

  async acceptSuggestion(index = 0) {
    await this.acceptSuggestionButtons.nth(index).click();
  }

  async declineSuggestion(index = 0) {
    await this.declineSuggestionButtons.nth(index).click();
  }

  async acceptAllSuggestions() {
    const count = await this.getSuggestionCount();
    for (let i = 0; i < count; i++) {
      await this.acceptSuggestionButtons.first().click();
      await this.page.waitForTimeout(300);
    }
  }

  // === Version History ===

  async openVersionHistory() {
    await this.versionHistoryButton.click();
  }

  async getVersionCount(): Promise<number> {
    return this.versionItems.count();
  }

  async restoreVersion(index = 0) {
    await this.restoreVersionButton.nth(index).click();
  }

  // === Actions ===

  async save() {
    await this.saveButton.click();
  }

  async approve() {
    await this.approveButton.click();
  }

  async regenerate() {
    await this.regenerateButton.click();
  }

  // === Complex Edit Scenarios ===

  /**
   * Edit a specific section of the resume
   */
  async editSection(sectionName: string, newContent: string) {
    // Find section heading
    const sectionHeading = this.page.locator(`text=${sectionName}`).first();
    await sectionHeading.click();

    // Move to next line and edit
    await this.page.keyboard.press('End');
    await this.page.keyboard.press('Enter');
    await this.page.keyboard.type(newContent, { delay: 30 });
  }

  /**
   * Delete a line containing specific text
   */
  async deleteLine(textToFind: string) {
    await this.editorContent.click();
    await this.page.keyboard.press('Meta+f');
    await this.page.keyboard.type(textToFind);
    await this.page.keyboard.press('Escape');
    await this.page.keyboard.press('Meta+Shift+k'); // Delete line
  }

  /**
   * Add a new bullet point under a section
   */
  async addBulletPoint(sectionName: string, bulletText: string) {
    const section = this.page.locator(`text=${sectionName}`).first();
    await section.click();
    await this.page.keyboard.press('End');
    await this.page.keyboard.press('Enter');
    await this.page.keyboard.type('• ' + bulletText, { delay: 30 });
  }
}
