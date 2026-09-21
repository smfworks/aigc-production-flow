# Studio shell (Phase 5)

Thin Vite + React UI around the studio API. The pack builder stays in `../app/`. Phase 5 adds org members, own-role chrome, presence chips, shot comments, an adapter health strip, and honest local-vs-S3 labels on top of the Phase 4 budget / audit / EDL / template desks.

```bash
# from repo root
./scripts/dev-studio.sh web
```

http://localhost:5174 — API must already be on :8000 (`./scripts/dev-studio.sh api`), or use `docker compose -f docker-compose.studio.yml up` (nginx on 5174 proxies `/api`). Pack builder on :5173 is optional; the shell iframes/links it.

Docs: [../docs/STUDIO.md](../docs/STUDIO.md)
