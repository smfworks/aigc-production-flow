"""Hop-1 preview desk: required shots, continuity receipts, generate-ok blockers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .deps import latest_revision
from .gates import as_list, as_record, filled, is_none_still, is_real_still_file, still_ok
from .models import ContinuityReceipt, Episode, MediaAsset, Shot, utcnow
from .schemas import ContinuityReceiptOut
from .store import get_store

DURATION_KEYS = ("duration_s", "duration", "seconds")
FRAME_KEYS = ("frames", "nb_frames", "nframes")


def pack_of(episode: Episode) -> dict[str, Any]:
    revision = latest_revision(episode)
    if not revision or not isinstance(revision.pack_json, dict):
        return {}
    return revision.pack_json


def hop1_required_shots(episode: Episode, pack: dict[str, Any] | None = None) -> list[Shot]:
    data = pack if pack is not None else pack_of(episode)
    planned: set[str] = set()
    for raw in as_list(data.get("takes")):
        take = as_record(raw)
        name = str(take.get("take") or "").strip()
        if not name:
            continue
        if take.get("hop1Planned") is False:
            continue
        planned.add(name)
    first: dict[str, Shot] = {}
    for shot in episode.shots:
        name = (shot.take or "").strip()
        if name and name not in first:
            first[name] = shot
    if planned:
        return [first[name] for name in first if name in planned]
    if episode.shots:
        return [episode.shots[0]]
    return []


def is_hop1_required(shot: Shot, pack: dict[str, Any] | None = None) -> bool:
    episode = shot.episode
    required = hop1_required_shots(episode, pack if pack is not None else pack_of(episode))
    return any(row.id == shot.id for row in required)


def receipt_blockers(receipt: ContinuityReceipt | None, *, for_extend: bool = False) -> list[str]:
    if receipt is None:
        return ["No continuity receipt."]
    problems: list[str] = []
    if not receipt.media_id:
        problems.append("Attach hop-1 preview media.")
    duration_ok = receipt.duration_s is not None and receipt.duration_s > 0
    frames_ok = receipt.frames is not None and receipt.frames > 0
    if not duration_ok and not frames_ok:
        problems.append("Receipt needs duration (seconds) or frame count.")
    if not filled(receipt.still_vs_lock):
        problems.append("Receipt needs a still-vs-lock note.")
    if not receipt.preview_watched:
        problems.append("Hop-1 is not preview-watched.")
    if receipt.ng_reason.strip():
        problems.append(f"NG: {receipt.ng_reason.strip()}")
    if for_extend:
        return problems
    return problems


def receipt_complete(receipt: ContinuityReceipt | None) -> bool:
    if receipt is None:
        return False
    problems = receipt_blockers(receipt, for_extend=False)
    return not problems


def extend_ok(receipt: ContinuityReceipt | None) -> bool:
    return not receipt_blockers(receipt, for_extend=True)


def receipt_out(receipt: ContinuityReceipt | None) -> ContinuityReceiptOut | None:
    if receipt is None:
        return None
    blockers = receipt_blockers(receipt)
    return ContinuityReceiptOut(
        id=receipt.id,
        episode_id=receipt.episode_id,
        shot_id=receipt.shot_id,
        media_id=receipt.media_id,
        duration_s=receipt.duration_s,
        frames=receipt.frames,
        fps=receipt.fps,
        still_vs_lock=receipt.still_vs_lock or "",
        ng_reason=receipt.ng_reason or "",
        source=receipt.source if receipt.source in {"manual", "parsed"} else "manual",  # type: ignore[arg-type]
        preview_watched=bool(receipt.preview_watched),
        watched_by=receipt.watched_by or "",
        watched_at=receipt.watched_at,
        notes=receipt.notes or "",
        created_by=receipt.created_by,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at,
        complete=not blockers,
        extend_ok=extend_ok(receipt),
        blockers=blockers,
    )


def generate_ok_blockers(episode: Episode) -> dict[str, Any] | None:
    revision = latest_revision(episode)
    snapshot = revision.gate_snapshot if revision else None
    gates = (snapshot or {}).get("gates") if isinstance(snapshot, dict) else None
    if not revision or not revision.all_gates_green:
        return {
            "code": "gates_not_green",
            "message": (
                "Refuse generate-ok until the latest pack revision shows all gates green "
                "(nine README gates plus entity-schedule and lock-diff). "
                "Do not skip the four-stage / gate order. Shot ready ≠ generating."
            ),
            "gates": gates or [],
        }
    missing: list[dict[str, str]] = []
    pack = revision.pack_json if isinstance(revision.pack_json, dict) else {}
    for shot in hop1_required_shots(episode, pack):
        blockers = receipt_blockers(shot.receipt)
        if blockers:
            missing.append(
                {
                    "shot_id": shot.id,
                    "take": shot.take or "",
                    "sort_index": str(shot.sort_index),
                    "reason": "; ".join(blockers),
                }
            )
    if missing:
        return {
            "code": "preview_incomplete",
            "message": (
                "Refuse generate-ok until each required hop-1 is preview-watched with a "
                "continuity receipt (duration/frames + still-vs-lock). An NG reason blocks spend."
            ),
            "missing": missing,
        }
    return None


def parse_preview_bytes(data: bytes, suffix: str = "", content_type: str = "") -> dict[str, Any]:
    text = ""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    if text.strip().startswith("{") or suffix.lower() in {".json", ".txt", ".md"}:
        parsed = _parse_jsonish(text)
        if parsed:
            parsed["source"] = "parsed"
            return parsed
    return {}


def parse_preview_file(path: Path, content_type: str = "") -> dict[str, Any]:
    if not path.is_file():
        return {}
    suffix = path.suffix.lower()
    if suffix in {".json", ".txt", ".md"}:
        return parse_preview_bytes(path.read_bytes(), suffix=suffix, content_type=content_type)
    if suffix in {".mp4", ".webm", ".mov"} or content_type.startswith("video/"):
        probed = _ffprobe(path)
        if probed:
            probed["source"] = "parsed"
        return probed
    return {}


def _parse_jsonish(text: str) -> dict[str, Any]:
    blob: Any
    try:
        blob = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(blob, dict):
        return {}
    out: dict[str, Any] = {}
    for key in DURATION_KEYS:
        if key in blob:
            try:
                value = float(blob[key])
            except (TypeError, ValueError):
                continue
            if value > 0:
                out["duration_s"] = value
                break
    for key in FRAME_KEYS:
        if key in blob:
            try:
                value = int(float(blob[key]))
            except (TypeError, ValueError):
                continue
            if value > 0:
                out["frames"] = value
                break
    if blob.get("fps") is not None:
        try:
            out["fps"] = float(blob["fps"])
        except (TypeError, ValueError):
            pass
    note = blob.get("still_vs_lock") or blob.get("stillVsLock")
    if isinstance(note, str) and note.strip():
        out["still_vs_lock"] = note.strip()
    return out


def _ffprobe(path: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(  # noqa: S603
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {}
    if completed.returncode != 0:
        return {}
    try:
        body = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    out: dict[str, Any] = {}
    fmt = body.get("format") if isinstance(body.get("format"), dict) else {}
    try:
        duration = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration > 0:
        out["duration_s"] = duration
    for stream in body.get("streams") or []:
        if not isinstance(stream, dict):
            continue
        if stream.get("codec_type") != "video":
            continue
        frames = stream.get("nb_frames")
        try:
            count = int(frames) if frames not in {None, "N/A", ""} else 0
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            out["frames"] = count
        rate = str(stream.get("r_frame_rate") or "")
        if "/" in rate:
            num, _, den = rate.partition("/")
            try:
                fps = float(num) / float(den)
            except (TypeError, ValueError, ZeroDivisionError):
                fps = 0.0
            if fps > 0:
                out["fps"] = fps
        if "duration_s" not in out:
            try:
                stream_dur = float(stream.get("duration") or 0)
            except (TypeError, ValueError):
                stream_dur = 0.0
            if stream_dur > 0:
                out["duration_s"] = stream_dur
        break
    if out.get("duration_s") and out.get("fps") and not out.get("frames"):
        out["frames"] = int(round(float(out["duration_s"]) * float(out["fps"])))
    return out


def get_or_create_receipt(db: Session, shot: Shot, user_name: str) -> ContinuityReceipt:
    if shot.receipt:
        return shot.receipt
    receipt = ContinuityReceipt(
        episode_id=shot.episode_id,
        shot_id=shot.id,
        created_by=user_name,
        source="manual",
    )
    db.add(receipt)
    db.flush()
    return receipt


def apply_receipt(
    db: Session,
    shot: Shot,
    *,
    user_name: str,
    media_id: str | None = None,
    duration_s: float | None = None,
    frames: int | None = None,
    fps: float | None = None,
    still_vs_lock: str | None = None,
    ng_reason: str | None = None,
    source: str | None = None,
    parse_media: bool = True,
    notes: str | None = None,
    watched: bool | None = None,
) -> ContinuityReceipt:
    receipt = get_or_create_receipt(db, shot, user_name)
    if media_id:
        asset = db.get(MediaAsset, media_id)
        if not asset or asset.episode_id != shot.episode_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found on this episode.")
        receipt.media_id = media_id
        if parse_media:
            store = get_store()
            local = store.local_path(asset.path)
            if local is not None and local.is_file():
                parsed = parse_preview_file(local, asset.content_type)
            else:
                try:
                    data = store.get_bytes(asset.path)
                except HTTPException:
                    data = b""
                suffix = Path(asset.original_name or asset.path or "").suffix
                parsed = parse_preview_bytes(data, suffix=suffix, content_type=asset.content_type or "")
            if parsed.get("duration_s") is not None and duration_s is None:
                duration_s = float(parsed["duration_s"])
                source = source or "parsed"
            if parsed.get("frames") is not None and frames is None:
                frames = int(parsed["frames"])
                source = source or "parsed"
            if parsed.get("fps") is not None and fps is None:
                fps = float(parsed["fps"])
            if parsed.get("still_vs_lock") and not (still_vs_lock or receipt.still_vs_lock):
                still_vs_lock = str(parsed["still_vs_lock"])
    if duration_s is not None:
        receipt.duration_s = duration_s
    if frames is not None:
        receipt.frames = frames
    if fps is not None:
        receipt.fps = fps
    if still_vs_lock is not None:
        receipt.still_vs_lock = still_vs_lock.strip()
    if ng_reason is not None:
        receipt.ng_reason = ng_reason.strip()
    if notes is not None:
        receipt.notes = notes.strip()
    if source in {"manual", "parsed"}:
        receipt.source = source
    elif source is None and (duration_s is not None or frames is not None):
        receipt.source = "manual"
    receipt.updated_at = utcnow()
    if watched is True:
        mark_preview_watched(receipt, user_name, True)
    elif watched is False:
        mark_preview_watched(receipt, user_name, False)
    return receipt


def mark_preview_watched(receipt: ContinuityReceipt, user_name: str, watched: bool) -> ContinuityReceipt:
    if watched:
        probe = ContinuityReceipt(
            episode_id=receipt.episode_id,
            shot_id=receipt.shot_id,
            media_id=receipt.media_id,
            duration_s=receipt.duration_s,
            frames=receipt.frames,
            fps=receipt.fps,
            still_vs_lock=receipt.still_vs_lock,
            ng_reason="",
            source=receipt.source,
            preview_watched=False,
        )
        blockers = [
            item
            for item in receipt_blockers(probe)
            if item != "Hop-1 is not preview-watched."
        ]
        if blockers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "receipt_incomplete",
                    "message": (
                        "Refuse preview-watched until hop-1 preview media is attached and the "
                        "receipt has duration/frames plus a still-vs-lock note."
                    ),
                    "blockers": blockers,
                },
            )
        receipt.preview_watched = True
        receipt.watched_by = user_name
        receipt.watched_at = utcnow()
    else:
        receipt.preview_watched = False
        receipt.watched_by = ""
        receipt.watched_at = None
    receipt.updated_at = utcnow()
    return receipt


def plates_bound_for_shot(
    shot: Shot, pack: dict[str, Any], media: list[MediaAsset]
) -> tuple[bool, str]:
    take_card = None
    for raw in as_list(pack.get("takes")):
        row = as_record(raw)
        if str(row.get("take") or "").strip() == (shot.take or "").strip():
            take_card = row
            break
    mode = str((take_card or {}).get("hop1Mode") or "").strip().lower()
    plate = str((take_card or {}).get("hop1Plate") or "")
    if mode == "i2va":
        if is_real_still_file(plate):
            return True, "pack plate file"
        labels = {(asset.entity_label or "").strip().lower() for asset in media if asset.kind == "plate"}
        entities = [part.strip().lower() for part in (shot.entities or "").split(",") if part.strip()]
        take_key = (shot.take or "").strip().lower()
        if take_key and any(take_key in label for label in labels):
            return True, "studio plate media (take)"
        if any(entity and any(entity in label for label in labels) for entity in entities):
            return True, "studio plate media (entity)"
        for asset in media:
            if asset.kind == "plate" and (asset.entity_type or "") in {"character", "prop", "scene"}:
                if (asset.entity_label or "").strip().lower() in entities:
                    return True, "studio plate media"
        return False, "I2VA hop-1 needs a bound plate (pack still or studio media)."
    if mode == "t2v":
        if still_ok(plate) and is_none_still(plate):
            return True, "T2V none + why"
        return True, "T2V hop-1 (no plate required)"
    if still_ok(plate) and is_none_still(plate):
        return True, "plate none + why"
    if is_real_still_file(plate):
        return True, "pack plate file"
    return False, "Hop-1 plate is not bound (need a plate file or none + why)."
