# Studio spine (Phase 4)

The pack builder in `app/` is still the four-stage walk. The local studio around it covers projects, episodes, pack zip revisions, review, comments, sheet/plate/costume/preview media, shot readiness, candidate confirm, a storyboard canvas, a **job center**, **engine adapters**, a **hop-1 preview desk**, a **budget dashboard**, an **audit log**, **retention**, **EDL / shot-playlist export**, and **vertical templates**.

It is not Jellyfish, not CapCut, and not a generate API. Pack zip remains the collaboration contract. The default factory is `adapter=stub` (fixture receipts). It never claims H3 or Qwen ran. Budget units are an **operator rate table** — not a cloud invoice.

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

Local-dev: `Authorization: Bearer $STUDIO_API_TOKEN` (default `local-dev-token`). Display name: `X-User-Name` or `STUDIO_DEFAULT_USER`.

`STUDIO_AUTH_MODE=local|forward-header`. Forward-header trusts `X-Forwarded-User` (reverse-proxy SSO **later**). **OIDC is not implemented.** See [AUTH.md](AUTH.md). Do not treat the token as multi-tenant SaaS security. There is a single default organization (`SMF Works (local)`).

## Database and files

- Default DB: SQLite at `data/studio.db` (gitignored). Override with `STUDIO_DATABASE_URL` (Postgres URL works if you install `pip install -e "./studio[postgres]"`).
- Media (sheets/plates/costumes/**hop-1 previews**) and stored pack zips: `data/media/` (gitignored). Do not commit likeness stills or engine MP4s. Preview MP4s are allowed **on disk** with `kind=preview` only.

## Operator path (Phase 4)

1. Start API + shell + builder: `./scripts/dev-studio.sh all`
2. **New from template** (Education lesson / Brand promo / Short drama ep) **or** create a blank project
3. Set **adapter defaults** (stub unless a live hook exists) and an optional **budget cap** + hard stop
4. Fill Script → Assets → Storyboard → Preview in the builder; export pack zip (every gate green) and import — or fill the seeded template pack
5. Confirm candidates, set shots `ready` (prepared, not generating)
6. Enqueue stub jobs (batch-precheck → hop-1). Job rows store estimated/actual **cost units** from the operator rate table
7. Open **Budget**: spend by episode/project, job counts, adapter mix
8. **Audit** filter by project/episode (review, enqueue/cancel, pack import/export, media upload)
9. Hop-1 preview desk → preview-watched → `generate-ok` still needs green gates + receipts
10. **Export EDL** / **Export shot playlist** (metadata only; media paths when preview receipts exist)
11. Retention dry-run / apply expires stub outputs / temp media after N days — **pack revisions are kept**

## Adapters

Registry: `stub` (default, not live) plus documented slots `comfy-h3` (clip), `comfy-qwen` (still), `webhook`, `cli`. Per-project still/clip default. Unset live hooks **always** resolve to stub.

| Env | Default | Notes |
|---|---|---|
| `STUDIO_STILL_ADAPTER` | `stub` | `stub` \| `comfy-qwen` \| `webhook` \| `cli` |
| `STUDIO_CLIP_ADAPTER` | `stub` | `stub` \| `comfy-h3` \| `webhook` \| `cli` |
| `STUDIO_ADAPTER_WEBHOOK_URL` | empty | Transport for live slots. Unset → stub only |
| `STUDIO_ADAPTER_CLI` | empty | `{job_id} {job_type} {episode_id} {shot_id}` template; JSON on stdin |
| `STUDIO_ADAPTER_TIMEOUT_SECONDS` | `60` | |

`GET /api/adapters` lists slots. Stub always labels `adapter=stub`, `engine: null`.

## Budget

Job rows store `estimated_cost_units` at enqueue and `actual_cost_units` on success (0 on fail/cancel). Units come from `STUDIO_COST_RATES` (default `stub:0.1,webhook:1,cli:1,comfy-h3:2,comfy-qwen:0.5`). `STUDIO_COST_CURRENCY` defaults to `credits`. Optional `STUDIO_COST_USD_PER_UNIT` is an estimate only.

`STUDIO_BUDGET_CAP_UNITS` + `STUDIO_BUDGET_HARD_STOP` are env defaults; each project can override. Hard stop returns **409** `budget_cap` when spent + pending + new estimate would exceed the cap.

This never claims a cloud bill was paid.

## Audit + retention

Audit table: `review.set`, `job.enqueue`, `job.cancel`, `pack.import`, `pack.export`, `media.upload`, `project.create`, `retention.apply`. `GET /api/audit?project_id=&episode_id=&action=`.

Retention: `STUDIO_RETENTION_DAYS` (default 30; `0` disables). Project override allowed. `GET /api/retention` (dry-run) and `POST /api/retention` with `{ "dry_run": false, "confirm": "expire" }` deletes **ephemeral** stub job outputs / temp media older than N days. **Pack revisions are not deleted.**

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

Phase 2–3 surface still applies. Phase 4 adds:

| Area | Methods |
|---|---|
| Adapters | `GET /api/adapters` |
| Budget | `GET /api/budget`, `GET /api/projects/{id}/budget`, `GET /api/episodes/{id}/budget` |
| Audit | `GET /api/audit` |
| Retention | `GET /api/retention`, `POST /api/retention`, `GET /api/retention/dry-run` |
| Export | `GET /api/episodes/{id}/export/edl`, `.../fcpxml`, `.../playlist` |
| Templates | `GET /api/templates`, `POST /api/templates/{id}/projects` |
| Project settings | `PATCH /api/projects/{id}` still/clip adapter, budget cap, hard stop, retention days |

## Tests

```bash
cd studio && python3 -m pip install -e ".[dev]"
python3 -m pytest

cd app && npm test
```

## Docker (optional)

```bash
docker compose up studio-api
```

API only (includes the in-process worker). The Vite apps stay on the host.

## What this phase is not

- No full NLE timeline editor (EDL/playlist assemble metadata only)
- No Celery broker (documented upgrade only)
- No OIDC / full SSO (forward-header hook + [AUTH.md](AUTH.md) only)
- No rewrite of the pack builder
- No engine MP4s in git
- No auto generate-ok from shot `ready`, candidate extract, a succeeded stub job, or a vertical template
- No claim that budget units are a paid cloud invoice
