# Studio spine (Phase 5)

The pack builder in `app/` is still the four-stage walk. The local studio around it covers projects, episodes, pack zip revisions, review, comments, sheet/plate/costume/preview media, shot readiness, candidate confirm, a storyboard canvas, a **job center**, **engine adapters**, a **hop-1 preview desk**, a **budget dashboard**, an **audit log**, **retention**, **EDL / shot-playlist export**, **vertical templates**, **app-level RBAC**, **presence**, **shot comments**, **media store adapters**, and **adapter health**.

It is not Jellyfish, not CapCut, and not a generate API. Pack zip remains the collaboration contract. The default factory is `adapter=stub` (fixture receipts). It never claims H3 or Qwen ran. Budget units are an **operator rate table** — not a cloud invoice. Media defaults to **local disk**. S3/MinIO is opt-in and never claimed live when unset. **OIDC is not implemented.** Celery is not this process.

## Ports (local)

| Process | Directory | Command | URL |
|---|---|---|---|
| Studio API (+ in-process job worker) | `studio/` | `./scripts/dev-studio.sh api` | http://localhost:8000 — OpenAPI at `/docs` |
| Standalone job poller (optional) | `studio/` | `./scripts/dev-studio.sh worker` | no HTTP — use when API has `STUDIO_JOB_WORKER=off` |
| Studio shell | `studio-web/` | `./scripts/dev-studio.sh web` | http://localhost:5174 |
| Pack builder | `app/` | `./scripts/dev-studio.sh app` | http://localhost:5173 |

`scripts/dev-studio.sh all` starts API (with the in-process worker) + both Vite apps.

Do not start `api` and `worker` together unless the API worker is off — both would dequeue the same SQLite rows.

## Auth + RBAC lite (honest)

Local-dev: `Authorization: Bearer $STUDIO_API_TOKEN` (default `local-dev-token`). Display name: `X-User-Name` or `STUDIO_DEFAULT_USER`.

`STUDIO_AUTH_MODE` is `local` (default) or `forward-header` (trust `X-Forwarded-User`; reverse-proxy SSO **later**). **OIDC is not implemented.** See [AUTH.md](AUTH.md).

Roles are **app-level** on the default org, not an IdP claim:

| Role | Mutating |
|---|---|
| `producer` | All writes, including members, budget hard-stop / cap, retention apply |
| `editor` | Review, jobs, pack import, media, shots, comments |
| `reviewer` | Comments + review set |
| `viewer` | Read-only (presence heartbeat still allowed) |

Seed: default org + `STUDIO_DEFAULT_USER` as **producer**. A producer adds members by local user name. Switch the studio chrome “Local user” field to that `X-User-Name` to act as them.

Do not treat the token as multi-tenant SaaS security. There is a single default organization (`SMF Works (local)`).

## Database and files

