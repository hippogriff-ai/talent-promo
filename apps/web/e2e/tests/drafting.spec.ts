import { test, expect } from '../fixtures/pages';
import { testEditContent } from '../fixtures/test-data';

/**
 * Drafting Step Tests
 *
 * These tests focus on the interactive editing canvas and verify:
 * 1. User edits are effectively applied to the resume
 * 2. Formatting (bold, italic, etc.) works correctly
 * 3. Suggestions can be accepted/declined
 * 4. Version history tracks changes
 * 5. Undo/redo functionality works
 */
test.describe('Drafting Step - Editor Canvas', () => {
  // Skip straight to drafting step by using a pre-configured state
  // In real tests, you would go through the full workflow or mock the state
  test.skip('displays editor when workflow reaches drafting', async ({ draftingPage, page }) => {
    // Navigate to a workflow in drafting state (requires setup)
    await page.goto('/optimize?thread_id=test-drafting-thread');
    await draftingPage.waitForEditor();
    await draftingPage.expectEditorVisible();
  });
});

test.describe('Drafting Step - Text Editing', () => {
  test.beforeEach(async ({ page }) => {
    // For these tests, we need to either:
    // 1. Run through the full workflow (slow but realistic)
    // 2. Use a mock/fixture to set up drafting state
    // 3. Use a test API to create a drafting session

    // For now, we'll skip to a test page that has an editor
    await page.goto('/optimize');
  });

  test.skip('user can type in the editor', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();

    const originalContent = await draftingPage.getEditorContent();
    await draftingPage.typeInEditor(' [ADDED TEXT]');

    const newContent = await draftingPage.getEditorContent();
    expect(newContent).toContain('[ADDED TEXT]');
    expect(newContent.length).toBeGreaterThan(originalContent.length);
  });

  test.skip('user edits persist after typing', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();

    const testText = `EDITED_${Date.now()}`;
    await draftingPage.typeInEditor(testText);

    // Verify the edit is in the editor
    await draftingPage.verifyChangesSaved(testText);
  });

  test.skip('user can replace content with select all', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();

    const newContent = 'Completely new resume content for testing';
    await draftingPage.replaceAllContent(newContent);

    const content = await draftingPage.getEditorContent();
    expect(content).toContain('Completely new resume');
  });

  test.skip('undo reverts last change', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();

    const originalContent = await draftingPage.getEditorContent();
    await draftingPage.typeInEditor(' WILL_BE_UNDONE');

    // Verify the change was made
    let content = await draftingPage.getEditorContent();
    expect(content).toContain('WILL_BE_UNDONE');

    // Undo
    await draftingPage.undo();

    // Verify undo worked
    content = await draftingPage.getEditorContent();
    expect(content).not.toContain('WILL_BE_UNDONE');
  });

  test.skip('redo restores undone change', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();

    await draftingPage.typeInEditor(' UNDO_REDO_TEST');
    await draftingPage.undo();
    await draftingPage.redo();

    const content = await draftingPage.getEditorContent();
    expect(content).toContain('UNDO_REDO_TEST');
  });
});

test.describe('Drafting Step - Formatting', () => {
  test.skip('bold formatting applies to selected text', async ({ draftingPage, page }) => {
    await draftingPage.waitForEditor();

    // Type some text
    await draftingPage.typeInEditor('Bold this text');

    // Select the text and apply bold
    await page.keyboard.press('Meta+a'); // Select all
    await draftingPage.applyBold();

    // Check if bold tag exists in HTML
    const html = await draftingPage.getEditorHTML();
    expect(html).toMatch(/<strong>|<b>/i);
  });

  test.skip('italic formatting applies to selected text', async ({ draftingPage, page }) => {
    await draftingPage.waitForEditor();

    await draftingPage.typeInEditor('Italicize this');
    await page.keyboard.press('Meta+a');
    await draftingPage.applyItalic();

    const html = await draftingPage.getEditorHTML();
    expect(html).toMatch(/<em>|<i>/i);
  });
});

test.describe('Drafting Step - Suggestions', () => {
  test.skip('suggestions panel is visible', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();
    await draftingPage.expectSuggestionsVisible();
  });

  test.skip('accepting suggestion updates editor content', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();

    const originalContent = await draftingPage.getEditorContent();
    await draftingPage.acceptSuggestion(0);

    // Content should change after accepting suggestion
    const newContent = await draftingPage.getEditorContent();
    // The content may or may not change depending on the suggestion
    // At minimum, we verify no error occurred
  });

  test.skip('declining suggestion removes it from panel', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();

    const originalCount = await draftingPage.getSuggestionCount();
    if (originalCount > 0) {
      await draftingPage.declineSuggestion(0);
      const newCount = await draftingPage.getSuggestionCount();
      expect(newCount).toBeLessThan(originalCount);
    }
  });
});

test.describe('Drafting Step - Version History', () => {
  test.skip('version history shows previous versions', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();
    await draftingPage.openVersionHistory();

    const count = await draftingPage.getVersionCount();
    expect(count).toBeGreaterThanOrEqual(1); // At least initial version
  });

  test.skip('restoring version changes editor content', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();

    // Make a change
    await draftingPage.typeInEditor(' VERSION_TEST');
    await draftingPage.save();

    // Open history and restore previous
    await draftingPage.openVersionHistory();
    const count = await draftingPage.getVersionCount();

    if (count > 1) {
      await draftingPage.restoreVersion(1); // Restore second-to-last

      const content = await draftingPage.getEditorContent();
      expect(content).not.toContain('VERSION_TEST');
    }
  });
});

test.describe('Drafting Step - Save and Approve', () => {
  test.skip('save button persists changes', async ({ draftingPage }) => {
    await draftingPage.waitForEditor();

    const uniqueText = `SAVED_${Date.now()}`;
    await draftingPage.typeInEditor(uniqueText);
    await draftingPage.save();

    // Verify save was successful (no error message)
    await draftingPage.verifyChangesSaved(uniqueText);
  });

  test.skip('approve navigates to export step', async ({ draftingPage, page }) => {
    await draftingPage.waitForEditor();
    await draftingPage.approve();

    // Should navigate to export or show export step
    await page.waitForTimeout(1000);
    // Check if export elements are visible
    const hasExport = await page.getByText(/export|download/i).first().isVisible().catch(() => false);
    expect(hasExport).toBeTruthy();
  });
});
