import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:1515";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 35_000,
  expect: {
    timeout: 12_000,
  },
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command:
      "RACE_E2E_FAST=1 DJANGO_DB_PATH=.e2e.sqlite3 .venv/bin/python scripts/serve.py --port 1515 --skip-build",
    url: "http://127.0.0.1:1515/health/",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
