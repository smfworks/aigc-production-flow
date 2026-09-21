"""MiniMax H3 clip factory on a local ComfyUI lane.

Enqueue returns a Studio job id and an ETA without waiting for the render.
A later poll reads history `images` (not `video`) and stores an mp4 path.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..config import Settings
from .base import AdapterResult, JobContext
from .catalog import H3_FPS, H3_FRAMES, H3_WINDOW_S
from .comfy_client import CLIP_PREFIX, VIDEO_CLIENT_ID, ComfyClient, ComfyError, comfy_out_dir, parse_lane_list

# Piecewise ETA from measured frame counts. Rough, not a bill.
_ETA_POINTS = ((90, 174), (124, 360), (192, 720), (362, 9000))
TURBO_SHIFT_VIDEO = 12.0
TURBO_SHIFT_AUDIO = 3.0
_NEGATIVE = (
    "low quality, blurry, distorted, watermark, on-screen text, people, "
    "soft focus, grain, halation, glow, haze, dreamy"
)


def eta_seconds(frames: int) -> int:
    if frames <= _ETA_POINTS[0][0]:
        return round(174 * frames / 90)
    for index in range(1, len(_ETA_POINTS)):
        frames_0, seconds_0 = _ETA_POINTS[index - 1]
        frames_1, seconds_1 = _ETA_POINTS[index]
        if frames <= frames_1:
            span = frames_1 - frames_0
            return round(seconds_0 + (seconds_1 - seconds_0) * (frames - frames_0) / span)
    return 9000


def fmt_duration(seconds: int) -> str:
    if seconds < 90:
        tenths = round(seconds / 6) / 10
        return f"about {tenths:.1f} min"
    if seconds < 3600:
        return f"about {round(seconds / 60)} min"
    tenths = round(seconds / 360) / 10
    return f"about {tenths:.1f} h"


def snap_frames(raw: int, max_frames: int) -> int:
    """Largest 17n+5 frame count that is not above `raw`, and not above the cap."""
    capped = min(max(raw, 1), max_frames)
    snapped = max(5, ((capped - 5) // 17) * 17 + 5)
    if snapped > max_frames:
        snapped = max(5, ((max_frames - 5) // 17) * 17 + 5)
    return snapped


def resolve_frames(payload: dict[str, Any], *, fps: float, max_frames: int) -> dict[str, Any]:
    """Default hop-1 is the measured 10.125s / 243f window. Other lengths snap down."""
    if payload.get("frames") not in {None, ""}:
        try:
            raw = int(payload.get("frames"))
        except (TypeError, ValueError) as exc:
            raise ComfyError("frames must be an integer") from exc
        if raw > max_frames:
            raise ComfyError(
                f"Requested {raw} frames exceeds the trained maximum of {max_frames} "
                f"(~{max_frames / fps:.1f}s). Split-and-stitch is not supported."
            )
        if raw < 1:
            raise ComfyError("frames must be at least 1")
        snapped = snap_frames(raw, max_frames)
        return {"frames": snapped, "raw": raw}
    seconds = payload.get("seconds", payload.get("duration_s"))
    if seconds in {None, ""}:
        seconds = H3_WINDOW_S
    try:
        sec = float(seconds)
    except (TypeError, ValueError) as exc:
        raise ComfyError("seconds must be a number") from exc
    if sec <= 0:
        raise ComfyError("seconds must be > 0")
    raw = max(1, int(sec * fps + 1e-9))
    if raw > max_frames:
        raise ComfyError(
            f"Requested {sec:g}s exceeds the trained maximum of {max_frames / fps:.1f}s "
            f"({max_frames} frames). Split-and-stitch is not supported."
        )
    snapped = snap_frames(raw, max_frames)
    return {"frames": snapped, "raw": raw}


def normalize_quality(value: Any) -> str:
    raw = str(value or "full").strip().lower()
    if raw in {"fast", "turbo"}:
        return "fast"
    if raw in {"", "full"}:
        return "full"
    raise ComfyError('quality must be "full" or "fast" (turbo is an alias of fast)')


def style_table(settings: Settings) -> dict[str, dict[str, str]]:
    raw = (settings.comfy_h3_styles or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ComfyError("STUDIO_COMFY_H3_STYLES must be a JSON object") from exc
    if not isinstance(data, dict):
        raise ComfyError("STUDIO_COMFY_H3_STYLES must be a JSON object")
    table: dict[str, dict[str, str]] = {}
    for name, spec in data.items():
        key = str(name).strip()
        if not key or key == "none":
            continue
        if not isinstance(spec, dict):
            raise ComfyError(f"style {key} must be an object with file and trigger")
        file_name = str(spec.get("file") or "").strip()
        trigger = str(spec.get("trigger") or "").strip()
        if not file_name:
            raise ComfyError(f"style {key} needs a file name")
        table[key] = {"file": file_name, "trigger": trigger}
    return table


def h3_files(settings: Settings) -> dict[str, str]:
    return {
        "unet_full": settings.comfy_h3_unet_full,
        "unet_turbo": settings.comfy_h3_unet_turbo,
        "clip": settings.comfy_h3_clip,
        "video_vae": settings.comfy_h3_video_vae,
        "audio_vae": settings.comfy_h3_audio_vae,
    }


def build_h3_graph(
    *,
    prompt: str,
    negative: str,
    frames: int,
    width: int,
    height: int,
    seed: int,
    quality: str,
    style: dict[str, str] | None,
    files: dict[str, str],
    fps: float,
    first_frame_b64: str | None = None,
) -> dict[str, Any]:
    """Full quality has no SigmaShift node. Fast/turbo adds 12.0 / 3.0 only."""
    turbo = quality == "fast"
    unet = files["unet_turbo"] if turbo else files["unet_full"]
    steps = 8 if turbo else 20
    graph: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": unet, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": files["clip"], "type": "minimax", "device": "default"},
        },
        "4": {
            "class_type": "EmptyMiniMaxH3LatentAV",
            "inputs": {"width": width, "height": height, "length": frames, "batch_size": 1},
        },
        "5": {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["8", 0],
                "prompt": prompt,
                "width": width,
                "height": height,
                "length": frames,
            },
        },
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative}},
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["5", 1],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": files["video_vae"]}},
        "9": {"class_type": "VAELoader", "inputs": {"vae_name": files["audio_vae"]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["8", 0]}},
        "11": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["7", 0], "vae": ["9", 0]}},
        "12": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["10", 0], "fps": fps, "audio": ["11", 0]},
        },
        "13": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["12", 0],
                "filename_prefix": f"video/{CLIP_PREFIX}",
                "format": "mp4",
                "codec": "h264",
            },
        },
    }
    model_ref: list[Any] = ["1", 0]
    if turbo:
        graph["3"] = {
            "class_type": "MiniMaxH3SigmaShift",
            "inputs": {
                "model": ["1", 0],
                "shift_video": TURBO_SHIFT_VIDEO,
                "shift_audio": TURBO_SHIFT_AUDIO,
            },
        }
        model_ref = ["3", 0]
    if style:
        graph["14"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"model": model_ref, "lora_name": style["file"], "strength_model": 1.0},
        }
        graph["7"]["inputs"]["model"] = ["14", 0]
    else:
        graph["7"]["inputs"]["model"] = model_ref
    if first_frame_b64:
        graph["20"] = {"class_type": "LoadImageFromBase64", "inputs": {"image": first_frame_b64}}
        graph["5"]["inputs"]["first_frame"] = ["20", 0]
    return graph


def sibling_image_lanes(settings: Settings, video_lanes: list[str], chosen: str) -> list[str]:
    image_lanes = parse_lane_list(settings.comfy_image_lanes_for_free)
    if not image_lanes:
        return []
    if len(image_lanes) == len(video_lanes) and chosen in video_lanes:
        return [image_lanes[video_lanes.index(chosen)]]
    return image_lanes


def poll_due(receipt: dict[str, Any], *, now: datetime | None = None) -> bool:
    raw = receipt.get("next_poll_at")
    if not raw:
        return True
    try:
        when = datetime.fromisoformat(str(raw))
    except ValueError:
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    clock = now or datetime.now(timezone.utc)
    return clock >= when


def _next_poll_at(settings: Settings) -> str:
    delay = max(0.0, float(settings.comfy_poll_interval_seconds or 0))
    when = datetime.now(timezone.utc) + timedelta(seconds=delay)
    return when.isoformat()


def _prompt_text(payload: dict[str, Any]) -> str:
    for key in ("prompt", "text", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _fail(message: str, *, busy: bool = False) -> AdapterResult:
    return AdapterResult(
        ok=False,
        adapter="comfy-h3",
        error=message,
        receipt={
            "adapter": "comfy-h3",
            "engine": "comfyui-minimax-h3",
            "called_comfy": False,
            "busy": busy,
            "hop1_watch_required": True,
            "window_s": H3_WINDOW_S,
            "frames": H3_FRAMES,
            "fps": H3_FPS,
            "claim": "ComfyUI was not asked to render. No clip file was saved.",
        },
    )


def _load_first_frame(path: str) -> str:
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        raise ComfyError(f"first_frame is not a file: {path}")
    data = file_path.read_bytes()
    if len(data) > 20 * 1024 * 1024:
        raise ComfyError("first_frame is larger than 20 MB")
    return base64.b64encode(data).decode("ascii")


def start_clip(settings: Settings, ctx: JobContext) -> AdapterResult:
    if ctx.cancel_requested():
        return AdapterResult(ok=False, adapter="comfy-h3", error="cancelled")
    payload = ctx.payload if isinstance(ctx.payload, dict) else {}
    prompt = _prompt_text(payload)
    if not prompt:
        return _fail("prompt must be a non-empty string")
    fps = float(settings.comfy_h3_fps or H3_FPS)
    max_frames = int(settings.comfy_h3_max_frames or 362)
    try:
        length = resolve_frames(payload, fps=fps, max_frames=max_frames)
        quality = normalize_quality(payload.get("quality"))
        styles = style_table(settings)
    except ComfyError as exc:
        return _fail(str(exc))
    style_name = str(payload.get("style") or "none").strip() or "none"
    style = styles.get(style_name) if style_name != "none" else None
    style_note = ""
    if style_name not in {"", "none"} and style is None:
        style_note = f"style {style_name} is not configured; rendering without a LoRA"
        style_name = "none"
    if style and style.get("trigger") and style["trigger"] not in prompt:
        prompt = f"{prompt}{' ' if prompt.endswith('.') else '. '}Style: {style['trigger']}."

    from .comfy_client import lanes_for_slot

    video_lanes = lanes_for_slot(settings, "comfy-h3")
    client = ComfyClient(settings)
    try:
        lane = client.pick_lane(video_lanes)
    except ComfyError as exc:
        return _fail(str(exc), busy=exc.busy)

    freed: list[str] = []
    missed: list[str] = []
    for image_lane in sibling_image_lanes(settings, video_lanes, lane):
        if client.free_memory(image_lane):
            freed.append(image_lane)
        else:
            missed.append(image_lane)

    first_b64 = None
    first_path = str(payload.get("first_frame") or "").strip()
    if first_path:
        try:
            first_b64 = _load_first_frame(first_path)
        except ComfyError as exc:
            return _fail(str(exc))
        except OSError as exc:
            return _fail(f"first_frame could not be read: {exc}")

    frames = int(length["frames"])
    raw = int(length["raw"])
    width = int(settings.comfy_h3_width or 960)
    height = int(settings.comfy_h3_height or 544)
    seed = secrets.randbits(32)
    graph = build_h3_graph(
        prompt=prompt,
        negative=_NEGATIVE,
        frames=frames,
        width=width,
        height=height,
        seed=seed,
        quality=quality,
        style=style,
        files=h3_files(settings),
        fps=fps,
        first_frame_b64=first_b64,
    )
    try:
        prompt_id = client.submit_prompt(lane, graph, VIDEO_CLIENT_ID)
    except ComfyError as exc:
        return _fail(str(exc))

    eta_s = eta_seconds(frames)
    eta_text = fmt_duration(eta_s)
    snap_note = ""
    if raw != frames:
        snap_note = f"snapped down from {raw} raw frames to {frames}"
    description = (
        f"Video job started: job_id {ctx.job_id} — {frames} frames "
        f"(~{frames / fps:.2f}s at {fps:g} fps)"
        f"{', ' + snap_note if snap_note else ''}, {width}x{height}, quality {quality}. "
        f"ETA {eta_text}. Poll this Studio job for the mp4 path."
    )
    if missed:
        description += " Could not free a sibling image lane; watch for memory pressure."
    receipt: dict[str, Any] = {
        "adapter": "comfy-h3",
        "engine": "comfyui-minimax-h3",
        "called_comfy": True,
        "comfy_pending": True,
        "job_id": ctx.job_id,
        "eta": eta_text,
        "eta_s": eta_s,
        "description": description,
        "comfy_prompt_id": prompt_id,
        "lane": lane,
        "frames": frames,
        "raw_frames": raw,
        "fps": fps,
        "duration_s": round(frames / fps, 3),
        "snap_note": snap_note,
        "quality": quality,
        "steps": 8 if quality == "fast" else 20,
        "sigma_shift": quality == "fast",
        "width": width,
        "height": height,
        "style": style_name,
        "filename_prefix": f"video/{CLIP_PREFIX}",
        "freed_image_lanes": freed,
        "hop1_watch_required": True,
        "window_s": H3_WINDOW_S,
        "measured_frames": H3_FRAMES,
        "started_at_epoch": time.time(),
        "next_poll_at": _next_poll_at(settings),
        "path": "",
        "still_vs_lock": (
            "Live MiniMax H3 clip was dispatched. Watch the file before stamping "
            "preview-watched. This receipt is not a watched sign-off."
        ),
    }
    if style_note:
        receipt["style_note"] = style_note
    if first_path:
        receipt["first_frame"] = first_path
    if missed:
        receipt["free_warning"] = "could not free the sibling image lane"
    ctx.set_progress(12)
    return AdapterResult(ok=True, adapter="comfy-h3", receipt=receipt, pending=True)


def poll_clip(settings: Settings, state: dict[str, Any]) -> AdapterResult:
    """One history check. Pending until `images` lists a file."""
    prompt_id = str(state.get("comfy_prompt_id") or "")
    lane = str(state.get("lane") or "")
    if not prompt_id or not lane:
        return AdapterResult(
            ok=False,
            adapter="comfy-h3",
            error="Clip job is missing its ComfyUI prompt id.",
            receipt={**state, "comfy_pending": False, "called_comfy": bool(state.get("called_comfy"))},
        )
    client = ComfyClient(settings)
    try:
        entry = client.history_entry(lane, prompt_id)
        output = client.output_file(entry, prompt_id)
    except ComfyError as exc:
        return AdapterResult(
            ok=False,
            adapter="comfy-h3",
            error=str(exc),
            receipt={**state, "comfy_pending": False, "called_comfy": True},
        )
    if not output:
        elapsed = max(0, int(time.time() - float(state.get("started_at_epoch") or time.time())))
        remaining = max(0, int(state.get("eta_s") or 0) - elapsed)
        note = (
            f"Job {state.get('job_id') or prompt_id} is still rendering. "
            f"About {fmt_duration(remaining)} to go."
        )
        receipt = {
            **state,
            "comfy_pending": True,
            "called_comfy": True,
            "poll_note": note,
            "eta_remaining": fmt_duration(remaining),
            "next_poll_at": _next_poll_at(settings),
        }
        return AdapterResult(ok=True, adapter="comfy-h3", receipt=receipt, pending=True)

    try:
        data = client.download_output(lane, output)
    except ComfyError as exc:
        receipt = {
            **state,
            "comfy_pending": True,
            "called_comfy": True,
            "poll_note": f"Render finished but the download failed: {exc}",
            "next_poll_at": _next_poll_at(settings),
        }
        return AdapterResult(ok=True, adapter="comfy-h3", receipt=receipt, pending=True)

    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    filename = f"{CLIP_PREFIX}_{stamp}_{secrets.token_hex(3)}.mp4"
    path = comfy_out_dir(settings) / filename
    path.write_bytes(data)
    frames = int(state.get("frames") or 0)
    mb = round(len(data) / (1024 * 1024), 1)
    description = f"{path} — video done ({mb} MB, {frames} frames)."
    receipt = {
        **state,
        "comfy_pending": False,
        "called_comfy": True,
        "path": str(path),
        "description": description,
        "bytes": len(data),
        "poll_note": "",
    }
    return AdapterResult(
        ok=True,
        adapter="comfy-h3",
        receipt=receipt,
        media_bytes=data,
        media_name=filename,
        media_kind="preview",
        content_type="video/mp4",
    )


class ComfyH3ClipFactory:
    name = "comfy-h3"

    def __init__(self, settings: Settings):
        self.settings = settings

    def hop1(self, ctx: JobContext) -> AdapterResult:
        return start_clip(self.settings, ctx)

    def extend(self, ctx: JobContext) -> AdapterResult:
        return start_clip(self.settings, ctx)
