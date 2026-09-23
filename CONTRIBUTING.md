# Contributing

Phase 15 is the CLIP_BRIDGE continuity bridge on the Phase 14 prompt preview. `docs/CLIP_BRIDGE.md` is the dialect. Fill its slots. Do not paraphrase locked continuity strings, and do not add a second H3 wrapper. Phase 14 is the Comfy / H3 machine shop under the Phase 13 director desk. Patterns are reimplemented here. Do not paste third-party graphs or agent trees into this repo.

## Role-tagged workflows

New Comfy paths are API-format JSON addressed by node **titles**, not node ids. The measured Qwen and H3 builders stay for the lanes that already ship. They run only when a job does not name a registered workflow.

Title a node like this:

```text
Positive (Input:prompt) (Profile:h3)
Char Ref (Input:character)
Previous clip (Input:video)
Clip (Output:video)
```

`(Input:role)` and `(Output:role)` are the contract. `(Profile:h3)` (also `h3-6`, `h3_6`, `minimax-h3`) asks the prompt rewrite for the six-section H3 profile. That rewrite is structured text. It does not call a model.

Canonical roles: `prompt`, `negative`, `width`, `height`, `character`, `location`, `image`, `video`, `audio`, `seed`, `duration`.

Aliases fold in: `positive` / `text` → prompt, `identity` → character, `env` / `environment` → location, `clip` → video, `sound` → audio, `seconds` / `length` → duration. An unknown role is kept and left unmapped.

Fill copies the graph and writes values into the discovered nodes. Multiple image-like roles fill in node-id order. Width and height are separate nodes; filling one does not clobber the other.

Register with `POST /api/workflows` or drop a file under `studio/fixtures/workflows/` (builtins) or `STUDIO_WORKFLOW_ROOT` (default `data/workflows`, beside the media root). The id is the filename stem: `^[a-z0-9][a-z0-9-]{0,60}$`. Import does not call Comfy.

Fixtures (small, not vendored production graphs):

- `studio/fixtures/workflows/character-sheet.json` — still sheet with an H3 profile tag
- `studio/fixtures/workflows/h3-extend.json` — clip extend with `(Input:video)`

A graph with no role tags is refused. Do not add a new path that hardcodes node ids.

## Prompt preview

`POST /api/jobs/preview` builds the exact prompt, negative, and reference list for `still-sheet`, `still-plate`, `clip-hop1`, and `clip-extend`. It does not enqueue.

- Patch edits the draft.
- `…/rewrite` runs only when the selected workflow asks for the H3 profile. Otherwise it returns 409 `profile_not_requested`.
- `…/cancel` drops the draft.
- `POST /api/jobs` with `payload.preview_id` queues that draft.

`STUDIO_REQUIRE_PROMPT_PREVIEW` defaults to on. A still or clip enqueue without a preview returns 409 `preview_required`. Tests set the flag false so older callers keep working. Batch precheck and stitch do not use a preview.

The draft is marked enqueued only after the job row is flushed. A later 409 does not burn it.

## Continue from the previous clip

`continue_from` may be `previous`, `timeline`, `auto`, or a shot id. Generate stays off, with a named warning, unless:

- a workflow is selected, and
- that workflow has an `(Input:video)` role, and
- a previous clip exists.

The hardcoded H3 graph has no role tags, so continue on it is refused. If the previous row is a fixture JSON receipt, a stub job may still enqueue and the warning says no latent was loaded. A live lane is not sent a continue without a real video file. That refusal happens before submit, and `called_comfy` stays false.

## Shot coverage

`POST /api/episodes/{id}/coverage` splits a scene into clips of about 5–10 seconds (default target 8). Dialogue lines and action sentences are allocated across those clips. A scene shorter than 5 seconds stays one short clip.

The plan is written onto the edit list and the board. `coverage.rendered` stays false. Replacing the board is refused with 409 `coverage_would_drop_receipts` when a shot already has a continuity receipt. Coverage does not write an MP4.

## Clarify before the crew lanes

Create asks for audience, deliverables, cast notes, and a negative constraint (must-nots, claim bans, or the negative field). Finish returns 409 `clarify_required` while any of those are empty. `?acknowledge_gaps=true` records those content gaps and continues. `@Name` in the prompt binds to a cast identity only when that name is already a slot, and to a sheet or plate on a job preview only when that asset exists. An unmatched mention stays a question. Acknowledging content gaps does not bind it and does not create an asset.

Still and clip lanes stay in ask mode until `engine_mode` is `approve`. The engines step records that approval. Approving does not call Comfy, and unset lanes stay stub. Lane approval is not skipped by acknowledging content gaps.

The same check blocks Hermes handoff until the gaps are answered or acknowledged and the lanes are approved.

This pause is not a gate. It does not turn checkpoints green.

Reference roles on an upload are `identity-lock`, `motion`, `environment`, or `audio`. The preview maps them to character, video, location, and audio. They are labels, not receipts.

## Honesty

Stub receipts say `stub: true`, `live: false`, `called_comfy: false`, `outcome: fixture`. Dry-run text says it did not enqueue. An unreachable live adapter names the cause. Hermes handoff still writes `called_comfy`, `hermes_ran`, and `produced_mp4` as false. Stitch concats only local video files that exist. A concat file sets `episode_completed` and `generate_ok` to false. The agent run status is `stitched`, not a completed episode. Hermes keeps the handoff. Studio does not replace it with another agent runtime.

Brief and Cut are labels on gates that already exist. Brief is the structured intake pause (audience, deliverables, cast, negative constraints). Cut is reviewer or producer sign-off. Prompt prose does not clear either one. Handoff still writes a brief while Cut is open, and that drop says `cut_cleared: false`.

## Deferred

Not in this slice:

- Build Scene Three.js composer
- Electron shell
- Plaza marketplace and MiniMax branding
- Global reroll UX
- Feishu / WeChat remote tasking
- A Calliope-style agent chat rewrite of Hermes
