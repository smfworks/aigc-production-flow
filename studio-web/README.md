# Studio shell (Phase 9)

Thin Vite + React UI around the studio API. The pack builder stays in `../app/`. Phase 9 adds the **writer/art role matrix**, **episode reorder**, a **soft playlist scrubber**, and **identity unapprove / keyword edit** on top of the identity store, pack revision diff, and builder auto-import.

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
