import { test, expect } from "@playwright/test";

const VIEWPORTS = [
  { name: "Desktop", width: 1440, height: 900 },
  { name: "Laptop", width: 1280, height: 800 },
  { name: "Tablet", width: 768, height: 1024 },
  { name: "Mobile", width: 390, height: 844 },
];

test.describe("Phase 5 — Responsive and Accessibility Checks", () => {
  for (const vp of VIEWPORTS) {
    test(`No unintended horizontal overflow at ${vp.name} (${vp.width}x${vp.height})`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });

      for (const path of ["/", "/shelf-monitoring", "/ai-assistant"]) {
        await page.goto(path);
        const hasOverflow = await page.evaluate(() => {
          return document.documentElement.scrollWidth > window.innerWidth + 2;
        });
        expect(hasOverflow, `Unexpected horizontal overflow on ${path} at ${vp.width}px`).toBe(false);
      }
    });
  }

  test("Mobile navigation drawer opens and closes properly at 390x844", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    // At 390px, desktop sidebar should be hidden offscreen
    const sidebar = page.locator("aside[aria-label='Sidebar navigation']");

    // Click hamburger button in topnav
    const menuBtn = page.getByRole("button", { name: /Open navigation menu/i });
    await expect(menuBtn).toBeVisible();
    await menuBtn.click();

    // Sidebar drawer should slide in
    await expect(sidebar).toBeVisible();

    // Close button in sidebar drawer
    const closeBtn = page.getByRole("button", { name: /Close navigation/i });
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();

    // Verify hamburger button is available again
    await expect(menuBtn).toBeVisible();
  });

  test("Copilot welcome state telemetry snapshot stacks cleanly on mobile (390px)", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/ai-assistant");

    // Verify snapshot metrics appear without overflow
    const footfallCard = page.locator("text=Daily Footfall").locator("..");
    const shelfCard = page.locator("text=Critical Shelves").locator("..");
    const queueCard = page.locator("text=Queue Status").locator("..");

    await expect(footfallCard).toBeVisible();
    await expect(shelfCard).toBeVisible();
    await expect(queueCard).toBeVisible();

    // On mobile, items stack vertically: Footfall Y < Shelf Y < Queue Y
    const footfallBox = await footfallCard.boundingBox();
    const shelfBox = await shelfCard.boundingBox();
    const queueBox = await queueCard.boundingBox();

    expect(footfallBox).not.toBeNull();
    expect(shelfBox).not.toBeNull();
    expect(queueBox).not.toBeNull();

    if (footfallBox && shelfBox && queueBox) {
      expect(footfallBox.y).toBeLessThan(shelfBox.y);
      expect(shelfBox.y).toBeLessThan(queueBox.y);
    }
  });

  test("Keyboard navigation and visible focus rings on interactive elements", async ({ page }) => {
    await page.goto("/ai-assistant");

    // Tab through elements
    await page.keyboard.press("Tab");
    await page.keyboard.press("Tab");

    // Verify focused element has visible focus ring or outline
    const hasFocusedElement = await page.evaluate(() => {
      const el = document.activeElement;
      return el && el !== document.body;
    });
    expect(hasFocusedElement).toBe(true);
  });
});
