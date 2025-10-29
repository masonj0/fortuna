const { chromium } = require('playwright');
const { test, expect } = require('@playwright/test');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Navigate to the dashboard
  await page.goto('http://localhost:3001');

  // Wait for the initial loading to complete.
  // We expect the skeleton loaders to disappear.
  await expect(page.locator('div:has-text("Loading races...")')).toHaveCount(0, { timeout: 15000 });

  // Check for the manual override panel
  const overridePanel = page.locator('div:has-text("Fetch Failed: AtTheRaces")');
  await expect(overridePanel).toBeVisible({ timeout: 10000 });

  // Check for the text area with the correct URL
  // The date is a placeholder, as it can change. The important part is the base URL.
  const textArea = overridePanel.locator('textarea');
  await expect(textArea).toHaveAttribute('value', /https:\/\/www\.attheraces\.com\/racecards\/\d{4}-\d{2}-\d{2}/);


  // Take a screenshot for visual confirmation
  await page.screenshot({ path: 'manual-override-panel.png' });

  await browser.close();
})();
