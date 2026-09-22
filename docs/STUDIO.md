# Studio spine (Phase 13)

**Start here:** open Studio. The home screen asks what you want to make. Finish the wizard. **Send to Hermes** writes a brief. Download agent zip is the fallback.

The wizard fills a draft pack: format, length, tone, deliverable scope, cast, audio, engines, a prunable task tree, then director checkpoints. Cast notes become identity **drafts**, not approvals. Gates stay red. No model is claimed. Unset Comfy lanes stay stub, and the handoff says so.

The task tree follows script/beats → identity sheets → plates → hop-1 → stitch → review gates. Disable or delete a branch you will not use. That skip is written into the brief. The tree does not call Comfy or start Hermes. Writer, Art, Picture, and Sound are routing labels on the crew brief, not four agents that ran. Checkpoints list the real gates (log line through lock-diff) plus draft identities, missing plates, unwatched hop-1, and missing sign-off. Must-nots, platform formats, and claim bans are optional and land in pack notes and `agent-brief.json`. **Save recipe** writes local JSON (`skill_<name>_v0.1.json` under `data/recipes/` or `STUDIO_RECIPE_ROOT`). Load recipe prefills Create. There is no plaza.

**Send to Hermes** does not invoke Hermes and does not call Comfy. It writes `data/handoff/<run-id>/` (or `STUDIO_HANDOFF_ROOT`) plus `latest.json`, and returns a `hermes://aigc/brief?run=` link and a copyable payload. The brief orders **sheets → plates → hop-1 clips → stitch**. The agent-run panel polls those jobs. Stub lanes return fixture receipts. Stitch writes an MP4 only when local ffmpeg can concat real video files; otherwise the run stays **awaiting stitch**. See [AGENTS.md](../AGENTS.md).

Projects, Task Center, Budget, and Audit stay on the desk. **New blank pack**, **New from template**, and **brain dump** remain on the Projects page. The four stages (Script → Assets → Storyboard → Preview) still edit inside the episode. **Export for agent** downloads the same zip. Pack zip remains the collaboration contract. It is not CapCut and not a generate API that invents MP4s.

The Hermes plugin `smf-h3-capture` can stay. It is not required to create a pack. Import zip and Open in Studio remain secondary paths.

The pack builder in `app/` is still a four-stage walk and the zip round-trip. The local studio around it covers projects, episodes (season/sequence order), pack zip revisions, **in-studio stage editing**, **brain-dump drafts**, **agent export**, **pack revision diff**, review, **reviewer/producer sign-off**, comments, **visual identity store** (approved sheets + per-window plates, unapprove, keyword edit), sheet/plate/costume/preview media, shot readiness, candidate confirm, a storyboard canvas, a **job center**, **engine adapters**, a **hop-1 preview desk**, a **soft playlist scrubber**, a **budget dashboard**, an **audit log**, **retention**, **EDL / shot-playlist export**, **vertical templates**, **app-level RBAC** (writer / art plus the Phase 5 roles), **presence**, **shot comments**, **media store adapters**, **adapter health**, optional **Celery**, optional **OIDC**, **multi-org lite**, **in-app notifications**, **ops probes**, a **continuity panel**, **demo seed**, **backup/restore**, and **builder Open in Studio auto-import**.

Brain dump is stub/local only. `STUDIO_LLM_BASE_URL` may point at a local or OpenAI-compatible chat endpoint. When it is unset, Studio expands the dump with a deterministic template and says **no model configured**. It does not invent that an LLM ran. Look starts blank on a new pack. Destructive resets use an in-app confirm (`confirm=reset`); earlier revisions are kept. Export for agent does **not** call Comfy. Adapter labels say stub or live. Unset hooks stay stub.

| Env | Default | Notes |
|---|---|---|
| `STUDIO_HANDOFF_ROOT` | beside the media dir (`./data/handoff`) | Hermes brief drop. `latest.json` is the pane watch file |
| `STUDIO_HERMES_DROP` | empty | Optional second copy, for example `~/.hermes/aigc`. Unset does not write outside the handoff root |
| `STUDIO_RECIPE_ROOT` | beside the media dir (`./data/recipes`) | Local Create recipes. Not a marketplace |
| `STUDIO_LLM_BASE_URL` | empty | Optional `…/v1` or full `…/chat/completions` URL. Unset → deterministic brain dump |
| `STUDIO_LLM_MODEL` | `local` when a URL is set | Model name sent to that endpoint |
| `STUDIO_LLM_API_KEY` | empty | Optional bearer for that endpoint. Stays in the process environment, not git |