- Default DB: SQLite at `data/studio.db` (gitignored). Override with `STUDIO_DATABASE_URL` (Postgres URL works if you install `pip install -e "./studio[postgres]"`).
- Media (sheets/plates/costumes/**hop-1 previews**) and stored pack zips: `data/media/` (gitignored) via the **local** media adapter. Do not commit likeness stills or engine MP4s. Preview MP4s are allowed **on disk** with `kind=preview` only.
- Optional S3/MinIO: `STUDIO_MEDIA_BACKEND=s3` plus `STUDIO_S3_BUCKET` (and `STUDIO_S3_ENDPOINT` for MinIO). Incomplete config **stays local** and `/api/meta` says so. Credentials stay in the process environment, not git. Install `pip install -e "./studio[s3]"` for boto3.

## Operator path (Phase 5)

1. Start API + shell + builder: `./scripts/dev-studio.sh all` **or** `docker compose -f docker-compose.studio.yml up --build`
2. Confirm chrome shows your role (`producer` for the seeded local user)
3. **Members**: add a colleague as `viewer` → they cannot enqueue → promote to `editor` → they can comment on a shot
4. Open an episode: presence chips (heartbeat TTL ~60s)
5. **New from template** or create a blank project; set adapter defaults (stub unless a live hook exists)
6. Fill Script → Assets → Storyboard → Preview in the builder; export pack zip and import
7. Confirm candidates, set shots `ready` (prepared, not generating)
8. Adapter status strip: stub is always healthy. Unset live hooks stay stub. Configured-but-down live slots **409** on enqueue
9. Enqueue stub jobs (batch-precheck → hop-1). Job rows store estimated/actual **cost units**
10. Hop-1 preview desk → shot comments → preview-watched → `generate-ok` still needs green gates + receipts
11. **Export EDL** / **Export shot playlist**. Retention dry-run / apply (producer) expires stub outputs — **pack revisions are kept**

## Compose deploy pack

```bash
docker compose -f docker-compose.studio.yml up --build
```

| Service | Port | Notes |
|---|---|---|
| `studio-api` | 8000 | FastAPI + in-process **thread** worker. SQLite volume `studio-data:/data` |
| `studio-web` | 5174 | nginx SPA; `/api` and `/health` proxy to the API |

Optional profiles (not production SSO, not Celery):

| Profile | What |
|---|---|
| `worker` | Standalone poller (`python -m app.jobs`). Set `STUDIO_JOB_WORKER=off` on the API so only one process dequeues |
| `postgres` | Postgres 16. Point `STUDIO_DATABASE_URL` at it **and** install the API `postgres` extra |
| `minio` | Local object store on 9000/9001. Set root user/password in the **shell**. Then `STUDIO_MEDIA_BACKEND=s3`, `STUDIO_S3_ENDPOINT=http://127.0.0.1:9000`, `STUDIO_S3_BUCKET=…`. Unset → local disk stays honest |

No secrets belong in the repo. The API token default is local-dev only. This compose file does **not** claim OIDC, TLS, or a paid cloud bill.

The older `docker-compose.yml` is still API-only.

## Adapters + health

Registry: `stub` (default, not live) plus documented slots `comfy-h3` (clip), `comfy-qwen` (still), `webhook`, `cli`. Per-project still/clip default. Unset live hooks **always** resolve to stub.

| Env | Default | Notes |
|---|---|---|
| `STUDIO_STILL_ADAPTER` | `stub` | `stub` \| `comfy-qwen` \| `webhook` \| `cli` |
| `STUDIO_CLIP_ADAPTER` | `stub` | `stub` \| `comfy-h3` \| `webhook` \| `cli` |
| `STUDIO_ADAPTER_WEBHOOK_URL` | empty | Transport for live slots. Unset → stub only |
| `STUDIO_ADAPTER_CLI` | empty | `{job_id} {job_type} {episode_id} {shot_id}` template; JSON on stdin |
| `STUDIO_ADAPTER_TIMEOUT_SECONDS` | `60` | |

`GET /api/adapters` lists slots + health. `GET /api/adapters/{id}/health` and `POST /api/adapters/{id}/dry-run` ask: config present? reachable? They do **not** enqueue a generate. Stub is always ok. A configured live slot that is down **blocks enqueue** (409 `adapter_unhealthy`). Unset hooks still fall back to stub.

## Presence + comments

`POST /api/episodes/{id}/presence` heartbeat; `GET` who’s on the episode (TTL `STUDIO_PRESENCE_TTL_SECONDS`, default 60). Optional `GET …/presence/stream` SSE.

Comments: episode thread plus `shot_id` / `board_node_id`. `POST /api/comments/{id}/resolve`. Audit: `comment.create`, `comment.resolve`.

## Budget

Job rows store `estimated_cost_units` at enqueue and `actual_cost_units` on success (0 on fail/cancel). Units come from `STUDIO_COST_RATES` (default `stub:0.1,webhook:1,cli:1,comfy-h3:2,comfy-qwen:0.5`). `STUDIO_COST_CURRENCY` defaults to `credits`. Optional `STUDIO_COST_USD_PER_UNIT` is an estimate only.

`STUDIO_BUDGET_CAP_UNITS` + `STUDIO_BUDGET_HARD_STOP` are env defaults; each project can override (**producer** only). Hard stop returns **409** `budget_cap` when spent + pending + new estimate would exceed the cap.

This never claims a cloud bill was paid.

## Audit + retention

Audit table: `review.set`, `job.enqueue`, `job.cancel`, `pack.import`, `pack.export`, `media.upload`, `project.create`, `retention.apply`, `comment.create`, `comment.resolve`, `member.add`, `member.role`. `GET /api/audit?project_id=&episode_id=&action=`.

Retention: `STUDIO_RETENTION_DAYS` (default 30; `0` disables). Project override allowed (producer). `GET /api/retention` (dry-run) and `POST /api/retention` with `{ "dry_run": false, "confirm": "expire" }` deletes **ephemeral** stub job outputs / temp media older than N days. **Pack revisions are not deleted.**

## Light timeline export

From the edit list + continue chains (not an NLE):

| Endpoint | File |
|---|---|
| `GET /api/episodes/{id}/export/edl` | CMX3600-ish EDL |
| `GET /api/episodes/{id}/export/fcpxml` | FCP XML lite |
| `GET /api/episodes/{id}/export/playlist` | Shot playlist JSON (Resolve/CapCut import) |

Media paths appear when a hop-1 preview receipt is attached.

## Vertical templates

Empty structured packs under `templates/verticals/` (`education-lesson`, `brand-promo`, `short-drama-ep`). Studio **New from template** creates a project + Ep 1 + pack revision. Gates stay red. No fake generate.

`GET /api/templates` · `POST /api/templates/{id}/projects`

## Jobs (Phase 3, unchanged contract)

Types: `still-sheet | still-plate | clip-hop1 | clip-extend | batch-precheck`

Default worker: in-process **thread** (`STUDIO_JOB_WORKER=thread`). Celery is the documented upgrade path, not this process. Tests use `inline` or `off`.

## Hop-1 preview desk

Required hop-1 = first edit-list row of each take with `hop1Planned`. `generate-ok` and `clip-extend` stay 409 until every required hop-1 has preview-watched + receipt and no NG reason.

## API surface

OpenAPI is canonical: http://localhost:8000/docs

Phase 2–4 surface still applies. Phase 5 adds:

| Area | Methods |
|---|---|
| Me / roles | `GET /api/me` includes `role`, `org_id`, `permissions` |
| Members | `GET/POST /api/orgs/{id}/members`, `PATCH /api/orgs/{id}/members/{member_id}` |
| Presence | `GET/POST /api/episodes/{id}/presence`, `GET …/presence/stream` |
| Comments | `POST` may include `shot_id` / `board_node_id`; `POST /api/comments/{id}/resolve` |
| Adapters | `GET /api/adapters/health`, `GET/POST /api/adapters/{id}/health|dry-run` |
| Meta | `media_backend`, `media_note`, `presence_ttl_seconds` |

## Tests

```bash
cd studio && python3 -m pip install -e ".[dev]"
python3 -m pytest

cd app && npm test
```

## What this phase is not

- No full NLE timeline editor (EDL/playlist assemble metadata only)
- No Celery broker (documented upgrade only)
- No OIDC / full SSO (forward-header hook + app-level roles + [AUTH.md](AUTH.md) only)
- No rewrite of the pack builder
- No engine MP4s in git
- No auto generate-ok from shot `ready`, candidate extract, a succeeded stub job, or a vertical template
- No claim that budget units are a paid cloud invoice
- No claim that S3/MinIO is live when `STUDIO_MEDIA_BACKEND` is unset or the bucket is empty
