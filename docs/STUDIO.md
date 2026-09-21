# Studio spine (Phase 3)

The pack builder in `app/` is still the four-stage walk. The local studio around it now covers projects, episodes, pack zip revisions, review, comments, sheet/plate/costume/preview media, shot readiness, candidate confirm, a storyboard canvas, a **job center**, **engine adapters**, and a **hop-1 preview desk**.

It is not Jellyfish, not CapCut, and not a generate API. Pack zip remains the collaboration contract. The default factory is `adapter=stub` (fixture receipts). It never claims H3 or Qwen ran.

## Ports (local)

| Process | Directory | Command | URL |
|---|---|---|---|
| Studio API (+ in-process job worker) | `studio/` | `./scripts/dev-studio.sh api` | http://localhost:8000 — OpenAPI at `/docs` |
| Standalone job poller (optional) | `studio/` | `./scripts/dev-studio.sh worker` | no HTTP — use when API has `STUDIO_JOB_WORKER=off` |
| Studio shell | `studio-web/` | `./scripts/dev-studio.sh web` | http://localhost:5174 |
| Pack builder | `app/` | `./scripts/dev-studio.sh app` | http://localhost:5173 |

`scripts/dev-studio.sh all` starts API (with the in-process worker) + both Vite apps.

Do not start `api` and `worker` together unless the API worker is off — both would dequeue the same SQLite rows.

## Auth (honest)

Local-dev only: `Authorization: Bearer $STUDIO_API_TOKEN`.

Default token: `local-dev-token` (`STUDIO_API_TOKEN`). Optional display name: header `X-User-Name` or `STUDIO_DEFAULT_USER` (default `local-dev`).

**SSO is not in this phase.** Do not treat the token as multi-tenant SaaS security. There is a single default organization (`SMF Works (local)`). Postgres-ready `STUDIO_DATABASE_URL` is for *your* later ops deploy, not a pretend tenant switcher.

## Database and files

- Default DB: SQLite at `data/studio.db` (gitignored). Override with `STUDIO_DATABASE_URL` (Postgres URL works if you install `pip install -e "./studio[postgres]"`).
- Media (sheets/plates/costumes/**hop-1 previews**) and stored pack zips: `data/media/` (gitignored). Do not commit likeness stills or engine MP4s. Preview MP4s are allowed **on disk** with `kind=preview` only.

## Operator path (Phase 3)

1. Start API + shell + builder: `./scripts/dev-studio.sh all`
2. Fill Script → Assets → Storyboard → Preview in the builder; export pack zip (every gate green)
3. Create a **project**, then an **episode**, **Import pack zip**
4. Confirm candidates, set shots `ready` (prepared, not generating)
5. **Task Center / episode Jobs:** enqueue `batch-precheck` (gates green + shot ready + plates bound)
6. Enqueue stub `clip-hop1` — the job stores a JSON fixture receipt labeled `adapter=stub`
7. On the **hop-1 preview desk**, attach that receipt (or upload a local preview), fill duration/frames + still-vs-lock, **Mark preview-watched**
8. `generate-ok` and `clip-extend` stay 409 until every required hop-1 has preview-watched + receipt and no NG reason
9. Cancel queued/running jobs; retry failed/cancelled. History lives in Task Center

## Jobs

Types: `still-sheet | still-plate | clip-hop1 | clip-extend | batch-precheck`

Status: `queued | running | succeeded | failed | cancelled`

| Endpoint | Action |
|---|---|
| `GET /api/jobs` | List (`episode_id`, `status`, `job_type` filters) |
| `GET /api/jobs/{id}` | Get |
| `POST /api/jobs` | Enqueue `{ episode_id, shot_id?, job_type, payload? }` |
| `POST /api/jobs/{id}/cancel` | Cancel queued or running |
| `POST /api/jobs/{id}/retry` | Clone a failed/cancelled job |

`clip-hop1` requires `shot_id` and a green batch-precheck (gates + that shot `ready` + plates bound). `clip-extend` additionally requires that shot's hop-1 preview-watched + receipt with no NG.

### Worker (in-process now, Celery later)

Default: the API process runs a daemon **thread** that dequeues `Job` rows (`STUDIO_JOB_WORKER=thread`). Tests use `inline` (run on enqueue) or `off` (leave queued).

```
Job row is the source of truth.
Today: FastAPI lifespan starts JobWorker (thread) → execute_job()
Tomorrow: Celery task calls the same execute_job(); Redis/broker in SMF ops
Do not claim Celery is running. The UI says in-process / stub.
```

Standalone poller for a split deploy:

```bash
STUDIO_JOB_WORKER=off ./scripts/dev-studio.sh api   # HTTP only
./scripts/dev-studio.sh worker                      # poller
```

## Adapters

Interface: still factory (`generate_sheet` / `generate_plate`) and clip factory (`hop1` / `extend`).

| Env | Default | Notes |
|---|---|---|
| `STUDIO_STILL_ADAPTER` | `stub` | `stub` \| `webhook` \| `cli` |
| `STUDIO_CLIP_ADAPTER` | `stub` | same |
| `STUDIO_ADAPTER_WEBHOOK_URL` | empty | If unset while mode is webhook → **stub only** |
| `STUDIO_ADAPTER_CLI` | empty | `{job_id} {job_type} {episode_id} {shot_id}` template; JSON on stdin |
| `STUDIO_ADAPTER_TIMEOUT_SECONDS` | `60` | |

The stub always labels `adapter=stub`, sets `engine: null`, and writes a JSON fixture (H3-measured 10.125 s / 243 f numbers as **documentation of the default window**, not a claim that H3 ran). Live hooks are optional; empty URL/CLI falls back to stub and records `live_hook: unset — stub only`.

## Hop-1 preview desk

Required hop-1 = first edit-list row of each take with `hop1Planned`. Attach preview media (`kind=preview`: json/txt receipt, image, or local mp4/webm). Continuity receipt: duration and/or frames (manual or parsed from JSON / ffprobe), still-vs-lock note, optional NG reason. `PUT .../preview-watched` is refused until media + duration/frames + still-vs-lock exist.

`PUT .../review` `generate-ok` returns **409** `gates_not_green` or `preview_incomplete`.

## API surface

OpenAPI is canonical: http://localhost:8000/docs

Phase 2 surface still applies (projects, episodes, pack zip, gates, review, comments, media, shots, candidates, board). Phase 3 adds:

| Area | Methods |
|---|---|
| Jobs | `GET /api/jobs`, `GET /api/episodes/{id}/jobs`, `POST /api/jobs`, `GET /api/jobs/{id}`, `POST .../cancel`, `POST .../retry` |
| Preview desk | `GET /api/episodes/{id}/preview-desk` |
| Receipts | `GET/PUT /api/episodes/{id}/shots/{id}/receipt`, `PUT .../preview-watched`, `POST .../preview` |

Review states: `draft | needs-art | needs-edit | preview-watched | generate-ok`.

Shot readiness: `draft | candidates | linked | ready`. `ready` is refused while candidates are still `pending` or `accepted` (unlinked). Prepared ≠ generating.

Media kinds: `sheet | plate | costume | preview | other`.

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

API only (includes the in-process worker). The Vite apps stay on the host.

## What this phase is not

- No NLE
- No Celery broker (documented upgrade only)
- No SSO / multi-tenant isolation
- No rewrite of the pack builder
- No engine MP4s in git
- No auto generate-ok from shot `ready`, candidate extract, or a succeeded stub job