It is not Jellyfish, not CapCut, and not a generate API. Pack zip remains the collaboration contract. The default factory is `adapter=stub` (fixture receipts). It never claims H3 or Qwen ran. Budget units are an **operator rate table** — not a cloud invoice. Media defaults to **local disk**. S3/MinIO is opt-in and never claimed live when unset. **OIDC is opt-in and off by default.** Celery is opt-in and off by default (`STUDIO_JOB_WORKER=thread`). **Multi-org lite is membership isolation, not SaaS billing, and not SSO org mapping.**

## Ports (local)

| Process | Directory | Command | URL |
|---|---|---|---|
| Studio API (+ in-process job worker) | `studio/` | `./scripts/dev-studio.sh api` | http://localhost:8000 — OpenAPI at `/docs` |
| Standalone job poller (optional) | `studio/` | `./scripts/dev-studio.sh worker` | no HTTP — use when API has `STUDIO_JOB_WORKER=off` |
| Celery worker (optional) | `studio/` | `./scripts/dev-studio.sh celery` | Redis broker from `STUDIO_CELERY_BROKER_URL`. API must use `STUDIO_JOB_WORKER=celery` |
| Studio shell | `studio-web/` | `./scripts/dev-studio.sh web` | http://localhost:5174 |
| Pack builder | `app/` | `./scripts/dev-studio.sh app` | http://localhost:5173 |

`scripts/dev-studio.sh all` starts API (with the in-process worker) + both Vite apps.

Do not start `api` (thread worker) and `worker` together unless the API worker is off — both would dequeue the same SQLite rows. **Never run the thread worker and a Celery worker against the same SQLite file.** Prefer the `postgres` compose profile when Celery is enabled.

## Auth + RBAC lite (honest)

Local-dev: `Authorization: Bearer $STUDIO_API_TOKEN` (default `local-dev-token`). Display name: `X-User-Name` or `STUDIO_DEFAULT_USER`.

`STUDIO_AUTH_MODE` is `local` (default), `forward-header` (trust `X-Forwarded-User`), or `oidc` (Bearer JWT via issuer JWKS). **OIDC is opt-in and off by default.** This repo does not ship a production IdP. See [AUTH.md](AUTH.md).

Roles are **app-level** on the active org, not an IdP claim (unless `STUDIO_OIDC_APPLY_ROLE_CLAIM` is set):

| Role | Mutating |
|---|---|
| `producer` | All writes, including members, budget hard-stop / cap, retention apply, **sign-off**, producer override of generate-ok |
| `editor` | Legacy craft bundle: script, identity, edit-list, review, jobs, pack import, media, shots, comments. Not budget, retention, members, or sign-off |
| `writer` | Script, map, dialogue, episode season/sequence order, comments |
| `art` | Sheets, plates, costumes, identity approve / unapprove / keyword edit, comments |
| `reviewer` | Comments + review set + **sign-off** |
| `viewer` | Read-only (presence heartbeat still allowed) |

Seed: default org + `STUDIO_DEFAULT_USER` as **producer**. A producer adds members by local user name. Switch the studio chrome “Local user” field to that `X-User-Name` to act as them.

Do not treat the token as multi-tenant SaaS security. **Multi-org lite** lets a producer create additional organizations, list orgs they belong to, and switch the active org (`X-Org-Id`). Members and projects are scoped to the active org. Cross-org IDs 404. There is still no billing, no SSO org mapping, and no SaaS tenancy. The seed keeps `SMF Works (local)` as the default org for existing single-org databases.

## Database and files

