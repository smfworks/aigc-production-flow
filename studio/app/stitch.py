"""Final concat step. A plan is not an MP4."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .adapters.base import AdapterResult
from .config import get_settings
from .models import Episode, Job
from .timeline import render_playlist

VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}

HERMES_STITCH_CONTRACT = (
    "Hermes stitch skill: read concat_plan in playlist order. "
    "Concat only local video files that exist. "
    "Write the output path back when a real file exists. "
    "Do not invent an MP4. "
    "If inputs are fixture JSON receipts, leave the run awaiting stitch. "
    "Studio did not call Comfy to build this plan. This is not CapCut."
)


def _ffmpeg_concat(paths: list[Path], dest: Path) -> str | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return "ffmpeg is not on PATH"
    list_file = dest.with_suffix(".txt")
    lines = []
    for path in paths:
        escaped = str(path.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        proc = subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(dest)],
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    if proc.returncode != 0 or not dest.is_file() or dest.stat().st_size <= 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace")[-400:]
        if dest.exists():
            dest.unlink()
        return err or "ffmpeg did not write a file"
    return None


def run_stitch(job: Job, episode: Episode, set_progress) -> AdapterResult:
    """Build a concat plan. Write an MP4 only when ffmpeg can concat real video files."""
    set_progress(15)
    playlist = render_playlist(episode)
    shots = playlist.get("shots") if isinstance(playlist.get("shots"), list) else []
    plan: list[dict] = []
    videos: list[Path] = []
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        raw_path = str(shot.get("media_path") or "")
        path = Path(raw_path) if raw_path else None
        suffix = path.suffix.lower() if path else ""
        is_video = bool(path) and suffix in VIDEO_SUFFIXES and path.is_file()
        plan.append(
            {
                "sort_index": shot.get("sort_index"),
                "edit_row_id": shot.get("edit_row_id"),
                "take": shot.get("take"),
                "join": shot.get("join"),
                "duration_s": shot.get("duration_s"),
                "frames": shot.get("frames"),
                "rec_in_tc": shot.get("rec_in_tc"),
                "rec_out_tc": shot.get("rec_out_tc"),
                "media_path": raw_path or None,
                "video_file": is_video,
            }
        )
        if is_video and path is not None:
            videos.append(path)
    set_progress(45)
    ffmpeg = shutil.which("ffmpeg")
    can_concat = bool(ffmpeg) and bool(plan) and len(videos) == len(plan)
    ffmpeg_error = ""
    if can_concat:
        dest_dir = get_settings().media_path / episode.id / "stitch"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{job.id}.mp4"
        ffmpeg_error = _ffmpeg_concat(videos, dest) or ""
        if not ffmpeg_error and dest.is_file() and dest.stat().st_size > 0:
            set_progress(90)
            return AdapterResult(
                ok=True,
                adapter="ffmpeg",
                media_bytes=dest.read_bytes(),
                media_name=f"stitch-{job.id[:8]}.mp4",
                media_kind="preview",
                content_type="video/mp4",
                receipt={
                    "state": "stitched",
                    "produced_mp4": True,
                    "called_comfy": False,
                    "ffmpeg": True,
                    "path": str(dest),
                    "concat_plan": plan,
                    "claim": "Local ffmpeg concat of existing video files. Not a Comfy render. Not CapCut.",
                    "hermes_skill": {"name": "stitch", "contract": HERMES_STITCH_CONTRACT},
                },
            )
        if dest.exists():
            dest.unlink()
    if can_concat and ffmpeg_error:
        reason = f"ffmpeg did not produce a file ({ffmpeg_error}). Awaiting stitch. No MP4 was invented."
    elif not plan:
        reason = "The shot playlist is empty. Awaiting stitch. No MP4 was produced."
    else:
        reason = (
            "Clip inputs are not local video files, so no concat ran. "
            "Fixture receipts are not an MP4. Awaiting stitch."
        )
    set_progress(90)
    receipt = {
        "state": "awaiting_stitch",
        "produced_mp4": False,
        "called_comfy": False,
        "ffmpeg_available": bool(ffmpeg),
        "video_inputs": len(videos),
        "plan_rows": len(plan),
        "concat_plan": plan,
        "playlist": {"format": playlist.get("format"), "fps": playlist.get("fps")},
        "hermes_skill": {"name": "stitch", "contract": HERMES_STITCH_CONTRACT},
        "reason": reason,
        "claim": "Stitch plan only. No MP4 was produced.",
    }
    return AdapterResult(
        ok=True,
        adapter="hermes-stitch",
        media_bytes=json.dumps(receipt, indent=2).encode("utf-8"),
        media_name=f"stitch-plan-{job.id[:8]}.json",
        media_kind="other",
        content_type="application/json",
        receipt=receipt,
    )
