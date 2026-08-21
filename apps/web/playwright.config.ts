import { defineConfig, devices } from "@playwright/test";

const liveBaseURL = process.env.MIRSAD_LIVE_BASE_URL;
const e2eDatabaseUrl =
  process.env.MIRSAD_E2E_DATABASE_URL ?? "sqlite:///../../data/e2e.db";

if (!liveBaseURL && /(?:^|\/)mirsad\.db$/i.test(e2eDatabaseUrl)) {
  throw new Error("Playwright refuses to use the operator database");
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  timeout: 60_000,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: liveBaseURL ?? "http://127.0.0.1:5273",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: liveBaseURL
    ? undefined
    : [
    {
      command:
        "../../.venv/bin/python -m uvicorn mirsad_api.main:app --host 127.0.0.1 --port 8100",
      url: "http://127.0.0.1:8100/api/v1/health",
      reuseExistingServer: false,
      env: {
        MIRSAD_DATABASE_URL: e2eDatabaseUrl,
        MIRSAD_ENABLE_MOCK_CONNECTOR: "true",
        MIRSAD_SEMANTIC_RANKING_ENABLED: "false",
        MIRSAD_WEB_ORIGIN: "http://127.0.0.1:5273",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5273",
      url: "http://127.0.0.1:5273",
      reuseExistingServer: false,
      env: {
        VITE_API_PROXY: "http://127.0.0.1:8100",
        VITE_ENABLE_MOCK_CONNECTOR: "true",
      },
    },
      ],
});
