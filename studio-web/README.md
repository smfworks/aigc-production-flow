# Studio shell (Phase 7)

Thin Vite + React UI around the studio API. The pack builder stays in `../app/`. Phase 7 adds **org switch**, an in-app **bell**, a **continuity** panel, **demo seed**, and **backup** on top of sign-off, members, presence, shot comments, adapter health, budget, audit, EDL, and templates.

Docs: [../docs/STUDIO.md](../docs/STUDIO.md)

```bash
# from repo root
./scripts/dev-studio.sh web
```

http://localhost:5174 — API must already be on :8000 (`./scripts/dev-studio.sh api`), or use `docker compose -f docker-compose.studio.yml up` (nginx on 5174 proxies `/api`). Pack builder on :5173 is optional; **Open in Studio** from the builder lands here with an import hint.

Shareable routes:

- `#/projects/<projectId>`
- `#/projects/<projectId>/episodes/<episodeId>`
- `#/projects/<projectId>/episodes/<episodeId>/shots/<shotId>`

Docs: [../docs/STUDIO.md](../docs/STUDIO.md)
