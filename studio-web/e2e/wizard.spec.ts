import { expect, test } from "@playwright/test";

test("create wizard prunes a task tree, shows lanes and checkpoints, and reloads a recipe", async ({
  page,
  request,
}) => {
  await page.goto("/#/create");
  await expect(page.getByTestId("create-wizard")).toBeVisible();
  await page.getByTestId("wizard-prompt").fill("Mara waits in the hall. She turns.");
  await page.getByTestId("wizard-continue").click();

  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByTestId("wizard-shots").fill("2");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByTestId("wizard-tone").fill("quiet dusk");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByTestId("wizard-scope")).toBeVisible();
  await page.getByTestId("wizard-audience").fill("late-night viewers");
  await page.getByTestId("wizard-deliverables").fill("one 9:16 cut");
  await page.getByTestId("wizard-negative").fill("no neon");
  await page.getByTestId("wizard-must-nots").fill("no logos");
  await page.getByTestId("platform-9-16").check();
  await page.getByTestId("wizard-claim-bans").fill("no medical claims");
  await page.getByRole("button", { name: "Continue" }).click();

  await page.getByTestId("wizard-cast").fill("Mara — lead, tired eyes");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByLabel("Audio and SFX notes").fill("room tone, no score");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByTestId("engine-honesty")).toContainText(/Comfy has not been called|stub/i);
  await expect(page.getByText("This does not call Comfy.")).toBeVisible();
  await page.getByTestId("wizard-approve-engines").click();

  await expect(page.getByTestId("task-tree")).toBeVisible();
  const plates = page.getByTestId("task-node-plates");
  await expect(plates).toHaveAttribute("data-executes", "false");
  await plates.getByRole("checkbox", { name: "Disable Plates" }).uncheck();
  await expect(page.getByTestId("task-node-hop-1:A")).toHaveAttribute("data-enabled", "false");
  await expect(page.getByTestId("task-node-review-gates").getByRole("checkbox")).toBeDisabled();
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByTestId("checkpoint-identities-draft")).toHaveAttribute("data-cleared", "false");
  await expect(page.getByTestId("checkpoint-gates-red")).toHaveAttribute("data-cleared", "false");
  await expect(page.getByTestId("checkpoint-hop1-unwatched")).toHaveAttribute("data-cleared", "false");
  await expect(page.getByTestId("checkpoint-no-signoff")).toHaveAttribute("data-cleared", "false");
  await expect(page.getByTestId("craft-lane-writer")).toHaveAttribute("data-ran", "false");
  await expect(page.getByTestId("craft-lane-note")).toContainText("not four agents");
  await page.getByTestId("wizard-finish").click();

  await expect(page.getByTestId("wizard-review")).toBeVisible();
  await expect(page.getByTestId("craft-lane-picture")).toHaveAttribute("data-ran", "false");
  await expect(page.getByTestId("checkpoint-plates-missing")).toHaveAttribute("data-cleared", "false");
  await page.getByTestId("recipe-name").fill("Short drama");
  await page.getByTestId("save-recipe").click();
  await expect(page.getByRole("status")).toContainText(/skill_short_drama_v0\.1\.json/);

  await page.getByTestId("send-hermes").click();
  await expect(page.getByTestId("hermes-handoff")).toBeVisible();
  await expect(page.getByTestId("hermes-handoff")).toContainText("hermes://aigc/brief?run=");

  const wizardUrl = page.url();
  const wizardId = wizardUrl.split("/create/")[1];
  expect(wizardId).toBeTruthy();
  const headers = {
    Authorization: "Bearer local-dev-token",
  };
  const runList = await request.get(`/api/create/wizard/${wizardId}`, { headers });
  expect(runList.ok()).toBeTruthy();
  const wizard = (await runList.json()) as {
    agent_run_id: string;
    gates_green: boolean;
    generate_ready: boolean;
    answers: { engine_mode: string; still_pref: string; clip_pref: string };
    director: { agents_ran: boolean; called_comfy: boolean };
  };
  expect(wizard.answers.engine_mode).toBe("approve");
  expect(wizard.answers.still_pref).toBe("comfy-qwen");
  expect(wizard.answers.clip_pref).toBe("comfy-h3");
  expect(wizard.gates_green).toBe(false);
  expect(wizard.generate_ready).toBe(false);
  expect(wizard.director.agents_ran).toBe(false);
  expect(wizard.director.called_comfy).toBe(false);
  const run = await request.get(`/api/agent-runs/${wizard.agent_run_id}`, { headers });
  expect(run.ok()).toBeTruthy();
  const body = (await run.json()) as {
    called_comfy: boolean;
    hermes_ran: boolean;
    steps: { kind: string; status: string; produced_mp4: boolean; called_comfy: boolean }[];
  };
  expect(body.called_comfy).toBe(false);
  expect(body.hermes_ran).toBe(false);
  expect(body.steps.at(-1)?.kind).toBe("stitch");
  expect(body.steps.at(-1)?.produced_mp4).toBe(false);
  expect(body.steps.filter((step) => step.kind === "still-plate").every((step) => step.status === "skipped")).toBe(
    true,
  );
  expect(body.steps.every((step) => step.called_comfy === false)).toBe(true);

  await page.getByRole("button", { name: "Start over" }).click();
  await expect(page.getByTestId("recipe-select")).toBeVisible();
  await page.getByTestId("recipe-select").selectOption({ label: "Short drama v0.1" });
  await page.getByTestId("load-recipe").click();
  await expect(page.getByTestId("wizard-prompt")).toHaveCount(0);
  await page.getByRole("button", { name: "Back" }).click();
  await expect(page.getByTestId("wizard-prompt")).toHaveValue("Mara waits in the hall. She turns.");
});
