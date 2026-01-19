import { test as base } from '@playwright/test';
import { LandingPage } from '../pages/landing.page';
import { ResearchPage } from '../pages/research.page';
import { DiscoveryPage } from '../pages/discovery.page';
import { DraftingPage } from '../pages/drafting.page';
import { ExportPage } from '../pages/export.page';

/**
 * Extended test fixtures with page objects
 *
 * Usage:
 * import { test, expect } from '../fixtures/pages';
 *
 * test('my test', async ({ landingPage, draftingPage }) => {
 *   await landingPage.goto();
 *   // ...
 * });
 */
type Pages = {
  landingPage: LandingPage;
  researchPage: ResearchPage;
  discoveryPage: DiscoveryPage;
  draftingPage: DraftingPage;
  exportPage: ExportPage;
};

export const test = base.extend<Pages>({
  landingPage: async ({ page }, use) => {
    const landingPage = new LandingPage(page);
    await use(landingPage);
  },

  researchPage: async ({ page }, use) => {
    const researchPage = new ResearchPage(page);
    await use(researchPage);
  },

  discoveryPage: async ({ page }, use) => {
    const discoveryPage = new DiscoveryPage(page);
    await use(discoveryPage);
  },

  draftingPage: async ({ page }, use) => {
    const draftingPage = new DraftingPage(page);
    await use(draftingPage);
  },

  exportPage: async ({ page }, use) => {
    const exportPage = new ExportPage(page);
    await use(exportPage);
  },
});

export { expect } from '@playwright/test';
