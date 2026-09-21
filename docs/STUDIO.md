# Studio spine (Phase 2)

The pack builder in `app/` is still the four-stage walk. This spine adds a **local studio** around it: projects, episodes (chapters), pack zip revisions, a review state machine, comments, a sheet/plate/costume media store, **shot readiness**, **candidate confirm**, and a **storyboard canvas**.

It is not Jellyfish, not CapCut, and not a generate API. Pack zip remains the collaboration contract. Async generate jobs are **Phase 3**.

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
- Media (sheets/plates/costumes) and stored pack zips: `data/media/` (gitignored). Do not commit likeness stills or engine MP4s.

## Operator path (Phase 2)

1. Start the API: `./scripts/dev-studio.sh api`
2. Start the studio shell: `./scripts/dev-studio.sh web`
3. Start the pack builder: `./scripts/dev-studio.sh app`
4. In the builder (http://localhost:5173), fill Script → Assets → Storyboard → Preview
5. On **Assets → Schedule**, pin who/what persists on which takes/windows. Identity hold at `cut` / `fadeblack` needs a plate still whose **entity** is that name (or `none` + why)
6. Keep lock paragraphs on the same keywords every hop. `brown` vs `brunette` is a red **lock-diff** gate
7. Storyboard **List** is precision; **Canvas** shows continue chains vs cut/fadeblack boundaries
8. Export pack zip (blocked until **every** gate is green, including `entity-schedule` and `lock-diff`)
9. In the shell (http://localhost:5174), create a **project**, then an **episode**, **Import pack zip**
10. Per-episode **shot list** (edit-list rows) with readiness chips: `draft → candidates → linked → ready`. `ready` = prepared, **not** generating
11. **Extract candidates (stub)** or add by hand. Accept / ignore / link existing character|prop|scene|costume assets. Human in the loop — this never stamps `generate-ok`
12. Deep-link **Open in pack builder** (`?step=edit&row=N`) to fix a window
13. Set review state. **`generate-ok` is refused unless the snapshot is all green** — including the new consistency gates
14. **Export pack zip** — latest revision, byte-for-byte the imported zip

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
| Media | `GET/POST /api/episodes/{id}/media`, `GET/DELETE /api/media/{id}` — kinds `sheet`, `plate`, `costume`, `other`; optional `entity_type` `character` / `prop` / `scene` / `costume` |
| Shots | `GET /api/episodes/{id}/shots`, `GET /api/episodes/{id}/board` |
| Candidates | `POST /api/episodes/{id}/shots/extract-candidates`, `POST .../shots/{id}/candidates`, `PATCH .../candidates/{id}` |
| Readiness | `PUT /api/episodes/{id}/shots/{id}/readiness` body `{ "readiness" }` |

Review states: `draft | needs-art | needs-edit | preview-watched | generate-ok`.

Shot readiness: `draft | candidates | linked | ready`. `ready` is refused while candidates are still `pending` or `accepted` (unlinked). Prepared ≠ generating.

`PUT .../review` with `generate-ok` returns **409** when there is no pack or any gate is red. Candidate extract never changes review state.

## Tests

```bash
# studio API
cd studio && python3 -m pip install -e ".[dev]"
python3 -m pytest

# pack builder (must still pass)
cd app && npm test
```

## Docker (optional)

```bash
docker compose up studio-api
```

API only. The Vite apps stay on the host.

## What this phase is not

- No NLE
- No Celery / generate queue (Phase 3)
- No SSO / multi-tenant isolation
- No rewrite of the pack builder
- No engine MP4s in git
- No auto generate-ok from shot `ready` or candidate extract
