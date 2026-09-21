# AIGC studio API (Phase 10)

FastAPI spine. Create a pack without a zip (`POST /api/studio/start`: blank, template, or brain dump). Edit it with `POST /api/episodes/{id}/pack/json`. Export an agent zip (`GET /api/episodes/{id}/export/agent`) that lists still jobs before hop-1 clips and does not call Comfy. Brain dump uses a deterministic template unless `STUDIO_LLM_BASE_URL` is set.

Also: ordered episodes, pack revision diff, review sign-off, identity store, media, shots, jobs, adapters, hop-1 preview desk, playlist scrubber, budget, audit, retention, EDL, vertical templates, org members, presence, multi-org lite, notifications, continuity, demo seed, backup, and optional builder handoff. Optional Celery. Optional OIDC.

Operator docs: [../docs/STUDIO.md](../docs/STUDIO.md). Auth: [../docs/AUTH.md](../docs/AUTH.md).

```bash
# from repo root
./scripts/dev-studio.sh api      # HTTP + in-process job worker (default)
./scripts/dev-studio.sh worker   # optional standalone thread poller (API should set STUDIO_JOB_WORKER=off)
./scripts/dev-studio.sh celery   # optional Celery worker (STUDIO_CELERY_BROKER_URL + STUDIO_JOB_WORKER=celery on the API)
docker compose -f docker-compose.studio.yml up --build
```

OpenAPI: http://localhost:8000/docs

Auth is **local-dev** (`Authorization: Bearer $STUDIO_API_TOKEN`) plus optional `STUDIO_AUTH_MODE=forward-header` or `oidc`, and **app-level** org roles. Multi-org lite is membership isolation (`X-Org-Id`), not SaaS billing. OIDC is opt-in and off by default. This is not a production IdP.

Default adapter is `stub`. It writes fixture receipts and never claims H3 or Qwen ran. Budget units are an operator rate table, not a cloud invoice. Media is local disk unless S3/MinIO is configured. Default job worker is `thread`. Celery is opt-in.
