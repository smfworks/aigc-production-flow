# AIGC production flow

**Script analysis → Asset setup → Storyboard → Video preview.**

Lock the pack before you spend GPU. A song map and a Wikipedia tab are not a generate list.

This is SMF Works’ public **video production flow** for short dramas and long-form AIGC. It is paper, templates, and a client-side pack builder. It is not model weights and not generated video. MiniMax H3 on a DGX Spark is the clip engine we measured first — an adapter, not the product.

Product architecture: [docs/PRODUCTION-FLOW.md](docs/PRODUCTION-FLOW.md).

Companion writeup: [Lock the bible before the GPU](https://www.smfclearinghouse.com/blog/2026-09-17-h3-longform-capture-bible) (Clearinghouse, 2026-09-17).

Measured origin: [28 windows on one Spark: Sigils in the Steel](https://www.smfclearinghouse.com/blog/2026-09-16-h3-sigils-four-minutes).

Still factory: [Qwen-Image-2.1 on one Spark](https://www.smfclearinghouse.com/blog/2026-09-20-qwen-image-21-one-spark). How stills condition hop-1: [docs/IMAGE-STILLS.md](docs/IMAGE-STILLS.md).

## What this is for

Short dramas and long-form video that must hold:

- a face / wardrobe across many windows
- a prop (length, mass, edge — not “research the axe”)
- one grade and location per take
- music or dialogue timing (verse = take, chorus = cuts)

If you are generating a single smoke clip with no continuity, stop. You do not need this pack.

## Four stages

| Stage | You lock | You do not lock yet |
|---|---|---|
| **1. Script analysis** | Log line, duration, audio path, **map** (clock → beat) | Cameras, stills |
| **2. Asset setup** | Character / prop / look cards; **sheets** then **plates** | Generate |
| **3. Storyboard** | Takes (one location + grade) and edit list (`continue` / `cut` / `fadeblack`) | GPU |
| **4. Video preview** | One hop-1 per take, watched at the planned fades | The rest of the night |

Nine gates still sit under those stages, plus two Phase 2 consistency gates (`entity-schedule`, `lock-diff`). Details: [docs/PRODUCTION-FLOW.md](docs/PRODUCTION-FLOW.md).

## How to use this repo on GitHub

### 1. Get the templates

```bash
git clone https://github.com/smfworks/aigc-production-flow.git
cd aigc-production-flow
```

Or fork, then clone your fork. The old name `h3-longform-capture` redirects here.

### 2. Copy a pack for your job

```bash
mkdir -p packs/my-title
cp templates/capture-pack.md packs/my-title/README.md
cp templates/edit-list.md    packs/my-title/edit-list.md
cp templates/look-card.md    packs/my-title/look.md
cp templates/continuity-log.md packs/my-title/continuity-log.md
# one file per person / prop
cp templates/character-card.md packs/my-title/character-smith.md
cp templates/prop-card.md      packs/my-title/prop-francisca.md
cp templates/still-card.md     packs/my-title/still-hop1-a.md
```

Fill every `{TITLE}` / blank. Empty “still” fields must say `none` and why. A **sheet** (character/prop bible) is not a **plate** (hop-1 first frame).

### 3. Gate (do not queue generate)

Refuse generate until all of these are green:

1. Log line (one sentence)
2. Map (song clock or narrative beats — **not** shots)
3. Edit list (every row has a join type)
4. Take cards (one location + one grade)
5. Character cards (verbatim lock + forbidden)
6. Prop cards (numbers + units + still or `none`)
7. Look card (one style line)
8. Audio path (exactly one of: `N/A` + mute in the NLE, prompt score, silence)
9. Hop-1 smoke plan (one hop-1 per take — I2VA if a plate still exists, else T2V — watched, before hopping)
10. Entity schedule (who/what persists on which takes/windows; identity hold at `cut`/`fadeblack` needs a bound plate)
11. Lock-diff (same identity keywords every hop — `brown` vs `brunette` is red)

### 4. Join types (only three)

| Join | Picture tool | Use |
|---|---|---|
| `continue` | Motion-context hop, trim overlap, stream-copy concat | Same camera, same room, action continues |
| `cut` | New I2VA/T2V, hard cut, **no hold** | Chorus, beat, new angle |
| `fadeblack` | New take hop-1 + 8-frame dip-to-black | New location, grade, or time of day |

A pasted wardrobe paragraph is not a face lock. Identity holds **inside** `continue`. Expect drift at `cut` and `fadeblack` until a **plate** still conditions hop-1. Do not re-feed a still on hop 2+.

### 5. Still factory (Asset setup, before clip GPU)

Sheets and plates are generated on the image box (Qwen-Image-2.1), native **1344×768**, then copied to the clip box. Procedure: [docs/IMAGE-STILLS.md](docs/IMAGE-STILLS.md). Wikipedia is not a still. Do not stretch 1024².

### 6. Preview, then spend

One hop-1 per take with a saved motion-context latent and a unique prefix. I2VA if a plate exists. Join the planned fades. Watch. Only then extend.

Default measured window (H3 adapter): 1344×768, 6-step turbo, 10.125 s hop-1. Serving pins live in SMF ops, not here. See [the Sigils post](https://www.smfclearinghouse.com/blog/2026-09-16-h3-sigils-four-minutes) for the measured stack.

## App

Fill the pack in the browser. The four stages above are the walk; the gates (nine README plus entity schedule and lock-diff) are a live checklist. Export is a markdown zip in the same shape as `templates/` — not a generate, and not an MP4.

Live demo: [aigc-production-flow.vercel.app](https://aigc-production-flow.vercel.app) (old slug [h3-longform-capture.vercel.app](https://h3-longform-capture.vercel.app) still points at this build).

```bash
cd app && npm i && npm run dev
```

Open the Vite URL (default http://localhost:5173). First visit loads the Sigils **lessons** sample so the clocks and lyric numbers are visible; it is not a generate pack until overall vs haft is a real measurement (gate 6 stays red while haft is `none`). **New pack** starts blank, including Look. The current pack autosaves in `localStorage`; New pack and Load sample ask before they wipe it.

Vercel can host `app/` (set the project Root Directory to `app`). `npm test` covers gate/validation helpers; `npm run build` typechecks and bundles.

## Studio spine (Phase 9) vs pack builder

Two pieces, one contract:

| | Pack builder (`app/`) | Studio spine (`studio/` + `studio-web/`) |
|---|---|---|
| Job | Four-stage walk. Export markdown zip + `pack.json`. Entity schedule + lock-diff gates. List + canvas boards. **Open in Studio** stages the zip when the studio API is reachable. | Projects, ordered episodes, pack revisions, **pack diff**, **identity store** (unapprove + keyword edit), review **sign-off**, comments, media, shots, job center, stub adapters, hop-1 desk, **playlist scrubber**, budget, audit, EDL, templates, **writer/art/editor/producer** roles, presence, adapter health, **multi-org lite**, **notifications**, **continuity panel**, **demo seed**, **backup**. Optional Celery / OIDC. |
| Where | Client-side Vite app (still the live demo). | Local FastAPI + thin studio shell. Compose pack: `docker-compose.studio.yml`. |
| Auth | None (browser `localStorage`). | Local-dev API token + optional `X-Forwarded-User` + app-level org roles (`writer` / `art` plus the Phase 5 four). Optional OIDC JWKS (**off by default**). Roles stay app-level unless the OIDC claim map is on. Multi-org lite is membership isolation, not SaaS. [docs/AUTH.md](docs/AUTH.md). |
| Generate | Refuses export-as-complete until every gate is green. | Refuses `generate-ok` unless gates are green, hop-1 receipts are preview-watched, **and** a reviewer/producer has signed off. Default adapter=`stub`. Budget units are operator credits, not a cloud bill. Media is local disk unless S3 is configured. |
| Not this | NLE, GPU, MP4. | Full NLE, CapCut clone, a generate API, SaaS billing. Celery and OIDC stay opt-in. |

Pack zip remains the collaboration object. Do not skip gates. How to run: [docs/STUDIO.md](docs/STUDIO.md).

```bash
./scripts/dev-studio.sh all
# API     http://localhost:8000/docs
# Studio  http://localhost:5174
# Builder http://localhost:5173
```

Set adapter defaults + budget cap → run stub jobs → see spend on Budget → audit trail → Export EDL → New from template. Add a member as viewer (cannot enqueue) → promote to editor → comment on a shot → presence chips. Assign **writer** and **art** as different roles (script vs identity). Reorder episodes. Scrub the shot playlist against a stub preview. Unapprove or edit identity keywords, then re-approve. Create a second org, switch, confirm the member cannot see it. Seed a demo episode. Approve a sheet, link a plate, open Continuity into identity. Diff two pack revisions before import (shared entity-schedule rows stay distinct). Open in Studio auto-imports after episode pick when configured. Bell on a stub job. `/readyz` green. Download a backup zip (season/sequence kept). A reviewer/producer **signs off**, then `generate-ok`. `generate-ok` stays blocked while any gate is red, a required hop-1 has no receipt, sign-off is missing, or approved identity keywords conflict. Unset comfy-* hooks stay stub / not live.

CI: GitHub Actions runs `studio` pytest, `app` `npm test`, `studio-web` `tsc --noEmit`, and a Playwright smoke (skips with `E2E_SKIP` if Chromium is unavailable) on every pull request and fails the PR on red.

```bash
docker compose -f docker-compose.studio.yml up --build
# API     http://localhost:8000/docs
# Studio  http://localhost:5174  (/api proxied)
```

## Layout

```
app/                     client-side pack builder (Vite + React) — do not rewrite
studio/                  FastAPI spine (SQLite default, Postgres-ready URL)
studio-web/              thin studio shell (lists, review, identity, playlist scrubber, pack diff, jobs, budget, audit, EDL, members)
docker-compose.studio.yml  API + studio-web (optional worker / postgres / minio / celery profiles)
scripts/dev-studio.sh    local API + studio + builder
data/                    local DB + media (gitignored)
templates/               blank cards (copy these) — source of truth
templates/verticals/     education / brand promo / short-drama empty packs
docs/PRODUCTION-FLOW.md  four stages, consistency, collaboration, adapters
docs/STUDIO.md           Phase 9 studio operator path (role matrix, episode order, scrubber, identity edit)
docs/AUTH.md             local / forward-header / optional OIDC — multi-org lite, not SaaS or a production IdP
docs/FRAMEWORK.md        why the pack looks like this
docs/IMAGE-STILLS.md     still factory → clip factory (sheet vs plate)
docs/HOW-TO.md           GitHub + local workflow, step by step
docs/REVIEW.md           end-to-end review of the pack builder (2026-09-17)
docs/SOURCES.md          citations
examples/                Sigils lessons (process only, no MP4s)
```

## Rules we will not bend

- Lyric numbers (45 cm / 600 g / 10 cm) go on a **prop card** before any browser call.
- “Research the axe” is treatment homework, not generate-time.
- One camera verb per window (type + amplitude + speed).
- Speech and chorus hits finish by **8.0 s** in a 10.125 s window. Hold only before `fadeblack`.
- `non_diegetic_music: N/A` + mute in the editor **or** a prompt score. Not both.
- Do not publish engine-generated MP4s from this workflow to the public tree.
- Do not publish likeness stills to this public tree. Private fork.

## License

MIT for this repo (templates, docs, and the client-side app). Clip-engine weights and outputs are a separate license (MiniMax H3: Community License).
