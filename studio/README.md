# AIGC studio API (Phase 16)

FastAPI spine. Quick create is the Create screen: `POST /api/quick/plan` builds a local shot list (no spend), `POST /api/quick/run` with `confirm: true` saves a project, episode, and pack on the local desk (jobs permission, 409 without confirm). `GET /api/quick/{run_id}` reads that episode. `called_comfy` stays false. `produced_mp4` stays false. Gates and generate-ok are unchanged. Stills and clips use stub, or Comfy on a private lane. Studio does not call a cloud image or video API.

The longer front door is still the Create wizard (`POST /api/create/wizard`, patch answers, `POST …/finish`). Scope, a prunable task tree, craft-lane labels, and director checkpoints are part of that door. Local recipes are `POST /api/create/recipes` and `recipe_id` on start. **Send to Hermes** (`POST /api/create/wizard/{id}/handoff/hermes`) writes a brief under the handoff root and returns a `hermes://` payload. It does not invoke Hermes or call Comfy. `GET /api/agent-runs/{id}` polls sheets, plates, hop-1 clips, and stitch. Disabled tree branches are skipped. Stitch does not invent an MP4.

`POST /api/studio/start` (blank, template, or brain dump) stays. Edit with `POST /api/episodes/{id}/pack/json`. Export an agent zip (`GET /api/episodes/{id}/export/agent`) lists still jobs, then hop-1 clips, then stitch, and does not call Comfy. Brain dump uses a deterministic template unless `STUDIO_LLM_BASE_URL` is set.

Native ComfyUI: set `STUDIO_COMFY_STILL_LANES` (Qwen-Image) and `STUDIO_COMFY_CLIP_LANES` (MiniMax H3) to private URLs. Empty lanes stay stub / not live. Example names: `comfy.example.json`. MIT notice: [../NOTICE](../NOTICE).

Phase 16 Comfy stubs, same desk. `docs/CLIP_BRIDGE_COMFY.md` is the widget guide. The API graphs are `studio/fixtures/clip_bridge/workflows/` (`resize_lock`, `qwen_t2i_sheet`, `qwen_edit_start`, `qwen_edit_end`, `h3_fl2va_api`, `h3_fl2va_native`). `GET /api/clip-bridge/workflows` lists inject paths and locked widgets. `POST …/inject` fills `_clip_bridge.inject` on a copy and does not queue. Prefer `h3_fl2va_api` for 2K / 10s. Qwen stays steps 25, cfg 1, euler, simple. Edit slots are `images.image_1` in the API JSON and `<image1>` in the prompt. Extract and stitch stay on ffmpeg. A stub file is not an MP4.

Phase 15 clip bridge, same desk. `docs/CLIP_BRIDGE.md` is the only H3 continuity dialect.

- **Story lock and clips.** `PUT /api/episodes/{id}/clip-bridge` stores `story_lock` on the episode and one bridge object on each shot. `POST …/clip-bridge/fixture` with `{"name":"forge_dawn"}` loads the 6-clip bladesmith chain. `POST …/copy-handoff` copies `end_state` into the next `start_state` with `strip()` only. `POST …/retry` reassembles one clip's prompts and does not rewrite the lock or earlier states.
- **Prompt preview.** A bridge shot's Generate preview shows `assemble_h3_prompt` for hop-1 and the Qwen Q2/Q3 strings for stills. The alignment line is the line in `CLIP_BRIDGE.md`. Rewrite stays off so a second H3 profile cannot replace it. Continuity failures return `clip_bridge_rejected` and do not enqueue.
- **Conform.** `POST …/clip-bridge/conform` returns the ffmpeg extract, trim (`end_frame=239`), and concat commands. `execute: true` runs them only when every clip video exists. Otherwise `produced_mp4` stays false. `studio/scripts/clip_bridge_conform.sh` does the same and exits without writing a stand-in file.

Phase 14 machine shop, still under the director desk:

- **Role-tagged workflows.** `GET/POST /api/workflows` registers Comfy API-format JSON. Editable nodes are discovered from titles such as `Prompt (Input:prompt)` and `Clip (Output:video)`. Canonical roles: prompt, negative, width, height, character, location, image, video, audio, seed, duration (aliases such as `identity` → character). Node ids are not the contract. Builtins: `studio/fixtures/workflows/character-sheet.json` (H3 6-section profile) and `h3-extend.json` (video input). `STUDIO_WORKFLOW_ROOT` overrides the import directory. Import does not call Comfy.
- **Prompt preview.** `POST /api/jobs/preview` shows the exact prompt, negative, and reference roles before a still or clip job. Patch, `…/rewrite` (only when the workflow title includes `(Profile:h3)`), or `…/cancel`. `POST /api/jobs` with `payload.preview_id` queues that draft. With `STUDIO_REQUIRE_PROMPT_PREVIEW` left on (the default), a still or clip enqueue without a preview returns 409 `preview_required`. Tests set the flag false so older callers keep working. A stub result is `outcome: fixture` and `called_comfy: false`.
- **Shot coverage.** `POST /api/episodes/{id}/coverage` breaks a scene into clips of about 5–10 seconds and stores them on the edit list / board. `coverage.rendered` stays false. No MP4 is written.
- **Continue-from-previous.** Set `continue_from` to `previous` or a shot id. Generate stays off, with a named warning, unless the selected workflow has `(Input:video)`. A fixture JSON receipt is not a video file. A live lane is not sent one.
- **Clarify-before-run.** `GET /api/create/wizard/{id}/clarify`. Finish returns 409 `clarify_required` when audience, deliverables, cast refs, or negative constraints are missing. `?acknowledge_gaps=true` records the gaps and continues. This is not a gate checkpoint.
- **Reference roles** on media: `identity-lock`, `motion`, `environment`, `audio`. They show up on the prompt preview. They are instructions, not receipts.

Dry-run (`POST /api/adapters/{id}/dry-run`) says it did not enqueue. An unreachable live adapter names the cause and does not look like success.

Also: ordered episodes, pack revision diff, review sign-off, identity store, media, shots, jobs, adapters, hop-1 preview desk, playlist scrubber, budget, audit, retention, EDL, vertical templates, org members, presence, multi-org lite, notifications, continuity, demo seed, backup, and optional builder handoff. Optional Celery. Optional OIDC.

Operator docs: [../docs/STUDIO.md](../docs/STUDIO.md). Auth: [../docs/AUTH.md](../docs/AUTH.md).

```bash
# from repo root
./scripts/dev-studio.sh api      # HTTP + in-process job worker (default)
./scripts/dev-studio.sh worker   # optional standalone thread poller (API should set STUDIO_JOB_WORKER=off)
./scripts/dev-studio.sh celery   # optional Celery worker (STUDIO_CELERY_BROKER_URL + STUDIO_JOB_WORKER=celery on the API)
docker compose -f docker-compose.studio.yml up --build
```

OpenAPI: http://localhost:8000/docs

Auth is **local-dev** (`Authorization: Bearer $STUDIO_API_TOKEN`) plus optional `STUDIO_AUTH_MODE=forward-header` or `oidc`, and **app-level** org roles. Multi-org lite is membership isolation (`X-Org-Id`), not SaaS billing. OIDC is opt-in and off by default. This is not a production IdP.

Default adapter is `stub`. It writes fixture receipts and never claims H3 or Qwen ran. Budget units are an operator rate table, not a cloud invoice. Media is local disk unless S3/MinIO is configured. Default job worker is `thread`. Celery is opt-in.
