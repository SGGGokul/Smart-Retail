import { test, expect } from "@playwright/test";

test.describe("Phase 4 — Dashboard, Shelf Monitoring, Video, Alerts, Reports & Settings E2E", () => {
  test("Dashboard Overview displays metrics, charts and consistency", async ({ page }) => {
    await page.goto("/");

    // Verify key metrics cards are visible
    await expect(page.getByText("Customer Footfall", { exact: true })).toBeVisible();
    await expect(page.locator("text=Avg Dwell Time")).toBeVisible();
    await expect(page.locator("text=Restock Priority")).toBeVisible();

    // Verify chart containers exist
    await expect(page.locator("text=Customer Footfall Volume & Trend")).toBeVisible();
    await expect(page.locator("text=Hourly Visitor Density Distribution")).toBeVisible();
  });

  test("Shelf Monitoring: live API integration and empty state", async ({ page }) => {
    await page.goto("/shelf-monitoring");

    // Verify page heading and description
    await expect(page.locator("h1")).toContainText("Shelf Monitoring");

    // Verify shelf health indicators section
    await expect(page.getByRole("region", { name: "Shelf health indicators" })).toBeVisible();

    // Verify search and filter controls exist
    const searchInput = page.getByPlaceholder(/Search aisle or category/i);
    await expect(searchInput).toBeVisible();
    await searchInput.fill("Aisle");
    await expect(searchInput).toHaveValue("Aisle");

    // Live backend returns empty shelf list (as YOLO11 doesn't fabricate shelves)
    await expect(page.getByText("No shelf bays found")).toBeVisible();
  });

  test("Video Analytics: Studio layout, upload dropzone, and job inspection", async ({ page }) => {
    await page.goto("/video-analytics");

    // Verify Studio headers and elements
    await expect(page.locator("h1")).toContainText("Computer Vision Studio");
    await expect(page.locator("text=FastAPI Video Ingestion")).toBeVisible();
    await expect(page.locator("text=Drop video or browse file")).toBeVisible();

    // Verify processed jobs table displays real video items
    await expect(page.locator("text=Processing Job History")).toBeVisible();
    await expect(page.locator("text=merl_retail_shopper_feed.mp4").first()).toBeVisible();
    await expect(page.locator("text=Completed").first()).toBeVisible();
  });

  test("Alerts Feed: filter, search, and acknowledge interactions", async ({ page }) => {
    await page.goto("/alerts");

    // Search input for real occupancy alert
    const searchInput = page.getByPlaceholder("Search location or keyword...");
    await expect(searchInput).toBeVisible();
    await searchInput.fill("Occupancy");
    await expect(page.locator("text=/Peak occupancy|Critical Store Occupancy/i").first()).toBeVisible();

    // Clear search
    await searchInput.fill("");

    // Toggle acknowledge on unacknowledged alert if available
    const ackBtn = page.getByRole("button", { name: "Acknowledge" }).first();
    if (await ackBtn.isVisible()) {
      await ackBtn.click();
      await expect(page.getByRole("button", { name: "Reopen" }).first()).toBeVisible();
    } else {
      // Or verify existing reopen / acknowledged button
      await expect(page.getByRole("button", { name: "Reopen" }).first()).toBeVisible();
    }
  });

  test("Reports: range switching and export simulation", async ({ page }) => {
    await page.goto("/reports");

    // Switch to "Today" range
    const todayBtn = page.getByRole("button", { name: "Today" });
    await todayBtn.click();
    await expect(todayBtn).toBeVisible();

    // Switch to "30 Days" range
    const monthBtn = page.getByRole("button", { name: "30 Days" });
    await monthBtn.click();
    await expect(monthBtn).toBeVisible();

    // Click Export Report button
    const exportBtn = page.getByRole("button", { name: /Export CSV Report/i }).first();
    await exportBtn.click();
    await expect(page.locator("text=/Exported retailiq_report_/i").first()).toBeVisible();
  });

  test("Settings: toggle thresholds, save to storage, test backend connection", async ({ page }) => {
    await page.goto("/settings");

    // Verify form elements
    const storeInput = page.locator("input#store-branch");
    await expect(storeInput).toBeVisible();
    await storeInput.fill("Store #104 — Downtown Flagship");

    // Save preferences
    const saveBtn = page.getByRole("button", { name: "Save", exact: true });
    await saveBtn.click();
    await expect(page.locator("text=Preferences saved successfully").first()).toBeVisible();

    // Test Backend Connection button (probes FastAPI backend)
    const testConnectionBtn = page.getByRole("button", { name: /Test Health/i });
    await testConnectionBtn.click();
    await expect(page.locator("text=Backend Connected").first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=Service Status:").first()).toBeVisible();
  });
});
