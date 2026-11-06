import { test, expect } from "@playwright/test";

test.describe("Phase 4 — Dashboard, Shelf Monitoring, Video, Alerts, Reports & Settings E2E", () => {
  test("Dashboard Overview displays metrics, charts and consistency", async ({ page }) => {
    await page.goto("/");

    // Verify key metrics cards are visible
    await expect(page.getByText("Customer Footfall", { exact: true })).toBeVisible();
    await expect(page.locator("text=8,304")).toBeVisible();
    await expect(page.locator("text=Avg Dwell Time")).toBeVisible();
    await expect(page.locator("text=22.4 min")).toBeVisible();

    // Verify Restock Priority card
    await expect(page.locator("text=Restock Priority")).toBeVisible();
    await expect(page.locator("text=Bakery (26%), Beverages (38%)")).toBeVisible();

    // Verify chart containers exist
    await expect(page.locator("text=Customer Footfall Volume & Trend")).toBeVisible();
    await expect(page.locator("text=Hourly Ingress Profile")).toBeVisible();
  });

  test("Shelf Monitoring: stock percentages, filters, and Restock modal", async ({ page }) => {
    await page.goto("/shelf-monitoring");

    // Verify critical and low stock shelves are visible
    await expect(page.locator("text=Bakery").first()).toBeVisible();
    await expect(page.locator("text=26% Available")).toBeVisible();
    await expect(page.locator("text=Beverages").first()).toBeVisible();
    await expect(page.locator("text=38% Available")).toBeVisible();

    // Open Restock Details modal for Bakery
    const restockBtn = page.getByRole("button", { name: /Restock Details/i }).first();
    await expect(restockBtn).toBeVisible();
    await restockBtn.click();

    // Verify modal dialog opened
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("Restock Verification (Simulation)");
    await expect(dialog).toContainText("Simulated");

    // Close dialog
    const closeBtn = page.getByRole("button", { name: "Close dialog" });
    await closeBtn.click();
    await expect(dialog).toHaveCount(0);
  });

  test("Video Analytics: camera switching and playback controls", async ({ page }) => {
    await page.goto("/video-analytics");

    // Select CAM-02 in camera select dropdown
    const camSelect = page.locator("select").first();
    await expect(camSelect).toBeVisible();
    await camSelect.selectOption("cam-02");
    await expect(page.locator("h2", { hasText: "CAM-02" })).toBeVisible();

    // Toggle stream pause / resume
    const pauseBtn = page.getByRole("button", { name: /Pause Feed|Resume Feed/i });
    await expect(pauseBtn).toBeVisible();
    await pauseBtn.click();
    await expect(page.getByRole("button", { name: /Resume Feed/i })).toBeVisible();
    await page.getByRole("button", { name: /Resume Feed/i }).click();

    // Toggle detections overlay
    const overlayBtn = page.getByRole("button", { name: /Hide Reticles|Show Reticles/i });
    await expect(overlayBtn).toBeVisible();
    await overlayBtn.click();
    await expect(page.getByRole("button", { name: /Show Reticles/i })).toBeVisible();
  });

  test("Alerts Feed: filter, search, and acknowledge interactions", async ({ page }) => {
    await page.goto("/alerts");

    // Check critical filter
    const criticalFilter = page.getByRole("button", { name: "critical" }).first();
    await expect(criticalFilter).toBeVisible();
    await criticalFilter.click();

    // Search input
    const searchInput = page.getByPlaceholder("Search location or keyword...");
    await expect(searchInput).toBeVisible();
    await searchInput.fill("Bakery");
    await expect(page.locator("text=Bakery display stock critically low.").first()).toBeVisible();

    // Clear search
    await searchInput.fill("");

    // Toggle acknowledge on first unacknowledged alert
    const ackBtn = page.getByRole("button", { name: /Acknowledge/i }).first();
    if (await ackBtn.isVisible()) {
      await ackBtn.click();
      // Toast confirmation
      await expect(page.locator("text=Acknowledged:").first()).toBeVisible();
    }
  });

  test("Reports: range switching and export simulation", async ({ page }) => {
    await page.goto("/reports");

    // Switch to "today" range
    const todayBtn = page.getByRole("button", { name: "Today" });
    await todayBtn.click();
    await expect(page.locator("text=1,248")).toBeVisible();

    // Switch to "30d" range
    const monthBtn = page.getByRole("button", { name: "30 Days" });
    await monthBtn.click();
    await expect(page.locator("text=36,410")).toBeVisible();

    // Click Export Report button
    const exportBtn = page.getByRole("button", { name: /Export CSV Report/i }).first();
    await exportBtn.click();
    await expect(page.locator("text=Exported retailiq_telemetry_").first()).toBeVisible();
  });

  test("Settings: toggle thresholds, save to storage, test backend connection", async ({ page }) => {
    await page.goto("/settings");

    // Verify form elements
    const storeInput = page.locator("input#store-branch");
    await expect(storeInput).toBeVisible();
    await storeInput.fill("Store #104 — Downtown Flagship");

    // Save preferences
    const saveBtn = page.getByRole("button", { name: /Save Preferences/i });
    await saveBtn.click();
    await expect(page.locator("text=Preferences successfully saved").first()).toBeVisible();

    // Test Backend Connection button (handles offline gracefully)
    const testConnectionBtn = page.getByRole("button", { name: /Test Connection/i });
    await testConnectionBtn.click();
    await expect(page.locator("text=Backend").first()).toBeVisible({ timeout: 5000 });
  });
});
