# Studio shell (Phase 4)

Thin Vite + React UI around the studio API. The pack builder stays in `../app/`. Phase 4 adds a Budget dashboard, audit log, EDL / shot-playlist export, project adapter/budget settings, and New from template.

```bash
# from repo root
./scripts/dev-studio.sh web
```

http://localhost:5174 — API must already be on :8000 (`./scripts/dev-studio.sh api`). Pack builder on :5173 is optional; the shell iframes/links it.

Docs: [../docs/STUDIO.md](../docs/STUDIO.md)
