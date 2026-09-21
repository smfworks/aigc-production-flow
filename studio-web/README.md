# Studio shell (Phase 3)

Thin Vite + React UI around the studio API. The pack builder stays in `../app/`. Phase 3 adds a Task Center, hop-1 preview desk, and stub job enqueue/cancel/retry.

```bash
# from repo root
./scripts/dev-studio.sh web
```

http://localhost:5174 — API must already be on :8000 (`./scripts/dev-studio.sh api`). Pack builder on :5173 is optional; the shell iframes/links it.

Docs: [../docs/STUDIO.md](../docs/STUDIO.md)
