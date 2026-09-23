# CLIP_BRIDGE Comfy stubs

API-format graphs for `POST /prompt`. `_clip_bridge` on each file is the inject contract. The bytes are the official pack. A file here is not a render.

Studio reads them from this directory so the Phase 14 role-tag folder (`studio/fixtures/workflows/`) stays title-addressed. `docs/CLIP_BRIDGE.md` §20 names the pack layout `comfy/` next to the spec. Same files.

Prefer `h3_fl2va_api.json` for production 2K / 10s. `h3_fl2va_native.json` is the local-GPU graph (1344×768, length 243 ≈ 10.125s).

Writable paths are each file's `_clip_bridge.inject` list. Locked sampler widgets stay on the nodes: Qwen steps 25, cfg 1, euler, simple; H3 API duration 10 and resolution 2K. Edit refs are `images.image_1` (and so on). Prompt text still uses `<image1>`.

Extract and stitch stay on ffmpeg (`studio/scripts/clip_bridge_conform.sh`, `docs/CLIP_BRIDGE.md` §12). They are not nodes in these graphs.

If a stub fails to queue on ComfyUI, import the official template and patch widgets only:

- Qwen T2I: `templates/image_qwen_image_2_1_t2i.json`
- Qwen Edit: `templates/image_qwen_image_2_1_image_edit.json`
- H3 FLF2V: `templates/api_minimax_h3_flf2v.json`

Guide: `docs/CLIP_BRIDGE_COMFY.md`. Filling a graph here does not call Comfy.
