import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  expect: {
    timeout: 5000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"], ["json", { outputFile: "reports/playwright-results.json" }]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    channel: "chrome",
  },
  projects: [
    {
      name: "Desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        channel: "chrome",
      },
    },
    {
      name: "Laptop",
      use: {
        viewport: { width: 1280, height: 800 },
        channel: "chrome",
      },
    },
    {
      name: "Tablet",
      use: {
        viewport: { width: 768, height: 1024 },
        channel: "chrome",
      },
    },
    {
      name: "Mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        channel: "chrome",
      },
    },
  ],
});
