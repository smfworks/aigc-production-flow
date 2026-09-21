import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const TOKEN = process.env.STUDIO_API_TOKEN || "local-dev-token";

function apiHeaders(): Record<string, string> {
  return {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  };
}

async function episodeIdFromPage(page: Page): Promise<string> {
  await page.waitForURL(/episodes\//);
  const hash = new URL(page.url()).hash;
  const id = hash.split("/episodes/")[1]?.split("/")[0];
  expect(id, "episode id in the hash route").toBeTruthy();
  return id as string;
}

test("demo seed shows continuity and identity signals, then stub precheck", async ({ page, request }) => {
  await page.goto("/?import=smoke");
  await expect(page.getByTestId("import-hint")).toBeVisible();
  await page.getByTestId("seed-demo").click();
  await page.getByTestId("episode-card").click();

  await expect(page.getByTestId("continuity-panel")).toBeVisible();
  await expect(page.getByTestId("continuity-signal")).toHaveAttribute("data-state", "red");
  await expect(page.getByTestId("identity-store")).toBeVisible();
  await expect(page.getByTestId("identity-status").first()).toHaveAttribute("data-state", "red");
  await expect(page.getByTestId("playlist-scrubber")).toBeVisible();
  await expect(page.getByTestId("signoff-status")).toContainText("none yet");

  const episodeId = await episodeIdFromPage(page);
  const headers = apiHeaders();

  const identity = await request.get(`/api/episodes/${episodeId}/identity`, { headers });
  expect(identity.ok()).toBeTruthy();
  const store = (await identity.json()) as { sheets: { id: string }[] };
  expect(store.sheets.length).toBeGreaterThan(0);
  const approved = await request.post(`/api/episodes/${episodeId}/identity/${store.sheets[0].id}/approve`, {
    headers,
    data: { lock_keywords: "lead placeholder", note: "e2e" },
  });
  expect(approved.ok()).toBeTruthy();

  const signed = await request.post(`/api/episodes/${episodeId}/review/signoff`, {
    headers,
    data: { note: "e2e sign-off" },
  });
  expect(signed.ok()).toBeTruthy();

  const queued = await request.post("/api/jobs", {
    headers,
    data: { episode_id: episodeId, job_type: "batch-precheck" },
  });
  expect(queued.ok()).toBeTruthy();

  await expect
    .poll(async () => jobStatus(request, episodeId, headers), { timeout: 30_000 })
    .toBe("failed");

  await page.reload();
  await expect(page.getByTestId("identity-status").first()).toHaveAttribute("data-state", "green");
  await expect(page.getByTestId("continuity-signal")).toHaveAttribute("data-state", "red");
  await expect(page.getByTestId("signoff-status")).toContainText("local-dev");
  await expect(page.getByText("batch-precheck · failed")).toBeVisible();
});

test("new project opens pack stages without a zip", async ({ page }) => {
  await page.goto("/");
  const start = page.getByTestId("start-here");
  await start.getByLabel("Project name").fill("Phase 10 hallway");
  await start.getByRole("button", { name: "New project" }).click();
  await expect(page.getByTestId("pack-stage")).toBeVisible();
  await expect(page.getByTestId("pack-save-state")).toContainText(/Draft|Stored|blank|red/i);
  await expect(page.getByTestId("export-agent")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Optional zip" })).toBeVisible();
});

async function jobStatus(
  request: APIRequestContext,
  episodeId: string,
  headers: Record<string, string>,
): Promise<string> {
  const response = await request.get(`/api/episodes/${episodeId}/jobs`, { headers });
  if (!response.ok()) return `http-${response.status()}`;
  const jobs = (await response.json()) as { status?: string }[];
  return jobs[0]?.status || "missing";
}
