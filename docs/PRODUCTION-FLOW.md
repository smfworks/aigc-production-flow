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

v1.5 (next, still this repo):

- **Entity schedule** — who/what must persist across which windows (papers: identity is grounding, not local continuation).[6][7][8]
- **Diff the lock** — same keywords every hop; rotating “brown”/“brunette” is a red gate
- **Preview receipt** — ffprobe + still-vs-lock + NG reason required before hop 2+
- **License/output policy** — public tree never takes likeness stills or engine MP4s

v2 (platform):

- visual identity store (approved sheet + per-window plates), not a pasted wardrobe paragraph
- review states: draft / needs-art / needs-edit / preview-watched / generate-ok
- async generate jobs with cancel/retry, one engine adapter at a time per GPU

**Phase 1 (this repo, studio spine):** review states and a local media store for sheet/plate metadata + files are delivered. Pack zip import/export creates `PackRevision` rows (pack.json + nine-gate snapshot). `generate-ok` is refused unless that snapshot is all green. Auth is a local-dev API token — not SSO. Async generate jobs stay deferred. Operator path: [STUDIO.md](STUDIO.md).

## Multi-user collaboration

v1 (now, honest): the pack **is** the collaboration object.

- Templates under `templates/` are the source of truth
- Export is a markdown zip in that shape — writers, art, and editors can pass the zip
- Public GitHub is process only. Private fork (or sibling private repo) holds likeness stills and unreleased music
- Roles on a pack (convention, not auth): **writer** (script + map), **art** (sheets/plates), **editor** (joins + verbs), **producer** (gates green / GPU spend)

Phase 1 (this repo): a **studio spine** holds projects / episodes, comments, review state, and a gitignored media directory. The zip is still the round-trip. Roles stay convention, not SSO. Do not treat `STUDIO_API_TOKEN` as multi-tenant isolation.

v2 leftover (build, do not pretend we have it):

| Role | Writes | Reviews |
|---|---|---|
| Writer | log line, map, dialogue finish-by | retention hooks, episode order |
| Art | sheets, plates, look | identity vs lock |
| Editor | takes, edit list, joins | one verb, fade vs cut |
| Producer | audio path, generate-ok | GPU budget, license |
| Reviewer | comments only | preview watch, NG reason |

Do not stand a multi-tenant SaaS until the zip round-trip and the four-stage gate order are boring.

## Engine adapters (H3 is one)

The flow does not name a model. Adapters do.

| Adapter | Job | Notes |
|---|---|---|
| **Still factory** | Sheets + plates | Measured: Qwen-Image-2.1 INT8 ConvRot, native 1344×768 |
| **Clip factory (default)** | Hop-1 I2VA / T2V + motion-context extend | Measured: Comfy native MiniMax H3 on spark-56bc |
| Future clip adapters | Same joins, same plates, declare window length | Cloud Hailuo / Veo / Kling / etc. only after a hop-1 watch protocol exists |

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
3. Export still requires nine green gates.
4. A pack zip round-trips without a GPU.
5. GPU spend still happens somewhere else, after preview.
6. Studio `generate-ok` is refused unless the stored nine-gate snapshot is green.

## Sources

See [SOURCES.md](SOURCES.md) (15–16 are the 2026 production-flow pass).
