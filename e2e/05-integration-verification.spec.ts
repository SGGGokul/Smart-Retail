import { test, expect } from "@playwright/test";

test.describe("Stage 3 — Full E2E Integration and Backend Verification", () => {
  test("Dashboard displays live FastAPI connection and real telemetry", async ({ page }) => {
    await page.goto("/");

    // Verify topbar backend health status
    const backendStatus = page.getByRole("status", { name: /fastapi service status/i });
    await expect(backendStatus).toBeVisible();
    await expect(backendStatus).toContainText(/online/i);

    // Verify metrics reflect real inference results
    const customerCard = page.getByText("Customer Footfall", { exact: true });
    await expect(customerCard).toBeVisible();
    await expect(page.locator("text=4 detected from 2 video clip(s)").first()).toBeVisible();
  });

  test("Video Analytics Studio displays genuine processed inference jobs", async ({ page }) => {
    await page.goto("/video-analytics");

    // Verify page header
    await expect(page.locator("h1")).toContainText("Computer Vision Studio");

    // Verify uploaded genuine MERL retail feed appears in job history
    const jobItem = page.getByText("merl_retail_shopper_feed.mp4").first();
    await expect(jobItem).toBeVisible();

    // Verify inference detections
    await expect(page.locator("text=50 frames").first()).toBeVisible();
  });

  test("AI Assistant communicates with backend copilot", async ({ page }) => {
    await page.goto("/ai-assistant");

    // Verify page title
    await expect(page.locator("h1")).toContainText("RetailIQ Copilot");

    // Type query
    const input = page.getByPlaceholder(/Ask about visitor counts/i);
    await input.fill("How many customers visited today?");

    // Click send
    const sendBtn = page.getByRole("button", { name: "Send message" });
    await sendBtn.click();

    // Verify grounded response
    await expect(page.locator("text=detected today across processed video")).toBeVisible({ timeout: 10000 });
  });

  test("Settings page verifies FastAPI health probe", async ({ page }) => {
    await page.goto("/settings");

    // Verify settings heading
    await expect(page.locator("h1")).toContainText("Settings");

    // Verify backend service health section
    await expect(page.locator("text=FastAPI Backend")).toBeVisible();
    await expect(page.locator("text=online").first()).toBeVisible();
  });
});
