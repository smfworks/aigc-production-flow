# CLIP_BRIDGE_COMFY.md
## ComfyUI workflow stubs for the CLIP_BRIDGE application

Hand this folder to the builder with `CLIP_BRIDGE.md`.
These graphs are **API-format** payloads for `POST /prompt`.
They use official Comfy-Org `class_type` names. Do not invent nodes.

Official UI templates to import if you want the canvas versions:

- Qwen T2I: `templates/image_qwen_image_2_1_t2i.json`
- Qwen Edit: `templates/image_qwen_image_2_1_image_edit.json`
- H3 first+last (hosted API): `templates/api_minimax_h3_flf2v.json`

Hermes should mutate the API stubs in this folder, not the official UI graphs.

---

## Files

| File | CLIP_BRIDGE step | Job |
|---|---|---|
| `qwen_t2i_sheet.json` | Q1 | Character sheet from `story_lock` |
| `qwen_edit_start.json` | Q2 | START still from identity + previous last frame |
| `qwen_edit_end.json` | Q3 | END still from identity + this clip START |
| `h3_fl2va_api.json` | animate | Hosted MiniMax H3 FL2VA, 10s, 2K |
| `h3_fl2va_native.json` | animate | Local-GPU MiniMaxH3ImageToVideo FL2VA |

Prefer `h3_fl2va_api.json` for production 2K / 10.00s.
Use `h3_fl2va_native.json` only when running H3 weights on the local box.
Native H3 canvas is a 768 short-edge (1344×768 at 16:9) unless you upscale after.

---

## Models the Comfy box must have

```
ComfyUI/models/
  diffusion_models/qwen_image_2.1_int8_convrot.safetensors
  text_encoders/qwen3vl_8b_int8_convrot.safetensors
  vae/qwen_image_2.1_vae_bf16.safetensors
```

BF16 variants are fine if VRAM allows. Swap the loader filenames; do not change node types.

Hosted H3 API node needs a MiniMax key configured in Comfy. No local H3 weights required for `h3_fl2va_api.json`.

---

## Locked sampler / canvas

Qwen 2.1 (all three image graphs):

- steps `25`
- cfg `1`
- sampler `euler`
- scheduler `simple`
- denoise `1`
- canvas `2560×1440` (16:9, both sides ÷32)
- `TextEncodeQwenImage21.resolution = 0` on edit graphs so refs keep their own pixel size
- then `ImageScale` forces `story_lock.width × story_lock.height`

H3 API graph:

- node `MinimaxHailuo03FirstLastFrameNode`
- model `MiniMax H3`
- resolution `2K`
- duration `10`
- watermark `false`
- prompt_expansion `balanced`

H3 native graph:

- node `MiniMaxH3ImageToVideo`
- width `1344` height `768` (native 16:9) or `2560` / `1440` if the local build accepts it
- length `243` (nearest 17k+5 grid to 10s at 24fps → 10.125s)
- first_frame + last_frame both connected

---

## Injection map (what Hermes overwrites before POST)

Every stub uses stable node ids. Overwrite only these inputs.

### qwen_t2i_sheet.json
- `10.inputs.prompt` ← assembled Q1 + visual lock
- `10.inputs.negative_prompt` ← story_lock.negative
- `12.inputs.width` / `12.inputs.height` ← lock canvas
- `20.inputs.filename_prefix` ← `clipbridge/lock/character_sheet`
- `30.inputs.seed` ← project seed

### qwen_edit_start.json
- `1.inputs.image` ← character sheet filename in Comfy `input/`
- `2.inputs.image` ← previous `end_extracted.png` (clip 1: location plate)
- `3.inputs.image` ← optional location plate (leave empty string to skip)
- `10.inputs.prompt` ← assembled Q2
- `10.inputs.negative_prompt` ← story_lock.negative
- `10.inputs.resolution` ← `0`
- `12.inputs.width` / `12.inputs.height` ← lock canvas
- `20.inputs.filename_prefix` ← `clipbridge/{clip_id}/start`
- `30.inputs.seed` ← clip seed

### qwen_edit_end.json
- `1.inputs.image` ← character sheet
- `2.inputs.image` ← this clip `start.png`
- `3.inputs.image` ← optional location plate
- `10.inputs.prompt` ← assembled Q3
- `20.inputs.filename_prefix` ← `clipbridge/{clip_id}/end_designed`

### h3_fl2va_api.json
- `1.inputs.image` ← `start.png`
- `2.inputs.image` ← `end_designed.png`
- `10.inputs.prompt` ← assembled H0 wrapper
- `10.inputs.duration` ← `10`
- `10.inputs.resolution` ← `2K`
- `10.inputs.seed` ← clip seed
- `20.inputs.filename_prefix` ← `video/clipbridge/{clip_id}/clip`

### h3_fl2va_native.json
- `1` / `2` same as API graph
- `10.inputs.prompt` ← assembled H0 wrapper
- `10.inputs.width` / `height` / `length` ← `1344` / `768` / `243`
- `30.inputs.seed` ← clip seed

After each Qwen save, copy the PNG into the project folder as `clips/{id}/start.png` or `end_designed.png`.
After each H3 save, run the ffmpeg extract from CLIP_BRIDGE.md §12 onto `clips/{id}/end_extracted.png`.

---

## How Hermes calls Comfy

```
POST {COMFY}/prompt
Content-Type: application/json

{
  "prompt": { ...stub graph... },
  "client_id": "clip-bridge"
}
```

Then poll `{COMFY}/history/{prompt_id}` until the SaveImage / SaveVideo node reports a filename.
Copy that file into the CLIP_BRIDGE project tree. Do not leave continuity files only inside Comfy's output folder.

Upload stills the graph will LoadImage with:

```
POST {COMFY}/upload/image
```

Use the returned filename as `LoadImage.inputs.image`.

---

## Continuity rules that belong in the Comfy caller, not the graph

1. Before Q2/Q3, assert start and end refs are the same pixel size after `ImageScale`.
2. Do not run H3 if start.png and end_designed.png differ in width or height.
3. Never feed a newly imagined start still into clip N+1 when `end_extracted.png` exists.
4. Keep `TextEncodeQwenImage21.resolution = 0` on edit graphs.
5. Do not enable Qwen prompt-enhancer on production takes. It can drop `<image1>` tags and the lock text.

---

## Slot convention

| Slot | Meaning |
|---|---|
| `<image1>` / `images.image_1` | Character sheet. Identity lock. Never re-describe the face. |
| `<image2>` / `images.image_2` | Previous last frame (Q2) or this clip start (Q3) |
| `<image3>` / `images.image_3` | Location plate. Optional. |

---

## Out of scope in these stubs

- Last-frame extraction (ffmpeg, not Comfy)
- Concat / stitch (ffmpeg)
- Prompt assembly (CLIP_BRIDGE.md §14)
- Prompt enhancer nodes
- Background-remove template
- H3 Ref2VA identity rescue (add later if audit fails)
