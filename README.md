# H3 long-form capture bible

**Lock the pack before you spend GPU.** A song map and a Wikipedia tab are not a generate list.

This repo is the public capture framework SMF Works now uses before MiniMax H3 long-form on a DGX Spark (Comfy native H3 + Motion-Context). Stills are a second Spark (Qwen-Image-2.1). It is paper, templates, and a client-side pack builder. It is not model weights and not generated video.

MiniMax H3 weights are under the MiniMax Community License. Generated MP4s stay internal. This repo is MIT.

Companion writeup: [Lock the bible before the GPU](https://www.smfclearinghouse.com/blog/2026-09-17-h3-longform-capture-bible) (Clearinghouse, 2026-09-17).

Measured origin: [28 windows on one Spark: Sigils in the Steel](https://www.smfclearinghouse.com/blog/2026-09-16-h3-sigils-four-minutes).

Still factory: [Qwen-Image-2.1 on one Spark](https://www.smfclearinghouse.com/blog/2026-09-20-qwen-image-21-one-spark) (Clearinghouse, 2026-09-20). How stills condition hop-1: [docs/IMAGE-STILLS.md](docs/IMAGE-STILLS.md).

## What this is for

Long-form H3 (story takes, lyric-timed music videos) that must hold:

- a prop (length, mass, edge, wood — not “research the axe”)
- a face / wardrobe
- one grade and location per take
- music timing (verse = take, chorus = cuts)

If you are generating a single 2/5/8 s smoke, stop. You do not need this pack.

## How to use this repo on GitHub

### 1. Get the templates

```bash
git clone https://github.com/smfworks/h3-longform-capture.git
cd h3-longform-capture
```

Or fork, then clone your fork.

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

### 3. Gate (do not queue Comfy)

Refuse generate until all nine exist:

1. Log line (one sentence)
2. Map (song clock or narrative beats — **not** shots)
3. Edit list (every row has a join type)
4. Take cards (one location + one grade)
5. Character cards (verbatim lock + forbidden)
6. Prop cards (numbers + units + still or `none`)
7. Look card (one style line)
8. Audio path (exactly one of: `N/A` + mute in the NLE, prompt score, silence)
9. Hop-1 smoke plan (one hop-1 per take — I2VA if a plate still exists, else T2V — watched, before hopping)

### 4. Join types (only three)

| Join | Tool on spark-56bc | Use |
|---|---|---|
| `continue` | Motion-Context hop, trim 22, `ffmpeg -c copy` | Same camera, same room, action continues |
| `cut` | New I2VA/T2V, hard cut, **no hold** | Chorus, beat, new angle |
| `fadeblack` | New take hop-1 + 8-frame `xfade=fadeblack` | New location, grade, or time of day |

A pasted wardrobe paragraph is not Ref2VA. Identity holds **inside** `continue`. Expect drift at `cut` and `fadeblack` until a **plate** still conditions hop-1 (`MiniMaxH3ImageToVideo.first_frame`). Do not re-feed a still on hop 2+ — that is Motion-Context.

### 5. Still factory (before GPU on 56bc)

Sheets and plates are generated on the image Spark (Qwen-Image-2.1), native **1344×768**, then copied to the clip Spark. Procedure: [docs/IMAGE-STILLS.md](docs/IMAGE-STILLS.md). Wikipedia is not a still. Do not stretch 1024².

### 6. Smoke, then spend

One hop-1 per take with `MiniMaxH3MotionContextSaveLatent` and a unique prefix. I2VA if a plate exists. Join the planned fades. Watch. Only then hop.

Serving pins (1344×768, 6-step turbo, 10.125 s hop-1, 85°C abort) live in SMF ops, not here. See [the Sigils post](https://www.smfclearinghouse.com/blog/2026-09-16-h3-sigils-four-minutes) for the measured stack.

## App

Fill the pack in the browser. The nine gates above are a live checklist. Export is a markdown zip in the same shape as `templates/` — not a generate, and not an MP4.

Live demo: [h3-longform-capture.vercel.app](https://h3-longform-capture.vercel.app)

```bash
cd app && npm i && npm run dev
```

Open the Vite URL (default http://localhost:5173). First visit loads the Sigils **lessons** sample so the clocks and lyric numbers are visible; it is not a generate pack until overall vs haft is a real measurement (gate 6 stays red while haft is `none`). **New pack** starts blank, including Look. The current pack autosaves in `localStorage`; New pack and Load sample ask before they wipe it.

Vercel can host `app/` (set the project Root Directory to `app`). `npm test` covers gate/validation helpers; `npm run build` typechecks and bundles.

## Layout

```
app/                client-side pack builder (Vite + React)
templates/          blank cards (copy these) — source of truth
docs/FRAMEWORK.md   why the pack looks like this
docs/IMAGE-STILLS.md still factory → clip factory (sheet vs plate, I2VA hop-1)
docs/HOW-TO.md      GitHub + local workflow, step by step
docs/SOURCES.md     citations
examples/           Sigils lessons (process only, no MP4s)
```

## Rules we will not bend

- Lyric numbers (45 cm / 600 g / 10 cm) go on a **prop card** before any browser call.
- “Research the axe” is treatment homework, not generate-time.
- One camera verb per window (type + amplitude + speed).
- Speech and chorus hits finish by **8.0 s** in a 10.125 s window. Hold only before `fadeblack`.
- `non_diegetic_music: N/A` + mute in the editor **or** a prompt score. Not both.
- Do not publish MiniMax-generated MP4s from this workflow.
- Do not publish likeness stills to this public tree. Private fork.

## License

MIT for this repo (templates, docs, and the client-side app). MiniMax H3 weights and outputs are a separate license.
