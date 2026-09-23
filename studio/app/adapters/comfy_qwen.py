"""Qwen-Image still factory on a local ComfyUI lane.

Returns a file path. PNG bytes go to the media store, not into the job receipt.
"""

from __future__ import annotations

import re
import secrets
import time
from pathlib import Path
from typing import Any

from ..config import Settings
from .base import AdapterResult, JobContext
from .comfy_client import STILL_PREFIX, ComfyClient, ComfyError, comfy_out_dir

# Sizes checked on the Qwen-Image graph, plus Studio's measured pack canvas.
SIZES: dict[str, tuple[int, int]] = {
    "square": (1328, 1328),
    "landscape": (1664, 928),
    "portrait": (928, 1664),
    "studio": (1344, 768),
    "pack": (1344, 768),
}

_REFERENCE = re.compile(r"reference:\s*(\S+)", re.IGNORECASE)


def graph_files(settings: Settings) -> dict[str, str]:
    return {
        "unet": settings.comfy_qwen_unet,
        "clip": settings.comfy_qwen_clip,
        "vae": settings.comfy_qwen_vae,
    }


def build_qwen_graph(
    prompt: str,
    width: int,
    height: int,
    seed: int,
    files: dict[str, str],
) -> dict[str, Any]:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": files["unet"], "weight_dtype": "default"},
        },
        "2": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": 3.1},
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": files["clip"], "type": "qwen_image", "device": "default"},
        },
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": prompt}},
        "5": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": files["vae"]}},
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["2", 0],
                "positive": ["4", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0],
                "seed": seed,
                "steps": 20,
                "cfg": 2.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["6", 0]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": STILL_PREFIX},
        },
    }


def resolve_size(payload: dict[str, Any]) -> tuple[str, int, int]:
    raw = str(payload.get("size") or payload.get("canvas") or "studio").strip().lower()
    raw = raw.replace("×", "x").replace(" ", "")
    if raw in SIZES:
        width, height = SIZES[raw]
        return raw, width, height
    for name, (width, height) in SIZES.items():
        if raw in {f"{width}x{height}", f"{width}×{height}"}:
            return name, width, height
    known = ", ".join(f"{name} ({w}x{h})" for name, (w, h) in SIZES.items())
    raise ComfyError(f"size must be one of: {known}")


def reference_paths(prompt: str) -> list[str]:
    """Edit convention: `reference: <path>` inside the prompt. Paths only, never pixels."""
    found: list[str] = []
    for match in _REFERENCE.findall(prompt):
        path = match.strip().strip("'\"")
        if path and path not in found:
            found.append(path)
        if len(found) >= 10:
            break
    return found


