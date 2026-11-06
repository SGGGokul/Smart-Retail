import { test, expect } from "@playwright/test";

test.describe("Phase 3 — RetailIQ Copilot UI E2E", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/ai-assistant");
  });

  test("1 & 2. Initial welcome state and telemetry snapshot layout (no overlap)", async ({ page }) => {
    // Verify welcome state text
    await expect(
      page.getByRole("heading", { name: "What would you like to know about your store?" })
    ).toBeVisible();

    // Verify snapshot metrics appear
    const footfallCard = page.locator("text=Daily Footfall").locator("..");
    const shelfCard = page.locator("text=Critical Shelves").locator("..");
    const queueCard = page.locator("text=Queue Status").locator("..");

    await expect(footfallCard).toBeVisible();
    await expect(shelfCard).toBeVisible();
    await expect(queueCard).toBeVisible();

    // Verify Footfall, Critical Shelves, and Queue Status do NOT overlap horizontally
    const footfallBox = await footfallCard.boundingBox();
    const shelfBox = await shelfCard.boundingBox();
    const queueBox = await queueCard.boundingBox();

    expect(footfallBox).not.toBeNull();
    expect(shelfBox).not.toBeNull();
    expect(queueBox).not.toBeNull();

    if (footfallBox && shelfBox && queueBox) {
      // In desktop view (1440px), items are in 3 columns:
      // Footfall right edge <= Shelf left edge
      expect(footfallBox.x + footfallBox.width).toBeLessThanOrEqual(shelfBox.x + 1);
      // Shelf right edge <= Queue left edge
      expect(shelfBox.x + shelfBox.width).toBeLessThanOrEqual(queueBox.x + 1);
    }
  });

  test("3. All 3 suggested starter prompts are readable, clickable, and submit questions", async ({ page }) => {
    const starterPrompts = [
      "Which aisle has the longest checkout queue?",
      "Which shelves need restocking first?",
      "Why did the latest critical shelf alert trigger?",
    ];

    for (const prompt of starterPrompts) {
      // Reload page to start fresh on welcome screen
      await page.goto("/ai-assistant");

      const promptBtn = page.getByRole("button", { name: prompt }).first();
      await expect(promptBtn).toBeVisible();
      await promptBtn.click();

      // Verify user message appears in thread
      const userBubble = page.locator(".bg-emerald-900", { hasText: prompt });
      await expect(userBubble).toBeVisible();

      // Verify assistant response appears
      const assistantBubble = page.locator(".rounded-tl-xs").first();
      await expect(assistantBubble).toBeVisible({ timeout: 5000 });
    }
  });

  test("4 & 5. Typing a custom message, Enter to send, Shift+Enter for newline", async ({ page }) => {
    const textarea = page.getByPlaceholder(/Ask about visitor counts/i);
    await expect(textarea).toBeVisible();

    // Test Shift+Enter inserts newline
    await textarea.fill("First line");
    await textarea.press("Shift+Enter");
    await textarea.type("Second line");
    await expect(textarea).toHaveValue("First line\nSecond line");

    // Clear and type single-line message
    await textarea.fill("How many customers visited today?");
    await textarea.press("Enter");

    // Input should clear
    await expect(textarea).toHaveValue("");

    // User message should appear
    await expect(page.locator("text=How many customers visited today?")).toBeVisible();

    // Assistant response should appear with traffic data
    await expect(page.locator("text=1,248 visitors")).toBeVisible({ timeout: 5000 });
  });

  test("6 & 7. Empty message cannot be submitted, send button disabled state", async ({ page }) => {
    const textarea = page.getByPlaceholder(/Ask about visitor counts/i);
    const sendButton = page.getByRole("button", { name: "Send message" });

    // When empty, send button should be disabled
    await expect(textarea).toHaveValue("");
    await expect(sendButton).toBeDisabled();

    // When typing spaces only, send button should be disabled
    await textarea.fill("   ");
    await expect(sendButton).toBeDisabled();

    // Pressing Enter with spaces should not submit
    await textarea.press("Enter");
    const userBubble = page.locator("text=You (Manager)");
    await expect(userBubble).toHaveCount(0);

    // Typing real text enables send button
    await textarea.fill("Hello");
    await expect(sendButton).toBeEnabled();
  });

  test("8. Conversation scrolls independently, composer remains visible", async ({ page }) => {
    const textarea = page.getByPlaceholder(/Ask about visitor counts/i);

    // Send multiple messages to generate a long thread
    const questions = [
      "How many customers visited today?",
      "What is the longest checkout queue?",
      "Which shelves need restocking first?",
      "Why did the latest critical shelf alert trigger?",
    ];

    for (const q of questions) {
      await textarea.fill(q);
      await textarea.press("Enter");
      await page.waitForTimeout(600);
    }

    // Verify composer container is still fully visible
    await expect(textarea).toBeVisible();
    const sendButton = page.getByRole("button", { name: "Send message" });
    await expect(sendButton).toBeVisible();

    // Verify conversation container has scrollable content
    const scrollableRegion = page.getByRole("region", { name: "Conversation message history" });
    const isScrollable = await scrollableRegion.evaluate((el) => el.scrollHeight > el.clientHeight);
    expect(isScrollable).toBe(true);
  });

  test("10. Network failure simulation: graceful error handling and local fallback", async ({ page }) => {
    // Intercept POST /api/v1/assistant/chat and abort network request
    await page.route("**/api/v1/assistant/chat", (route) => route.abort("failed"));

    const textarea = page.getByPlaceholder(/Ask about visitor counts/i);
    await textarea.fill("Which shelves need restocking first?");
    await textarea.press("Enter");

    // Frontend must not crash; fallback engine must respond cleanly
    await expect(page.locator("text=Which shelves need restocking first?")).toBeVisible();
    await expect(page.locator("text=Bakery in Aisle 7 needs restocking first")).toBeVisible({ timeout: 5000 });
  });

  test("11. Copy answer button provides feedback and contextual follow-ups work", async ({ page }) => {
    const textarea = page.getByPlaceholder(/Ask about visitor counts/i);
    await textarea.fill("Which shelves need restocking first?");
    await textarea.press("Enter");

    // Wait for response
    await page.waitForTimeout(600);

    // Verify copy button
    const copyButton = page.getByRole("button", { name: /Copy/i }).first();
    await expect(copyButton).toBeVisible();
    await copyButton.click();

    // Verify "Copied" feedback
    await expect(page.locator("text=Copied").first()).toBeVisible();

    // Verify contextual follow-up chip is clickable
    const followUp = page.locator("button", { hasText: "Why did the latest critical shelf alert trigger?" }).last();
    if (await followUp.isVisible()) {
      await followUp.click();
      await expect(page.locator("text=al-01 logged at 14:05").first()).toBeVisible({ timeout: 5000 });
    }
  });

  test("12. Greeting inputs ('hi', 'hello') return greeting capabilities, NEVER restocking", async ({ page }) => {
    const textarea = page.getByPlaceholder(/Ask about visitor counts/i);

    // Test "hi"
    await textarea.fill("hi");
    await textarea.press("Enter");

    // Wait for assistant response to render
    const assistantBubble = page.locator(".rounded-tl-xs div.whitespace-pre-wrap").first();
    await expect(assistantBubble).toBeVisible({ timeout: 5000 });
    const responseText = await assistantBubble.innerText();
    expect(responseText.toLowerCase()).toContain("hello! i am retailiq copilot");
    expect(responseText.toLowerCase()).not.toContain("aisle restocking audit");
    expect(responseText.toLowerCase()).not.toContain("bakery");

    // Reload page to start clean session
    await page.goto("/ai-assistant");
    const textarea2 = page.getByPlaceholder(/Ask about visitor counts/i);
    await textarea2.fill("hello");
    await textarea2.press("Enter");

    const assistantBubble2 = page.locator(".rounded-tl-xs div.whitespace-pre-wrap").first();
    await expect(assistantBubble2).toBeVisible({ timeout: 5000 });
    const responseText2 = await assistantBubble2.innerText();
    expect(responseText2.toLowerCase()).toContain("hello! i am retailiq copilot");
    expect(responseText2.toLowerCase()).not.toContain("aisle restocking audit");
  });
});
