# AIGC studio API (Phase 5)

FastAPI spine for projects, episodes, pack zip revisions, review states, comments, media, shots, jobs, adapters, hop-1 preview desk, budget, audit, retention, EDL export, vertical templates, org members, presence, and media store adapters.

Operator docs: [../docs/STUDIO.md](../docs/STUDIO.md). Auth: [../docs/AUTH.md](../docs/AUTH.md).

```bash
# from repo root
./scripts/dev-studio.sh api      # HTTP + in-process job worker
./scripts/dev-studio.sh worker   # optional standalone poller (API should set STUDIO_JOB_WORKER=off)
docker compose -f docker-compose.studio.yml up --build
```

OpenAPI: http://localhost:8000/docs

Auth is **local-dev** (`Authorization: Bearer $STUDIO_API_TOKEN`) plus optional `STUDIO_AUTH_MODE=forward-header` and **app-level** org roles. OIDC is not implemented.

Default adapter is `stub`. It writes fixture receipts and never claims H3 or Qwen ran. Budget units are an operator rate table, not a cloud invoice. Media is local disk unless S3/MinIO is configured. Celery is a documented upgrade path, not this process.