def _prompt_text(payload: dict[str, Any]) -> str:
    for key in ("prompt", "text", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _stamped_png() -> str:
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    return f"{STILL_PREFIX}_{stamp}_{secrets.token_hex(3)}.png"


def _fail(message: str, *, busy: bool = False) -> AdapterResult:
    return AdapterResult(
        ok=False,
        adapter="comfy-qwen",
        error=message,
        receipt={
            "adapter": "comfy-qwen",
            "engine": "comfyui-qwen-image",
            "called_comfy": False,
            "busy": busy,
            "hop1_watch_required": True,
            "claim": "ComfyUI was not asked to render. No still file was saved.",
        },
    )


def generate_still(settings: Settings, ctx: JobContext, *, role: str) -> AdapterResult:
    if ctx.cancel_requested():
        return AdapterResult(ok=False, adapter="comfy-qwen", error="cancelled")
    payload = ctx.payload if isinstance(ctx.payload, dict) else {}
    prompt = _prompt_text(payload)
    if not prompt:
        return _fail("prompt must be a non-empty string")
    if len(prompt) > 100_000:
        return _fail("prompt is too long")
    workflow_id = str(payload.get("workflow_id") or "").strip()
    if workflow_id:
        from ..clipbridge_workflows import role_registry_refusal

        refusal = role_registry_refusal(workflow_id)
        if refusal:
            return _fail(refusal)
    try:
        size_name, width, height = resolve_size(payload)
    except ComfyError as exc:
        return _fail(str(exc))

    client = ComfyClient(settings)
    try:
        from .comfy_client import lanes_for_slot

        lane = client.pick_lane(lanes_for_slot(settings, "comfy-qwen"))
    except ComfyError as exc:
        return _fail(str(exc), busy=exc.busy)

    seed = secrets.randbits(32)
    if workflow_id:
        from ..workflows import filled_graph

        try:
            graph = filled_graph(workflow_id, ctx.payload if isinstance(ctx.payload, dict) else {})
        except Exception as exc:  # noqa: BLE001 — name the cause; do not submit
            detail = getattr(exc, "detail", None)
            message = detail if isinstance(detail, str) else str(exc)
            return _fail(message or f"Role-tagged workflow {workflow_id} could not be filled.")
    else:
        graph = build_qwen_graph(prompt, width, height, seed, graph_files(settings))
    ctx.set_progress(15)
    try:
        prompt_id = client.submit_prompt(lane, graph, "smf-aigc-studio")
    except ComfyError as exc:
        return _fail(str(exc))

    ctx.set_progress(30)
    deadline = time.monotonic() + float(settings.comfy_still_timeout_seconds or 300)
    poll = max(0.0, float(settings.comfy_still_poll_seconds or 0))
    output: dict[str, Any] | None = None
    while True:
        if ctx.cancel_requested():
            return AdapterResult(ok=False, adapter="comfy-qwen", error="cancelled")
        try:
            entry = client.history_entry(lane, prompt_id)
            output = client.output_file(entry, prompt_id)
        except ComfyError as exc:
            return AdapterResult(
                ok=False,
                adapter="comfy-qwen",
                error=str(exc),
                receipt=_running_receipt(lane, prompt_id, size_name, width, height, called=True),
            )
        if output:
            break
        if time.monotonic() >= deadline:
            return AdapterResult(
                ok=False,
                adapter="comfy-qwen",
                error=(
                    f"ComfyUI job {prompt_id} did not finish within "
                    f"{int(settings.comfy_still_timeout_seconds or 300)}s"
                ),
                receipt=_running_receipt(lane, prompt_id, size_name, width, height, called=True),
            )
        ctx.set_progress(60)
        time.sleep(poll if poll > 0 else 0.05)

    try:
        data = client.download_output(lane, output)
    except ComfyError as exc:
        return AdapterResult(
            ok=False,
            adapter="comfy-qwen",
            error=str(exc),
            receipt=_running_receipt(lane, prompt_id, size_name, width, height, called=True),
        )
    filename = _stamped_png()
    path = _write(settings, filename, data)
    kb = max(1, round(len(data) / 1024))
    refs = reference_paths(prompt)
    description = f"{path} — {width}x{height} PNG saved ({kb} KB)."
    receipt: dict[str, Any] = {
        "adapter": "comfy-qwen",
        "engine": "comfyui-qwen-image",
        "called_comfy": True,
        "role": role,
        "path": str(path),
        "description": description,
        "width": width,
        "height": height,
        "size": size_name,
        "canvas": f"{width}x{height}",
        "lane": lane,
        "comfy_prompt_id": prompt_id,
        "filename_prefix": STILL_PREFIX,
        "hop1_watch_required": True,
        "bytes": len(data),
    }
    if refs:
        receipt["references"] = refs
        receipt["edit_note"] = (
            "Reference paths stay text on this receipt. "
            "The published still graph is text-to-image; pixels are not inlined."
        )
    ctx.set_progress(95)
    kind = "plate" if role == "plate" else "sheet"
    return AdapterResult(
        ok=True,
        adapter="comfy-qwen",
        receipt=receipt,
        media_bytes=data,
        media_name=filename,
        media_kind=kind,
        content_type="image/png",
    )


def _running_receipt(
    lane: str,
    prompt_id: str,
    size_name: str,
    width: int,
    height: int,
    *,
    called: bool,
) -> dict[str, Any]:
    return {
        "adapter": "comfy-qwen",
        "engine": "comfyui-qwen-image",
        "called_comfy": called,
        "lane": lane,
        "comfy_prompt_id": prompt_id,
        "size": size_name,
        "canvas": f"{width}x{height}",
        "hop1_watch_required": True,
    }


def _write(settings: Settings, filename: str, data: bytes) -> Path:
    directory = comfy_out_dir(settings)
    path = directory / filename
    path.write_bytes(data)
    return path


class ComfyQwenStillFactory:
    name = "comfy-qwen"

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_sheet(self, ctx: JobContext) -> AdapterResult:
        return generate_still(self.settings, ctx, role="sheet")

    def generate_plate(self, ctx: JobContext) -> AdapterResult:
        return generate_still(self.settings, ctx, role="plate")
