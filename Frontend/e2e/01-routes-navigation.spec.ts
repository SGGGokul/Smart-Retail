import { test, expect } from "@playwright/test";

const ROUTES = [
  { path: "/", heading: "Store Intelligence" },
  { path: "/video-analytics", heading: "Computer Vision Studio" },
  { path: "/customer-analytics", heading: "Customer Analytics" },
  { path: "/shelf-monitoring", heading: "Shelf Monitoring" },
  { path: "/alerts", heading: "Alerts" },
  { path: "/reports", heading: "Reports" },
  { path: "/ai-assistant", heading: "RetailIQ Copilot" },
  { path: "/settings", heading: "Settings" },
];

test.describe("Phase 2 — Route Health and Navigation E2E", () => {
  for (const route of ROUTES) {
    test(`Route ${route.path} loads cleanly without fatal errors`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          consoleErrors.push(msg.text());
        }
      });

      const response = await page.goto(route.path);
      expect(response?.status()).toBe(200);

      // Verify no fatal Next.js error overlays
      const nextError = page.locator("[data-nextjs-dialog-header], [data-nextjs-toast-errors]");
      await expect(nextError).toHaveCount(0);

      // Verify heading or page content appears
      const heading = page.locator("h1");
      await expect(heading).toContainText(route.heading);

      // Verify header and store selector render
      const storeButton = page.getByRole("button", { name: /Store #104/i }).first();
      await expect(storeButton).toBeVisible();

      // Check FastAPI status badge in topnav
      const backendIndicator = page.getByRole("status", { name: /fastapi service status/i });
      await expect(backendIndicator).toBeVisible();

      // Verify no unintended horizontal scrollbar
      const hasHorizontalScroll = await page.evaluate(() => {
        return document.documentElement.scrollWidth > window.innerWidth + 2;
      });
      expect(hasHorizontalScroll).toBe(false);

      // Verify no critical uncaught console errors
      const criticalErrors = consoleErrors.filter(
        (err) =>
          !err.includes("favicon") &&
          !err.includes("Failed to load resource") &&
          !err.includes("hydration")
      );
      expect(criticalErrors).toHaveLength(0);
    });
  }

  test("Sidebar navigation items have correct active states", async ({ page }) => {
    await page.goto("/");

    // Verify Overview link is active
    const overviewLink = page.locator("aside nav a", { hasText: "Overview" });
    await expect(overviewLink).toHaveAttribute("aria-current", "page");

    // Click Shelf Monitoring in sidebar
    const shelfLink = page.locator("aside nav a", { hasText: "Shelf Monitoring" });
    await shelfLink.click();
    await expect(page).toHaveURL("/shelf-monitoring");
    await expect(shelfLink).toHaveAttribute("aria-current", "page");

    // Click RetailIQ Copilot in sidebar
    const copilotLink = page.locator("aside nav a", { hasText: "RetailIQ Copilot" });
    await copilotLink.click();
    await expect(page).toHaveURL("/ai-assistant");
    await expect(copilotLink).toHaveAttribute("aria-current", "page");
  });

  test("Store selector dropdown opens and closes", async ({ page }) => {
    await page.goto("/");
    const selectorButton = page.getByRole("button", { name: /Store #104/i }).first();
    await selectorButton.click();

    // Verify dropdown items are visible
    const branchOption = page.getByRole("button", { name: /Store #202/i });
    await expect(branchOption).toBeVisible();

    // Click to select branch
    await branchOption.click();
    await expect(page.getByRole("button", { name: /Store #202/i }).first()).toBeVisible();
  });
});
