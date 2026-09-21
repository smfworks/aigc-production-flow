# Third-party software

AIGC Studio's live still and clip engines are an SMF Works reimplementation for
this repo's Python job runner. They follow the behavior of two MIT-licensed
community tools by tonyd2wild. The copyright and license text live in
[NOTICE](NOTICE). We do not vendor those repositories.

| Upstream | Copyright | What Studio kept |
|---|---|---|
| [DeepSeek-Harness-Image-Tools](https://github.com/tonyd2wild/DeepSeek-Harness-Image-Tools) | Copyright (c) 2026 tonyd2wild, MIT | Qwen-Image via ComfyUI: free-lane pick, `/prompt`, poll `/history`, download `/view`, path text instead of pixels, size presets |
| [DeepSeek-Harness-Video-Tools](https://github.com/tonyd2wild/DeepSeek-Harness-Video-Tools) | Copyright (c) 2026 tonyd2wild, MIT | MiniMax H3 via ComfyUI: async job id + ETA, `images` output key, 17n+5 frame grid, SigmaShift only on turbo, `POST /free` for a sibling still lane |

These projects describe themselves as unofficial and not endorsed by DeepSeek.
Studio does not claim that endorsement. Studio does not own MiniMax, Qwen, or
ComfyUI. Product surfaces say SMF Works, AIGC Studio, ComfyUI, Qwen-Image, and
MiniMax H3.

Checkpoint file names in `studio/comfy.example.json` are overridable examples.
Lane URLs are not hardcoded. Leave the lane env vars empty and Studio stays on
the stub adapter.
