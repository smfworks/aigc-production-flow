# Hermes handoff contract

Studio writes this. Hermes is not started by Studio. Comfy is not called by the handoff. A file on disk is not proof that either one ran.

Companion pane: [smf-aigc-studio-pane](https://github.com/smfworks/smf-aigc-studio-pane). This repo is the contract. The pane can watch the drop folder. It does not need a Studio change to read the latest brief.

## Where to look

| Path | What it is |
|---|---|
| `data/handoff/latest.json` | Pointer to the newest brief. This is the file to watch. |
| `data/handoff/latest/` | Copy of that brief (stable path). |
| `data/handoff/<agent_run_id>/` | Immutable drop for one send. |

`STUDIO_HANDOFF_ROOT` overrides the directory. Default is the sibling of the media root (`./data/handoff` when media is `./data/media`).

`STUDIO_HERMES_DROP` (optional, empty by default) mirrors the same files, for example `~/.hermes/aigc`. Unset means Studio does not write outside the handoff root.

## latest.json

```json
{
  "agent_run_id": "<uuid>",
  "drop_dir": "<absolute path>",
  "deep_link": "hermes://aigc/brief?run=<uuid>",
  "open": "hermes-handoff.json",
  "called_comfy": false,
  "hermes_ran": false,
  "produced_mp4": false
}
```

`called_comfy` and `hermes_ran` are false when Studio writes the file. Do not flip them true because the file exists.

## Deep link

`hermes://aigc/brief?run=<agent_run_id>`

Open that run's folder, or resolve it through `latest.json` when the query is the latest id.

## Bundle

- `hermes-handoff.json` — copyable payload (`kind: aigc-hermes-handoff`)
- `agent-brief.json` — ordered jobs: still sheets, still plates, hop-1 clips, **stitch**
- `pack.json` — capture pack snapshot
- `gate-snapshot.json` — gates at send time
- `playlist.json` — shot playlist
- `edit.edl` — EDL lite
- `README.md` — order and honesty

`agent-brief.json` → `honesty.called_comfy` is false. Adapter labels say stub or live. Unset `STUDIO_COMFY_STILL_LANES` / `STUDIO_COMFY_CLIP_LANES` means the measured slots are **not live**. Use stub receipts, or refuse a live generate. Do not tell anyone Qwen or H3 ran.

## Stitch

The last job is `kind: stitch`. Concat the playlist in order.

- Concat only local video files that exist.
- If the inputs are fixture JSON receipts, leave the run **awaiting stitch**.
- Do not invent an MP4.
- Studio's own stitch job uses local ffmpeg only when every playlist row is a real video file. Otherwise it writes a plan and `produced_mp4: false`.

## Pane behavior that satisfies this contract

1. Watch `latest.json` (or `STUDIO_HANDOFF_ROOT/latest.json`).
2. Offer **Open latest brief**. Read `hermes-handoff.json` and `agent-brief.json` from `drop_dir`.
3. Accept `hermes://aigc/brief?run=`.
4. Show stub vs live from the brief. Do not show a finished film unless `produced_mp4` is true and the file is on disk.

No Studio endpoint posts to X or starts Hermes.

## Director front door (Phase 13)

Create can show a prunable task tree (script/beats → identity sheets → plates → hop-1 → stitch → review gates), four craft-lane labels (Writer, Art, Picture, Sound), director checkpoints, and optional scope (must-nots, platform formats, claim bans).

- The tree is a plan. Disabling a branch skips that brief job. It does not call Comfy or start Hermes.
- `director.craft_lanes` in `agent-brief.json` are routing labels. `director.agents_ran` stays false.
- Checkpoints repeat the real gates (log line through lock-diff, plus draft identities, missing plates, unwatched hop-1, and missing sign-off). They do not turn gates green.
- Scope is copied into pack notes and `director.scope`.
- Saved Create recipes are local JSON under `data/recipes/` (`skill_<name>_v0.1.json`, or `STUDIO_RECIPE_ROOT`). They prefill the wizard. There is no plaza.

## Machine shop (Phase 14)

Role-tagged Comfy workflows, prompt preview, shot coverage, and continue-from-previous live under the same desk.

- A workflow file is not a render. `called_comfy` stays false until a live lane accepts a prompt.
- Prompt preview does not enqueue. Stub and dry-run stay labeled. Do not treat a fixture receipt as an MP4.
- Coverage clips are a plan on the board (`rendered: false`). They do not invent video.
- Continue-from-previous requires an `(Input:video)` role. A missing role disables Generate and names why.
- Clarify-before-run asks for missing brief fields. It does not turn gates green.
- Brief is that structured pause. Cut is the existing sign-off. Prompt prose is not permission to generate.
- A stitch file does not mark the episode completed and does not stamp generate-ok. Hermes stays the handoff, not a second runtime.