- Default DB: SQLite at `data/studio.db` (gitignored). Override with `STUDIO_DATABASE_URL` (Postgres URL works if you install `pip install -e "./studio[postgres]"`).
- Media (sheets/plates/costumes/**hop-1 previews**) and stored pack zips: `data/media/` (gitignored) via the **local** media adapter. Do not commit likeness stills or engine MP4s. Preview MP4s are allowed **on disk** with `kind=preview` only.
- Optional S3/MinIO: `STUDIO_MEDIA_BACKEND=s3` plus `STUDIO_S3_BUCKET` (and `STUDIO_S3_ENDPOINT` for MinIO). Incomplete config **stays local** and `/api/meta` says so. Credentials stay in the process environment, not git. Install `pip install -e "./studio[s3]"` for boto3.

## Operator path (Phase 10)

1. Open Studio (`http://localhost:5174`). Chrome **New project** works from Projects, Task Center, Budget, and Audit
2. **Start here**: blank pack, vertical template, or paste a brain dump. You land on the episode. No zip
3. Edit Script → Assets → Storyboard → Preview in the episode. Autosave writes a pack revision. Gates stay red until filled. A new pack’s Look line is blank
4. **Export for agent**. The zip contains `pack.zip`, `pack.json`, `gate-snapshot.json`, `agent-brief.json`, and `README.md`. Jobs are still sheets, then still plates, then hop-1 clips, with measured window metadata (10.125 s / 243 f @ 24 fps, canvas 1344×768). `honesty.called_comfy` is false
5. Import zip / Open in Studio remain available under **Optional zip**

## Operator path (Phase 9)

The Phase 8 path still applies. Phase 9 adds:

1. **Members matrix** — add `writer` and `art` as different roles. A writer can save log line / map / dialogue and reorder episodes. An art member can approve a sheet. Neither can enqueue. The legacy `editor` still can
2. **Episode order** — on the project, move episodes up/down. `season` + `sequence` are what backup restores. Retention expires stub media only and does not reorder episodes
3. **Playlist scrubber** — on the episode, scrub the shot list. A stored `kind=preview` file plays (video or still). A JSON stub receipt shows metadata and does not pretend to be an MP4. Empty shots say so. This is not an NLE
4. **Identity** — after approve, **Unapprove** (audited) or edit keywords. **Save draft keywords** drops an approved asset back to draft. **Re-approve** is what makes the new keywords count
5. **Pack diff** — two entity-schedule rows that share kind/name/take/windows stay two rows (matched by id). The panel says when that group was ambiguous

## Operator path (Phase 8)

1. Start API + shell + builder: `./scripts/dev-studio.sh all` **or** `docker compose -f docker-compose.studio.yml up --build`
2. Confirm chrome shows your role (`producer` for the seeded local user) on the default org
3. **Create org** → switch the active org in chrome → add a member on org A who cannot see org B
4. Empty org: **Seed demo episode** (short-drama-ep template + JSON fixture metadata — no likeness, no MP4)
5. **Members**: add a colleague as `viewer` → they cannot enqueue → promote to `editor` → they can comment on a shot
6. Open an episode: presence chips, **Continuity** panel (entity-schedule + lock-diff, red gates, deep-link to the shot board **and identity store** — not an NLE)
7. **Identity store**: upload a sheet/plate (fixture JSON is fine in public trees — no likeness stills) → **Approve** (who/when). Link a plate to a shot/window. Draft assets do **not** count for lock-diff / I2VA generate readiness
8. Fill Script → Assets → Storyboard → Preview in the builder; **Export pack zip** or **Open in Studio**. When `VITE_STUDIO_URL` is set, Open in Studio stages the zip (`POST /api/handoffs`, CORS + token documented below). Pick a project/episode → review the **pack revision diff** → Confirm import. The file is not re-chosen when the handoff carried the zip. **Never auto-generate**
9. Confirm candidates, set shots `ready` (prepared, not generating)
10. Enqueue stub jobs. Bell shows **job succeeded/failed**. Optional `STUDIO_NOTIFY_WEBHOOK_URL` POSTs the same JSON when set; unset means in-app only (`/api/meta` reports `notify_webhook_configured`)
11. Hop-1 preview desk → shot comments (`@name` mentions) → preview-watched → a **reviewer or producer signs off** → `generate-ok`
12. **Export backup zip** (org/project/episode metadata + media manifest hashes). Restore dry-run, then apply. **Pack revisions are never deleted.**
13. `/healthz` liveness, `/readyz` DB + worker mode, `/metrics` Prometheus text (optional scrape — not a SaaS APM)

## Compose deploy pack

```bash
docker compose -f docker-compose.studio.yml up --build
```

| Service | Port | Notes |
|---|---|---|
| `studio-api` | 8000 | FastAPI + in-process **thread** worker. SQLite volume `studio-data:/data` |
| `studio-web` | 5174 | nginx SPA; `/api` and `/health` proxy to the API |

Optional profiles (not production SSO, not a live IdP):

| Profile | What |
|---|---|
| `worker` | Standalone **thread** poller (`python -m app.jobs`). Set `STUDIO_JOB_WORKER=off` on the API so only one process dequeues |
| `postgres` | Postgres 16. Point `STUDIO_DATABASE_URL` at it **and** install the API `postgres` extra |
| `minio` | Local object store on 9000/9001. Set root user/password in the **shell**. Then `STUDIO_MEDIA_BACKEND=s3`, `STUDIO_S3_ENDPOINT=http://127.0.0.1:9000`, `STUDIO_S3_BUCKET=…`. Unset → local disk stays honest |
| `celery` | Redis 7 + Celery worker. Set `STUDIO_JOB_WORKER=celery` **and** `STUDIO_CELERY_BROKER_URL` (compose default `redis://redis:6379/0`) on the API. Tasks enqueue/dequeue the same `Job` rows. **Never** also run the thread worker against the same SQLite file. Prefer `postgres` with Celery |

```bash
# Celery opt-in (API must not use the thread worker on this SQLite file)
STUDIO_JOB_WORKER=celery STUDIO_CELERY_BROKER_URL=redis://redis:6379/0 \
  docker compose -f docker-compose.studio.yml --profile celery up --build
```

OIDC env vars (`STUDIO_AUTH_MODE=oidc`, `STUDIO_OIDC_ISSUER`, `STUDIO_OIDC_AUDIENCE`, optional client id / JWKS URL / role map) pass through compose. Empty issuer = OIDC is **not** configured. No secrets belong in the repo.

The older `docker-compose.yml` is still API-only.

## Adapters + health

Registry: `stub` (default, not live) plus documented slots `comfy-h3` (clip), `comfy-qwen` (still), `webhook`, `cli`. Per-project still/clip default. Unset live hooks **always** resolve to stub and report **not live**.

| Env | Default | Notes |
|---|---|---|
| `STUDIO_STILL_ADAPTER` | `stub` | `stub` \| `comfy-qwen` \| `webhook` \| `cli` |
| `STUDIO_CLIP_ADAPTER` | `stub` | `stub` \| `comfy-h3` \| `webhook` \| `cli` |
| `STUDIO_ADAPTER_WEBHOOK_URL` | empty | Fallback transport when native Comfy lanes are unset. Unset → **not live**, stub only |
| `STUDIO_ADAPTER_CLI` | empty | `{job_id} {job_type} {episode_id} {shot_id}` template; JSON on stdin. Fallback when lanes are unset |
| `STUDIO_ADAPTER_TIMEOUT_SECONDS` | `60` | Must be > 0 (schema-validated) |
| `STUDIO_COMFY_STILL_LANES` | empty | Comma-separated ComfyUI base URLs for Qwen-Image. Empty → comfy-qwen is **not live** |
| `STUDIO_COMFY_CLIP_LANES` | empty | Comma-separated ComfyUI base URLs for MiniMax H3. Empty → comfy-h3 is **not live** |
| `STUDIO_COMFY_IMAGE_LANES_FOR_FREE` | empty | Sibling still lanes. Studio `POST /free`s them before a clip when they share VRAM |
| `STUDIO_COMFY_ALLOW_HOSTS` | empty | Extra trusted hostnames. Loopback and private IPs are already allowed |
| `STUDIO_COMFY_OUT_DIR` | media root `comfy/` | Where the client writes the PNG or mp4 before the media store copies it |
| `STUDIO_COMFY_H3_STYLES` | empty | Optional JSON `{ "name": {"file", "trigger"} }`. No style LoRA unless you set this |
| `STUDIO_COMFY_POLL_INTERVAL_SECONDS` | `15` | How often a running clip job checks ComfyUI history |

Measured window metadata (declared on the slot, not a generate):

| Slot | Kind | Declared window / canvas | Hop-1 watch |
|---|---|---|---|
| `comfy-h3` | clip | **10.125 s / 243 f @ 24 fps** (measured hop-1 default) | required — live adapters must not skip |
| `comfy-qwen` | still | canvas **1344×768** | hop-1 watch still required before generate-ok |
| `stub` | both | same numbers on fixture receipts | required |

`GET /api/adapters` lists slots + health + window metadata. `GET /api/adapters/{id}/health` and `POST /api/adapters/{id}/dry-run` ask: config present? schema valid? reachable? They do **not** enqueue a generate. Stub is always ok. Unset hooks report `not_live` and enqueue still falls back to stub. A configured live slot that is down **blocks enqueue** (409 `adapter_unhealthy`). This PR does **not** add Hailuo / Veo / Kling.

Point a live Comfy box (optional):

```bash
export STUDIO_STILL_ADAPTER=comfy-qwen
export STUDIO_CLIP_ADAPTER=comfy-h3
export STUDIO_ADAPTER_WEBHOOK_URL="http://127.0.0.1:8188/studio-hook"   # or
export STUDIO_ADAPTER_CLI="/path/to/comfy-hook.sh {job_id} {job_type} {episode_id} {shot_id}"
```

Honesty labels in the studio adapter strip: **ok** (stub), **not live** (hook unset), **live**, or **down**. A **lanes** badge means `STUDIO_COMFY_*_LANES` is set. Studio chrome never claims H3 or Qwen ran unless a live adapter actually ran. Stub receipts keep `called_comfy` off. Export for agent still does not call Comfy.

## Phase 11 — native ComfyUI stills and clips

When the lane env vars are set, `comfy-qwen` and `comfy-h3` talk to ComfyUI directly (Python, no Node plugin). When they are unset, behavior matches earlier phases: **not live**, enqueue resolves to stub.

| | Qwen-Image still (`comfy-qwen`) | MiniMax H3 clip (`comfy-h3`) |
|---|---|---|
| Pick | `GET /queue` on each lane. A free lane runs. If every lane is busy or down, the job fails with a clear refusal. Studio does not sit behind a long render. | Same, on the clip lanes |
| Dispatch | `POST /prompt` with the Qwen graph. Poll `GET /history/<id>`. Download `GET /view`. | Returns `{job_id, eta}` on the Studio job immediately. Poll the job until the mp4 path is stored |
| Output key | `images` | `images` (a `video` key alone is not done) |
| Sizes | `square` 1328², `landscape` 1664×928, `portrait` 928×1664, `studio` / `pack` 1344×768 | 960×544. Frame count snaps **down** onto 17n+5 at 24 fps. Max 362 frames (~15.1s). Default hop-1 stays **10.125s / 243f**. The snap is on the job receipt |
| Quality | 20 steps | `full`: 20 steps, no SigmaShift. `fast` or `turbo`: 8 steps and SigmaShift 12.0 / 3.0. SigmaShift is not applied on full |
| Files | Checkpoint names from env (`STUDIO_COMFY_QWEN_*`). See `studio/comfy.example.json` | `STUDIO_COMFY_H3_*`. Style LoRA only if `STUDIO_COMFY_H3_STYLES` is set |
| Result | PNG path text on the job. Bytes live in the media store | mp4 path text after the poll. Bytes live in the media store |
| Watch | Hop-1 watch stays required | A finished clip does **not** stamp preview-watched |

Edits: a prompt may include `reference: /path/to/file` (up to 10). Those paths are recorded as text. The still graph Studio sends is the published text-to-image graph. Pixels are not copied into the receipt.

Security: lane URLs must be `http`/`https` on loopback, a private address, or a name listed in `STUDIO_COMFY_ALLOW_HOSTS`. Do not point Studio at a public ComfyUI. ComfyUI on these lanes has no auth of its own. Keep it on `127.0.0.1` or a private network.

Honesty: `honesty.called_comfy` on an agent export stays false. Export does not generate. Running live jobs and then exporting is a later option, not this endpoint. A stub job never sets `called_comfy`. A refused busy lane does not either. A prompt ComfyUI accepted does.

Example (override the ports; they are not the only legal values):

```bash
export STUDIO_STILL_ADAPTER=comfy-qwen
export STUDIO_CLIP_ADAPTER=comfy-h3
export STUDIO_COMFY_STILL_LANES="http://127.0.0.1:8190"
export STUDIO_COMFY_CLIP_LANES="http://127.0.0.1:8188"
export STUDIO_COMFY_IMAGE_LANES_FOR_FREE="http://127.0.0.1:8190"
```

Attribution: MIT, Copyright (c) 2026 tonyd2wild, DeepSeek-Harness-Image-Tools and DeepSeek-Harness-Video-Tools. See [NOTICE](../NOTICE) and [THIRD_PARTY.md](../THIRD_PARTY.md). Studio is a rewrite for this stack. No DeepSeek endorsement. We do not own MiniMax, Qwen, or ComfyUI.

## Visual identity store

Sheets (character/prop bible) and per-window plates are first-class media with `draft → approved` (who / when). Link a plate to a shot / edit-list window. Only **approved** sheets/plates count for lock-diff extras and I2VA plate-bind / generate readiness. Synonym lock-diff groups are unchanged (explicit list, not embeddings). Continuity panel deep-links into `#/projects/<id>/episodes/<id>/identity/<assetId>`.

Public trees use fixture/placeholder JSON metadata. Do not commit likeness stills.

`GET /api/episodes/{id}/identity` · `POST …/identity/{assetId}/approve` · `POST …/identity/{assetId}/link`

## Pack revision diff

Diff two stored `PackRevision`s, or the current episode pack vs a candidate import (zip or builder handoff). Compares gates, entity-schedule, edit-list, and identity keywords. Studio-web shows the structured diff **before** overwrite; Confirm applies. Audit: `pack.diff` (preview) and `pack.import` (apply).

`GET /api/episodes/{id}/revisions/{left}/diff/{right}` · `POST /api/episodes/{id}/pack/diff`

## Pack ↔ studio bridge (auto-import)

Studio-web deep links (shareable):

- `#/projects/<projectId>`
- `#/projects/<projectId>/episodes/<episodeId>`
- `#/projects/<projectId>/episodes/<episodeId>/shots/<shotId>`
- `#/projects/<projectId>/episodes/<episodeId>/identity/<assetId>`

Handoff from the pack builder: **Open in Studio** (`VITE_STUDIO_URL`, default http://localhost:5174) stages the current pack zip:

| Builder env | Default | Role |
|---|---|---|
| `VITE_STUDIO_URL` | `http://localhost:5174` | Studio shell to open |
| `VITE_STUDIO_API_URL` | `http://localhost:8000` (derived from Vite 5174) | FastAPI for `POST /api/handoffs` |
| `VITE_STUDIO_TOKEN` | local-dev default on localhost only | Must match `STUDIO_API_TOKEN`. Leave empty off-localhost |

CORS: `STUDIO_CORS_ORIGINS` already includes `http://localhost:5173`. Studio-web consumes `?handoff=<id>` after you pick a project/episode — import does **not** re-ask for the file. You still Confirm the pack diff. Query `?import=1` remains a hint if staging failed.

Failure modes (documented in the builder toast — never claimed as auto-generate):

- **Studio down / CORS**: zip is not staged; export the zip and Import pack zip by hand
- **Auth 401/403**: set `VITE_STUDIO_TOKEN` to the same local-dev token the studio API expects
- **Expired / already imported handoff**: stage a new zip from Open in Studio

`POST /api/handoffs` · `GET /api/handoffs/{id}` · `POST /api/episodes/{id}/pack` with `handoff_id`

A `handoff_id` is the zip that imports (it wins over a file part sent in the same request). Consume is single-use. `episode_id` on the handoff must belong to the active org. Studio-web accepts builder `postMessage` bytes only from the pack-builder origin (or the studio origin).

## Presence + comments

`POST /api/episodes/{id}/presence` heartbeat; `GET` who’s on the episode (TTL `STUDIO_PRESENCE_TTL_SECONDS`, default 60). Optional `GET …/presence/stream` SSE.

Comments: episode thread plus `shot_id` / `board_node_id`. `POST /api/comments/{id}/resolve`. Audit: `comment.create`, `comment.resolve`.

## Budget

Job rows store `estimated_cost_units` at enqueue and `actual_cost_units` on success (0 on fail/cancel). Units come from `STUDIO_COST_RATES` (default `stub:0.1,webhook:1,cli:1,comfy-h3:2,comfy-qwen:0.5`). `STUDIO_COST_CURRENCY` defaults to `credits`. Optional `STUDIO_COST_USD_PER_UNIT` is an estimate only.

`STUDIO_BUDGET_CAP_UNITS` + `STUDIO_BUDGET_HARD_STOP` are env defaults; each project can override (**producer** only). Hard stop returns **409** `budget_cap` when spent + pending + new estimate would exceed the cap.

This never claims a cloud bill was paid.

## Audit + retention

Audit table: `review.set`, `review.signoff`, `review.override`, `job.enqueue`, `job.cancel`, `pack.import`, `pack.export`, `pack.diff`, `pack.save`, `brain.dump`, `agent.export`, `media.upload`, `identity.approve`, `identity.unapprove`, `identity.keywords`, `identity.link`, `episode.reorder`, `project.create`, `retention.apply`, `comment.create`, `comment.resolve`, `member.add`, `member.role`, `org.create`, `backup.export`, `backup.restore`, `demo.seed`. `GET /api/audit?project_id=&episode_id=&action=`. Scoped to the active org.

Retention: `STUDIO_RETENTION_DAYS` (default 30; `0` disables). Project override allowed (producer). `GET /api/retention` (dry-run) and `POST /api/retention` with `{ "dry_run": false, "confirm": "expire" }` deletes **ephemeral** stub job outputs / temp media older than N days. **Pack revisions are not deleted.** Episode **season/sequence order is preserved**; retention does not reorder or delete episodes. Backup manifests store that order and restore it with the episode.

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

## Jobs (Phase 3 contract, Phase 6 worker)

Types: `still-sheet | still-plate | clip-hop1 | clip-extend | batch-precheck`

Default worker: in-process **thread** (`STUDIO_JOB_WORKER=thread`). Optional `celery` mode uses Redis (`STUDIO_CELERY_BROKER_URL`) and Celery tasks against the same `Job` rows (`pip install -e "./studio[celery]"`). Tests use `inline` or `off`; the celery path is mocked unless Redis is available.

## Review gate matrix (Phase 6, still)

Before `generate-ok`:

1. Latest pack revision: all gates green
2. Each required hop-1: preview-watched continuity receipt, no NG reason — **live adapters (comfy-h3 / comfy-qwen / webhook / cli) must not skip this**
3. At least one **sign-off** record from a `reviewer` or `producer` (who / when / note)
4. I2VA plate bind uses **approved** identity plates only (draft sheets/plates do not count). Label match is exact (take `A` does not match a plate named `smith`). `generate-ok` returns 409 `identity_lock_diff` or `plates_unbound` when this fails. Approved lock keywords are stamped on approve. Unapprove and keyword-save return the asset to draft; those keywords do not count until re-approve. Synonym groups are unchanged.

`POST /api/episodes/{id}/review/signoff`. Viewers cannot sign off. Editors cannot sign off. A producer may stamp `generate-ok` with `{ "override": true }` — audited as `review.override`. Sign-off itself is `review.signoff`.

## Hop-1 preview desk

Required hop-1 = first edit-list row of each take with `hop1Planned`. `generate-ok` and `clip-extend` stay 409 until every required hop-1 has preview-watched + receipt and no NG reason. `generate-ok` also stays 409 until a reviewer/producer sign-off exists (unless a producer override is audited).

## API surface

OpenAPI is canonical: http://localhost:8000/docs

Phase 2–9 surface still applies. Phase 10 adds:

| Area | Methods |
|---|---|
| Create | `POST /api/studio/start` with `mode` `blank` \| `template` \| `brain`. Org-scoped project + episode + pack revision. No zip |
| Episodes | `POST /api/projects/{id}/episodes` accepts `pack=blank`, `template_id`, or `brain_dump` |
| Brain dump | `POST /api/episodes/{id}/brain-dump`. Draft skeleton. `model_ran` is false unless the optional endpoint returned JSON |
| Editor | `POST /api/episodes/{id}/pack/json` saves a new revision from the in-studio stages |
| Reset | `POST /api/episodes/{id}/pack/blank` with `confirm=reset` when a revision already exists |
| Agent | `GET /api/episodes/{id}/export/agent` — zip contract for Hermes / OpenClaw / Grok. Does not call Comfy |
| Meta | `phase` is 10. `llm_configured` is false when `STUDIO_LLM_BASE_URL` is unset. `primary_create` is `studio` |

Phase 9 adds:

| Area | Methods |
|---|---|
| Roles | `writer` and `art` on member create/patch. `GET /api/meta` `role_matrix`. `phase: 9` |
| Episodes | `season`, `sequence`, `log_line`, `map_notes`, `dialogue`. `POST /api/projects/{id}/episodes/reorder` |
| Playlist | `GET /api/episodes/{id}/playlist-scrub` (metadata + preview media flags; not an NLE) |
| Identity | `POST …/identity/{assetId}/unapprove`, `POST …/identity/{assetId}/keywords` (draft; does not count until approve) |
| Shots | `PATCH /api/episodes/{id}/shots/{shotId}` join / camera verb / action (edit permission) |
| Pack diff | entity-schedule `ambiguous` when rows share kind/name/take/windows |

Phase 8 surface:

| Area | Methods |
|---|---|
| Identity | `GET /api/episodes/{id}/identity`, `POST …/identity/{assetId}/approve`, `POST …/identity/{assetId}/link` |
| Pack diff | `GET /api/episodes/{id}/revisions/{left}/diff/{right}`, `POST /api/episodes/{id}/pack/diff` |
| Handoff | `POST /api/handoffs`, `GET /api/handoffs/{id}`; import accepts `handoff_id` |
| Adapters | catalog/health include window metadata, `not_live`, `schema_ok`, `hop1_watch_required` |
| Meta | response `phase` is 10 (see the Phase 10 table). Phase 9 fields remain |
| Orgs | `GET/POST /api/orgs`, `GET /api/orgs/{id}`; members stay `…/members`. Header `X-Org-Id` selects the active org |
| Notifications | `GET /api/notifications`, `POST /api/notifications/read-all`, `POST /api/notifications/{id}/read` |
| Continuity | `GET /api/episodes/{id}/continuity` (read/visualize + navigate, not an NLE; identity deep-links) |
| Demo | `POST /api/demo/seed` |
| Backup | `GET /api/backup`, `POST /api/backup/restore` (`dry_run` + `confirm=restore`) |
| Ops | `/healthz`, `/readyz`, `/metrics` (Prometheus text). `/api/meta` has `notify_webhook_configured`, `multi_org` |

## Tests

```bash
cd studio && python3 -m pip install -e ".[dev]"
python3 -m pytest

cd app && npm test

cd studio-web && npx tsc --noEmit
cd studio-web && npm run e2e
```

GitHub Actions (`.github/workflows/ci.yml`) runs studio pytest, pack-builder `npm test`, studio-web typecheck, and a Playwright smoke. The smoke prints `E2E_SKIP: playwright browsers unavailable` and exits 0 when Chromium cannot launch. It does not need live Comfy, S3, or OIDC.

## What this phase is not

- No Hailuo / Veo / Kling adapters (documented Comfy slots only; unset stays stub)
- Identity store is **not** embeddings and does **not** change synonym lock-diff groups
- Builder Open in Studio never auto-generates; staging can fail (studio down / auth)
- No full NLE timeline editor (continuity panel, playlist scrubber, and EDL/playlist export are metadata plus local preview playback only)
- No Hermes Desktop pane (separate plugin)
- Playlist scrubber does not invent MP4s. A missing or JSON stub preview stays a stub
- Celery is **optional** and off by default — never claimed running unless `STUDIO_JOB_WORKER=celery`
- OIDC is **optional** and off by default — this repo does not ship a production IdP
- Multi-org lite is **not** SaaS billing, SSO org mapping, or a multi-tenant product
- Optional notify webhook is **unset by default** — `/api/meta` says so; we never invent delivery
- `/metrics` is an optional Prometheus scrape, not a claimed SaaS APM
- No rewrite of the pack builder. Studio reuses its stage components. The builder’s New pack / Load sample / Import zip ask with an in-app confirm
- Hermes `smf-h3-capture` is not rewritten. Studio is the primary create surface
- No mandatory live LLM and no mandatory live Comfy. Brain dump without `STUDIO_LLM_BASE_URL` is a template expansion. Agent export does not call Comfy
- A brain dump or blank pack is not generate-ready. Gates stay red until filled. `generate_ready` on these responses is false
- No engine MP4s in git
- No auto generate-ok from shot `ready`, candidate extract, a succeeded stub job, a vertical template, or a missing sign-off
- No claim that budget units are a paid cloud invoice
- No claim that S3/MinIO is live when `STUDIO_MEDIA_BACKEND` is unset or the bucket is empty
