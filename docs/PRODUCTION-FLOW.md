# AIGC production flow

This repo is a **video production flow**, not a MiniMax wrapper. MiniMax H3 on a DGX Spark is the stack we measured first. The product is the line that makes short dramas and long-form video **planable, reviewable, and scalable** before anyone spends GPU.

Target shape:

**Script analysis → Asset setup → Storyboard → Video preview**

Editor-level precision. Built-in consistency checks. Multi-user collaboration. Engine adapters underneath — not in the title.

Do not queue generate until the four stages below are green. Serving pins stay in SMF ops. Prompt syntax stays with the active engine adapter.

## Why the model is not the product

Short drama in 2026 is a content business, not a five-second demo. A video model can make a hallway confrontation. It does not know which script version, which approved face, which episode-12 / scene-4 plate, or which subtitle pass cleared review.[15][16]

Industry pattern (extract, do not clone):

- Script / storyboard / character layer is the pre-production bottleneck.[15]
- Consistency is a first-class problem: characters, costumes, locations, props as reusable assets, not prompt paragraphs.[16]
- Generation is a trackable job, not a chat turn.[16]
- The winning stack is a production line, not one brand of model.[15]

SMF already paid for this lesson. *Sigils in the Steel* (28 windows) held picture and missed the song because research was not a pin, the map was not an edit list, and there was no prop still. Receipts: [Clearinghouse 2026-09-16](https://www.smfclearinghouse.com/blog/2026-09-16-h3-sigils-four-minutes).

We do **not** wholesale-adopt another studio (Jellyfish, AniShort, LTX Studio, CapCut). One SMF testing standard. Take the production-flow idea. Keep our gates, joins, and sheet-vs-plate rule.

## The four stages

| Stage | Operator question | Pack objects | Gate ids |
|---|---|---|---|
| **1. Script analysis** | What is this piece, in order, without cameras? | Log line, duration, audio path, speech rule, **map** (clock → beat, not shots) | `log-line`, `map`, `audio` |
| **2. Asset setup** | Who/what must persist, with stills or an explicit `none`? | Character cards, prop cards, look card, **sheets** then **plates** | `characters`, `props`, `look` |
| **3. Storyboard** | How does picture join, one camera verb per window? | Take cards (one location + one grade), edit list (`continue` / `cut` / `fadeblack`) | `takes`, `edit-list` |
| **4. Video preview** | Did hop-1 hold identity at the planned cuts *before* we spend the night? | Hop-1 smoke plan, continuity log | `smoke` |

Nine gates, four stages. The gates did not go away. They got a production order.

Fill order in the builder: Script → Assets → Storyboard → Preview. Do not board a face you have not locked. Do not preview a board with no join type.

## Editor-level precision (non-negotiable)

These are editorial rules, not model folklore:

1. **Map ≠ shot list.** Beats and clocks first. Cameras live on the edit list.
2. **Three joins only.** `continue` (same room, action continues), `cut` (new angle/plate, no hold), `fadeblack` (new location / grade / time of day).
3. **One camera verb per window.** Type + amplitude + speed. “Pan and zoom and circle” is three rows or it is refused.
4. **Sheet vs plate.** A sheet is the character/prop bible. A plate is the first frame of *this* window. Do not stretch a 1024² sheet onto a 16:9 hop-1. Procedure: [IMAGE-STILLS.md](IMAGE-STILLS.md).
5. **Numbers before generate.** If the script already has 45 cm / 600 g / 10 cm, copy them onto the prop card. “Research the axe” is treatment homework.
6. **Audio is one path.** Mute in the NLE and lay the mastered track, **or** let the engine invent a score, **or** silence. Not two of those.
7. **Preview before spend.** One hop-1 per take, watched at the planned fades. A hop-1 with no saved motion context cannot be extended.

Default measured window (H3 adapter): hop-1 **10.125 s / 243 f @ 24 fps**. Speech and chorus hits finish by **8.0 s**. Hold only before `fadeblack`. Other adapters must declare their window length; they do not get to skip the join types.

## Built-in consistency checks

The pack builder already refuses export until gates are green. That is the v1 consistency engine. It checks:

- lock paragraph + forbidden list on every character and prop
- still path or explicit `none` + why
- sheet vs plate role, canvas, and “does this plate condition hop-1?”
- one join + one camera verb per edit row
- one location + one grade per take
- hop-1 mode: I2VA if a plate exists, else T2V
- no “research …” language on a pin field

**Phase 2 (this repo, delivered):**

- **Entity schedule** — who/what must persist across which takes/windows. Gate `entity-schedule` fails if a scheduled entity is missing from a required window, or if identity must hold at `cut` / `fadeblack` and no plate is bound to that entity (or explicit `none` + why). `continue` hop 2+ is the latent — no new plate.
- **Lock-diff** — same identity keywords every hop. Rotating synonyms (`brown` / `brunette`) are a red `lock-diff` gate. The synonym groups are an explicit list, not embeddings.
- **Studio shot readiness** — edit-list rows map to shots: `draft → candidates → linked → ready`. `ready` means prepared, not generating.
- **Candidate confirm** — stub extract or manual add; accept / ignore / link existing character|prop|scene|costume assets. Human in the loop. Never auto-stamps `generate-ok`.
- **Costume** — linkable media kind / entity type in the studio library.
- **Storyboard canvas** — list (precision) + board of takes/edit rows with join types; join inspector highlights continue chains vs cut/fadeblack boundaries.

Still deferred (NLE):

- Full NLE timeline editor (Phase 4 ships metadata-only EDL / FCP XML lite / shot playlist)

OIDC and Celery are **optional in Phase 6** and **off by default**. They are not a production IdP or a claimed live broker.

**Phase 3 (this repo, delivered):**

- **Preview receipt** — hop-1 preview desk: attach/upload preview media, duration/frames (manual or parsed JSON / ffprobe), still-vs-lock note, optional NG reason. Required before `generate-ok` and `clip-extend`
- Async generate jobs with cancel/retry (in-process thread worker default; Celery is opt-in in Phase 6)
- Engine adapters: still + clip factory interface; default `adapter=stub` with fixture receipts; optional webhook/CLI live hook (unset → stub only)
- `batch-precheck` job: gates green + shot ready + plates bound before hop-1 enqueue

**Phase 4 (this repo, delivered):**

- Adapter **catalog** with documented slots `comfy-h3` / `comfy-qwen` / `webhook` / `cli` plus per-project default. Unset hooks still resolve to stub
- Job **cost units** (estimated/actual) from an operator rate table; producer **Budget** dashboard; optional hard stop at a budget cap. Never a cloud invoice
- **Audit log** (review, jobs, pack import/export, media upload) and **retention** dry-run/apply for stub/temp media (pack revisions kept)
- Light **EDL / FCP XML lite / shot playlist** export from the edit list + continue chains
- **Vertical templates** (education lesson, brand promo, short drama ep) — empty structured packs, no fake generate

**Phase 5 (this repo, collaborate & operate):**

- App-level **RBAC lite** (`producer` / `editor` / `reviewer` / `viewer`) on the default org. Seed local-dev user as producer. Viewers are read-only. Identity is still local token or `X-Forwarded-User` unless OIDC is explicitly enabled
- **Presence** heartbeats (TTL ~60s) and **shot comment** threads (create / list / resolve) with audit
- **Media store adapters**: local disk default; optional S3/MinIO when `STUDIO_MEDIA_BACKEND=s3` and a bucket are set. Unset stays local and never claims cloud storage is live
- Adapter **health / dry-run** (reachable? config present?) plus a studio status strip. Unhealthy live slots 409 on enqueue. Stub remains default
- Compose pack: `docker compose -f docker-compose.studio.yml up` (API + studio-web; optional worker / Postgres / MinIO profiles)

**Phase 7 (this repo, scale the team & see the system):**

- **Multi-org lite** — create orgs, list memberships, switch active org. Members/projects scoped; cross-org 404. Not SaaS billing, not SSO org mapping. Default org remains for local-dev / existing DBs
- **In-app notifications** (job succeeded/failed, comment mention / watched-shot comment, sign-off requested, generate-ok blocker cleared) plus optional `STUDIO_NOTIFY_WEBHOOK_URL` (unset = no outbound delivery)
- **Ops visibility:** `/healthz`, `/readyz` (DB + worker mode), structured JSON request logs, `/metrics` Prometheus text (optional scrape, not APM)
- **Continuity panel** — entity-schedule + lock-diff summary, red gates, deep-link to the shot board. Read/visualize + navigate only. Not an NLE
- **Demo seed** (`POST /api/demo/seed`) from a vertical template with fixture media metadata (no likeness, no MP4 claims)
- **Backup/restore** — org/project/episode metadata + media manifest (paths/hashes). Restore dry-run then apply. Pack revisions are never deleted

**Phase 8 (this repo, identity + pack diff + auto-import + measured Comfy hooks):**

- **Visual identity store** — approved sheets and per-window plates as assets linked to characters/props/scenes and to shots/windows. Draft → approved (who/when). Only approved sheets/plates count for lock-diff extras and I2VA generate readiness. Not embeddings. Synonym lock-diff groups unchanged. Fixture/placeholder metadata in tests/seed — no likeness stills in the public tree
- **Pack revision diff** — API diffs two `PackRevision`s or current pack vs a candidate import (gates, entity-schedule, edit-list, identity keywords). Studio-web shows the structured diff before overwrite; Confirm applies. Audit `pack.diff` / `pack.import`
- **Builder → studio auto-import** — Open in Studio stages the zip (`POST /api/handoffs`) when `VITE_STUDIO_URL` is set (CORS/token documented). Pick project/episode → import uses the handed-off zip (no re-choose file). Failure modes: studio down, auth. Never auto-generate
- **Measured live Comfy hooks** — `comfy-h3` declares hop-1 **10.125 s / 243 f @ 24 fps**; `comfy-qwen` declares canvas **1344×768**. Health/dry-run include config schema validation. Unset env is **not live** and still resolves to stub. Hop-1 watch protocol remains required; live adapters must not skip it. Stub remains default. No Hailuo/Veo/Kling in this phase

**Phase 9 (this repo, roles, order, scrub, identity edit):**

- **Role matrix** — pack-convention `writer` (script/map/dialogue, episode order) and `art` (sheets/plates/identity approve) sit beside the Phase 5 roles. Legacy `editor` stays the craft bundle (those writes plus joins/board/edit-list, jobs, pack). `producer` keeps gates governance, GPU budget, retention, members, and generate-ok override. Reviewers still sign off. Viewers stay read-only. App-level only — not IdP groups unless the OIDC claim map is on
- **Episode order** — `season` + `sequence` on each episode, reorder API, studio-web up/down. Backup and retention preserve that order; retention does not delete or reorder episodes
- **Soft playlist scrubber** — studio-web steps through the shot playlist and plays a local/stub `kind=preview` file when one is stored. Metadata otherwise. Not an NLE. No invented MP4s
- **Identity unapprove + keyword edit** — audited unapprove; saving keywords on an approved asset returns it to draft. Only the approved set counts for generate-ok. Synonym lock-diff rules unchanged
- **Pack diff** — distinct entity-schedule rows that share kind/name/take/windows are not collapsed (matched by id, or by occurrence when id is missing, and marked ambiguous)
- **Playwright smoke** — headless demo seed → continuity/identity signals → API-assisted sign-off and stub precheck. Skips with `E2E_SKIP` when browsers are unavailable. No live Comfy/S3/OIDC

v2 leftover (platform, do not pretend we have it):

- GPU queue / one engine adapter at a time per GPU (ops pin)
- multi-tenant SaaS billing / SSO org mapping
- Hermes Desktop studio pane (separate plugin)

**Phase 6 (this repo, production readiness):**

- Optional **Celery** (`STUDIO_JOB_WORKER=celery` + Redis broker). Default remains the in-process thread worker. Never run both against the same SQLite file.
- Optional **OIDC** (`STUDIO_AUTH_MODE=oidc` + issuer JWKS). Off by default. Not a production IdP.
- **Review sign-off** required before `generate-ok` (reviewer or producer; producer override audited)
- Pack ↔ studio **deep links** and builder **Open in Studio** import handoff (`?import=` hint; Phase 8 upgrades this to a staged zip)
- GitHub Actions CI: studio pytest, pack-builder `npm test`, studio-web typecheck

**Phase 1 (this repo, studio spine):** review states and a local media store for sheet/plate metadata + files are delivered. Pack zip import/export creates `PackRevision` rows (pack.json + gate snapshot). Auth is a local-dev API token plus optional reverse-proxy / optional OIDC. Operator path: [STUDIO.md](STUDIO.md). Auth: [AUTH.md](AUTH.md).

**Phase 3 (this repo, jobs + desk):** `generate-ok` is refused unless that snapshot is all green **and** each required hop-1 is preview-watched with a continuity receipt. Stub jobs never stamp generate-ok.

**Phase 6 (this repo, production readiness):** `generate-ok` also needs a reviewer/producer sign-off (or an audited producer override). Celery and OIDC remain opt-in.

**Phase 4 (this repo, scale & polish):** set adapter defaults + budget cap → run stub jobs → see spend → audit trail → export EDL → create a project from a vertical template.

**Phase 5 (this repo, collaborate & operate):** add a member as viewer → cannot enqueue → promote to editor → comment on a shot → see presence. Adapter health strip. Optional MinIO/S3 when env is set. `docker compose -f docker-compose.studio.yml up`.

## Multi-user collaboration

v1 (now, honest): the pack **is** the collaboration object.

- Templates under `templates/` are the source of truth
- Export is a markdown zip in that shape — writers, art, and editors can pass the zip
- Public GitHub is process only. Private fork (or sibling private repo) holds likeness stills and unreleased music
- Roles on a pack (convention, not auth): **writer** (script + map), **art** (sheets/plates), **editor** (joins + verbs), **producer** (gates green / GPU spend)

Phase 1 (this repo): a **studio spine** holds projects / episodes, comments, review state, and a gitignored media directory. The zip is still the round-trip. Do not treat `STUDIO_API_TOKEN` as multi-tenant isolation.

Phase 5 (this repo): org **members** with app-level roles. Pack zip is still the collaboration object. Identity is still not OIDC.

Phase 7 (this repo): **multi-org lite** — a producer can create a second org and switch. Members of org A cannot read org B. Still not SaaS billing.

Phase 9 maps that convention onto org members. It is still app-level, not IdP groups.

| Role | Writes | Reviews |
|---|---|---|
| Writer | log line, map, dialogue finish-by, episode season/sequence | retention hooks stay producer-only; order is the writer reorder API |
| Art | sheets, plates, identity approve / unapprove / keywords | identity vs lock (approved set only) |
| Editor | takes, edit list, joins — and, for the **legacy editor role**, the writer + art bundle plus jobs and pack import | one verb, fade vs cut |
| Producer | audio path, generate-ok override, budget, retention, members | GPU budget, license |
| Reviewer | comments, review set | preview watch, NG reason, **sign-off** |
| Viewer | none | read-only |

Do not stand a multi-tenant SaaS until the zip round-trip and the four-stage gate order are boring. Phase 7 multi-org lite stops at membership 404s.

## Engine adapters (H3 is one)

The flow does not name a model. Adapters do.

| Adapter | Job | Notes |
|---|---|---|
| **Still factory** | Sheets + plates | Measured: Qwen-Image-2.1 INT8 ConvRot, native 1344×768 |
| **Clip factory (default)** | Hop-1 I2VA / T2V + motion-context extend | Measured: Comfy native MiniMax H3 on spark-56bc |
| Future clip adapters | Same joins, same plates, declare window length | Documented slots: `comfy-h3`, `webhook`, `cli`. Cloud Hailuo / Veo / Kling only after a hop-1 watch protocol exists |

A pasted lock is not Ref2VA. Identity holds inside `continue`. Drift at `cut` / `fadeblack` is expected until a **plate** conditions hop-1.

Do not publish engine MP4s from this public tree. MiniMax Community License still applies to H3 outputs even though the *flow* is MIT.

## What this repo is not

- Not model weights
- Not a generate API
- Not a NLE
- Not AniShort, not Jellyfish, not CapCut
- Not a promise that hop-1 I2VA from a Qwen plate is a PSNR pin (prescribed; watch it)

## Verification

The flow is real when:

1. A stranger can name the four stages from the README without seeing “MiniMax” in the title.
2. The builder walks Script → Assets → Storyboard → Preview.
3. Export still requires every gate green (nine README gates plus entity-schedule and lock-diff).
4. A pack zip round-trips without a GPU.
5. GPU spend still happens somewhere else, after preview.
6. Studio `generate-ok` is refused unless the stored gate snapshot is all green, each required hop-1 has preview-watched + a continuity receipt, **and** a reviewer or producer has signed off (producer override is audited). Shot `ready` is prepared, not generating. Stub jobs do not stamp generate-ok.

## Sources

See [SOURCES.md](SOURCES.md) (15–16 are the 2026 production-flow pass).
