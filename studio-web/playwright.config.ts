import { defineConfig, devices } from "@playwright/test";

const api = "http://127.0.0.1:8000";
const web = "http://127.0.0.1:5174";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  retries: 0,
  reporter: "line",
  use: {
    baseURL: web,
    headless: true,
    trace: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        "rm -f /tmp/aigc-phase9-e2e.db && rm -rf /tmp/aigc-phase9-e2e-media && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../studio",
      url: `${api}/healthz`,
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        STUDIO_DATABASE_URL: "sqlite:////tmp/aigc-phase9-e2e.db",
        STUDIO_MEDIA_ROOT: "/tmp/aigc-phase9-e2e-media",
        STUDIO_JOB_WORKER: "thread",
        STUDIO_AUTH_MODE: "local",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5174",
      url: web,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
