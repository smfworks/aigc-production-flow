# Studio spine (Phase 1)

The pack builder in `app/` is still the nine-gate walk. This spine adds a **local studio** around it: projects, episodes (chapters), pack zip revisions, a review state machine, comments, and a sheet/plate media store.

It is not Jellyfish, not CapCut, and not a generate API. Pack zip remains the collaboration contract. Async generate jobs are **deferred**.

## Ports (local)

| Process | Directory | Command | URL |
|---|---|---|---|
| Studio API | `studio/` | `./scripts/dev-studio.sh api` | http://localhost:8000 — OpenAPI at `/docs` |
| Studio shell | `studio-web/` | `./scripts/dev-studio.sh web` | http://localhost:5174 |
| Pack builder | `app/` | `./scripts/dev-studio.sh app` | http://localhost:5173 |

`scripts/dev-studio.sh all` starts API + both Vite apps.

## Auth (honest)

Local-dev only: `Authorization: Bearer $STUDIO_API_TOKEN`.

Default token: `local-dev-token` (`STUDIO_API_TOKEN`). Optional display name: header `X-User-Name` or `STUDIO_DEFAULT_USER` (default `local-dev`).

**SSO is not in this phase.** Do not treat the token as multi-tenant SaaS security. There is a single default organization (`SMF Works (local)`). Postgres-ready `STUDIO_DATABASE_URL` is for *your* later ops deploy, not a pretend tenant switcher.

## Database and files

- Default DB: SQLite at `data/studio.db` (gitignored). Override with `STUDIO_DATABASE_URL` (Postgres URL works if you install `pip install -e "./studio[postgres]"`).
- Media (sheets/plates) and stored pack zips: `data/media/` (gitignored). Do not commit likeness stills or engine MP4s.

## Operator path (done when this works)

1. Start the API: `./scripts/dev-studio.sh api`
2. Start the studio shell: `./scripts/dev-studio.sh web`
3. Start the pack builder if you need to fill gates: `./scripts/dev-studio.sh app`
4. In the shell (http://localhost:5174), create a **project**, then an **episode**
5. In the builder, export a pack zip (must contain `pack.json`)
6. On the episode, **Import pack zip** — this creates a `PackRevision` (pack.json + nine-gate snapshot)
7. Set review state (`draft` / `needs-art` / `needs-edit` / `preview-watched`). **`generate-ok` is refused unless the snapshot is nine green.**
8. Upload a plate image to the media library
9. **Export pack zip** — latest revision, byte-for-byte the imported zip

## API surface

OpenAPI is canonical: http://localhost:8000/docs

| Area | Methods |
|---|---|
| Projects | `GET/POST /api/projects`, `GET/PATCH/DELETE /api/projects/{id}` |
| Episodes | `GET/POST /api/projects/{id}/episodes`, `GET/PATCH/DELETE /api/episodes/{id}` |
| Pack zip | `POST /api/episodes/{id}/pack` (import), `GET /api/episodes/{id}/pack` (export latest) |
| Gates | `GET /api/episodes/{id}/gates` |
| Review | `GET/PUT /api/episodes/{id}/review` body `{ "state", "note" }` |
| Comments | `GET/POST /api/episodes/{id}/comments` |
| Media | `GET/POST /api/episodes/{id}/media`, `GET/DELETE /api/media/{id}` |

Review states: `draft | needs-art | needs-edit | preview-watched | generate-ok`.

`PUT .../review` with `generate-ok` returns **409** when there is no pack or any of the nine gates is red. The builder in `app/` is still the operator UI for filling gates; the API re-evaluates the same nine README gates so the stamp cannot lie.

## Tests

```bash
# studio API
cd studio && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest

# pack builder (must still pass)
cd app && npm test
```

## Docker (optional)

```bash
docker compose up studio-api
```

API only. The Vite apps stay on the host for Phase 1.

## What this phase is not

- No NLE
- No Celery / generate queue
- No SSO / multi-tenant isolation
- No rewrite of the nine-gate builder
- No engine MP4s in git
