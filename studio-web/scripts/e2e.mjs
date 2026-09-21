import { spawnSync } from "node:child_process";

const skip = "E2E_SKIP: playwright browsers unavailable";

function probe() {
  return spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      "import { chromium } from '@playwright/test'; const browser = await chromium.launch({ headless: true }); await browser.close();",
    ],
    { stdio: "pipe" },
  );
}

let launched;
try {
  launched = probe();
} catch (err) {
  console.log(skip);
  console.error(err instanceof Error ? err.message : String(err));
  process.exit(0);
}

if (!launched || launched.status !== 0) {
  const detail = launched?.stderr?.toString() || launched?.stdout?.toString() || "";
  console.log(skip);
  if (detail.trim()) console.error(detail.trim());
  process.exit(0);
}

const run = spawnSync("npx", ["playwright", "test"], { stdio: "inherit" });
process.exit(run.status === null ? 1 : run.status);
