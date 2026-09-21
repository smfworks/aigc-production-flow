# AIGC studio API (Phase 9)

FastAPI spine for projects, ordered episodes, pack zip revisions, pack revision diff, review states, reviewer/producer sign-off, comments, visual identity store (approve / unapprove / keyword edit), media, shots, jobs, adapters, hop-1 preview desk, playlist scrubber, budget, audit, retention, EDL export, vertical templates, org members (`writer` / `art` plus the Phase 5 roles), presence, media store adapters, multi-org lite, notifications, continuity, demo seed, backup, and builder pack handoff. Optional Celery worker. Optional OIDC JWKS.

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
