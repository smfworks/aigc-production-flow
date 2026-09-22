# Studio shell (Phase 13)

Vite + React UI for one AIGC Studio. **New creation** is the home screen: a prompt, scope, a prunable task tree, director checkpoints, then **Send to Hermes**. Craft lanes are labels. Saved recipes are local. The agent-run strip polls still / plate / clip / stitch and says when the result is a fixture or awaiting stitch. **Download agent zip** is secondary.

Projects still has blank pack, template, and brain dump. The episode embeds the pack builder’s four stages (Script → Assets → Storyboard → Preview) and autosaves revisions. Zip import and the optional builder window stay secondary.

The pack builder source stays in `../app/` and is reused by the episode stages. Hermes `smf-h3-capture` is unchanged.

`npm run e2e` is the Playwright smoke. It prints `E2E_SKIP: playwright browsers unavailable` and exits 0 when Chromium cannot launch.

Docs: [../docs/STUDIO.md](../docs/STUDIO.md)

```bash
# from repo root
./scripts/dev-studio.sh web
```

http://localhost:5174 — API must already be on :8000 (`./scripts/dev-studio.sh api`), or use `docker compose -f docker-compose.studio.yml up` (nginx on 5174 proxies `/api`). Pack builder on :5173 is optional; **Open in Studio** from the builder stages a zip (`?handoff=`) when the API is reachable. Pick a project/episode, review the pack diff, Confirm import. Failure modes (studio down / auth) fall back to a manual Import pack zip. Never auto-generate.

Shareable routes:

- `#/projects/<projectId>`
- `#/projects/<projectId>/episodes/<episodeId>`
- `#/projects/<projectId>/episodes/<episodeId>/shots/<shotId>`
- `#/projects/<projectId>/episodes/<episodeId>/identity/<assetId>`

Docs: [../docs/STUDIO.md](../docs/STUDIO.md)
