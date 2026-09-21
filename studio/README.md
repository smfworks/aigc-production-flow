# AIGC studio API (Phase 3)

FastAPI spine for projects, episodes, pack zip revisions, review states, comments, media (including costume and hop-1 preview), shots, candidate confirm, jobs, adapters, and the hop-1 preview desk.

Operator docs: [../docs/STUDIO.md](../docs/STUDIO.md).

```bash
# from repo root
./scripts/dev-studio.sh api      # HTTP + in-process job worker
./scripts/dev-studio.sh worker   # optional standalone poller (API should set STUDIO_JOB_WORKER=off)
```

OpenAPI: http://localhost:8000/docs

Auth is **local-dev only** (`Authorization: Bearer $STUDIO_API_TOKEN`). SSO is not in this phase.

Default adapter is `stub`. It writes fixture receipts and never claims H3 or Qwen ran. Celery is a documented upgrade path, not this process.
