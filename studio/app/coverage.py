"""Break one scene into timed shot clips. The plan is not a render."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .deps import latest_revision
from .gates import all_gates_green, gate_snapshot
from .models import Episode, Shot, utcnow
from .shots import sync_shots_from_pack

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class CoverageError(ValueError):
    pass


def split_beats(text: str) -> list[str]:
    raw = (text or "").replace("\r\n", "\n").strip()
    if not raw:
        return []
    beats: list[str] = []
    for line in raw.split("\n"):
        piece = line.strip()
        if not piece:
            continue
        parts = _SENTENCE.split(piece)
        for part in parts:
            cleaned = part.strip()
            if cleaned:
                beats.append(cleaned)
    return beats


def _clip_count(scene_s: float, target_s: float, min_s: float, max_s: float) -> int:
    if min_s <= 0 or max_s <= 0 or target_s <= 0:
        raise CoverageError("target_s, min_s, and max_s must be > 0.")
    if max_s < min_s:
        raise CoverageError("max_s must be greater than or equal to min_s.")
    if scene_s <= 0:
        raise CoverageError("scene_s must be > 0.")
    if scene_s < min_s:
        return 1
    aim = min(max(target_s, min_s), max_s)
    count = max(1, int(round(scene_s / aim)))
    while count > 1 and (scene_s / count) < min_s - 1e-9:
        count -= 1
    while (scene_s / count) > max_s + 1e-9:
        count += 1
    return count


def _durations(scene_s: float, count: int) -> list[float]:
    if count <= 1:
        return [round(scene_s, 3)]
    base = round(scene_s / count, 3)
    rows = [base] * (count - 1)
    last = round(scene_s - base * (count - 1), 3)
    rows.append(last)
    return rows


def _spread(items: list[str], count: int) -> list[list[tuple[int, str]]]:
    buckets: list[list[tuple[int, str]]] = [[] for _ in range(count)]
    if not items or count < 1:
        return buckets
    if len(items) >= count:
        base, extra = divmod(len(items), count)
        cursor = 0
        for index in range(count):
            take = base + (1 if index < extra else 0)
            buckets[index] = [(cursor + offset, items[cursor + offset]) for offset in range(take)]
            cursor += take
        return buckets
    for index, item in enumerate(items):
        buckets[index] = [(index, item)]
    return buckets


def plan_clips(
    *,
    action: str = "",
    dialogue: str = "",
    scene_s: float | None = None,
    target_s: float = 8.0,
    min_s: float = 5.0,
    max_s: float = 10.0,
    continue_chain: bool = False,
    take: str = "A",
) -> dict[str, Any]:
    """Allocate every action beat and dialogue line across ~5–10s clips.

    When ``scene_s`` is omitted, one clip is planned per beat at ``target_s``
    (clamped into min/max). A coverage plan never claims a clip was rendered.
    """
    try:
        target = float(target_s)
        low = float(min_s)
        high = float(max_s)
    except (TypeError, ValueError) as exc:
        raise CoverageError("Durations must be numbers.") from exc
    action_beats = split_beats(action)
    dialogue_lines = [line.strip() for line in (dialogue or "").splitlines() if line.strip()]
    if scene_s not in {None, ""}:
        try:
            length = float(scene_s)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise CoverageError("scene_s must be a number.") from exc
        count = _clip_count(length, target, low, high)
        durations = _durations(length, count)
        declared = round(length, 3)
    else:
        units = max(len(action_beats), len(dialogue_lines), 1)
        count = units
        clamped = min(max(target, low), high) if low <= high else target
        if low <= 0 or high < low:
            raise CoverageError("target_s, min_s, and max_s must be > 0 and max_s >= min_s.")
        durations = [round(clamped, 3)] * count
        declared = round(sum(durations), 3)
    actions = _spread(action_beats, count)
    lines = _spread(dialogue_lines, count)
    clips: list[dict[str, Any]] = []
    cursor = 0.0
    for index, duration in enumerate(durations):
        start = round(cursor, 3)
        end = round(cursor + duration, 3)
        cursor = end
        action_rows = actions[index]
        line_rows = lines[index]
        short = duration + 1e-9 < low
        over = duration > high + 1e-9
        action_text = " ".join(text for _i, text in action_rows).strip()
        dialogue_text = " / ".join(text for _i, text in line_rows).strip()
        shown = action_text or "(held)"
        if dialogue_text:
            shown = f"{shown} | {dialogue_text}"
        join = "cut" if index == 0 or not continue_chain else "continue"
        prior = f"cov-{index}" if join == "continue" else ""
        clips.append(
            {
                "edit_row_id": f"cov-{index + 1}",
                "index": index,
                "take": take or "A",
                "join": join,
                "song_t": f"{start:.3f}-{end:.3f}",
                "duration_s": duration,
                "action": shown[:1000],
                "coverage": {
                    "index": index,
                    "count": count,
                    "duration_s": duration,
                    "start_s": start,
                    "end_s": end,
                    "action_beats": [text for _i, text in action_rows],
                    "action_indexes": [i for i, _text in action_rows],
                    "dialogue": [text for _i, text in line_rows],
                    "dialogue_indexes": [i for i, _text in line_rows],
                    "short": short,
                    "over_cap": over,
                    "plan_only": True,
                    "rendered": False,
                    "continue_from_edit_row": prior,
                },
            }
        )
    covered_dialogue = sorted(
        index for clip in clips for index in clip["coverage"]["dialogue_indexes"]
    )
    covered_action = sorted(index for clip in clips for index in clip["coverage"]["action_indexes"])
    return {
        "plan_only": True,
        "rendered": False,
        "scene_s": declared,
        "clip_count": len(clips),
        "target_s": target,
        "min_s": low,
        "max_s": high,
        "action_count": len(action_beats),
        "dialogue_count": len(dialogue_lines),
        "covered_action_indexes": covered_action,
        "covered_dialogue_indexes": covered_dialogue,
        "clips": clips,
        "note": (
            "Coverage is a timed plan stored on the board. "
            "No clip was rendered and no MP4 was written."
        ),
    }


def _edit_row(clip: dict[str, Any], *, location: str) -> dict[str, Any]:
    return {
        "id": clip["edit_row_id"],
        "songT": clip["song_t"],
        "durS": f"{clip['duration_s']:.3f}",
        "join": clip["join"],
        "take": clip["take"],
        "locationGrade": location,
        "cameraVerb": "",
        "cameraAmplitude": "",
        "cameraSpeed": "",
        "action": clip["action"],
        "hold": "",
        "notes": "Coverage plan only. Not a rendered clip.",
        "entities": "",
        "coverage": clip["coverage"],
    }


def apply_coverage(db: Session, episode: Episode, plan: dict[str, Any], *, replace: bool = True) -> list[Shot]:
    revision = latest_revision(episode)
    if revision is None or not isinstance(revision.pack_json, dict):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "pack_missing",
                "message": "Start a pack before breaking a scene into clips. Coverage is stored on the board.",
            },
        )
    if replace:
        for shot in list(episode.shots):
            if shot.receipt is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "coverage_would_drop_receipts",
                        "message": (
                            "Refusing to replace the board while a shot still has a continuity receipt. "
                            "Coverage is a plan, not a reason to drop a watched hop-1."
                        ),
                    },
                )
    pack = dict(revision.pack_json)
    location = ""
    existing_rows = pack.get("editList") if isinstance(pack.get("editList"), list) else []
    if existing_rows and isinstance(existing_rows[0], dict):
        location = str(existing_rows[0].get("locationGrade") or "")
    rows = [_edit_row(clip, location=location) for clip in plan["clips"]]
    if replace:
        pack["editList"] = rows
    else:
        pack["editList"] = list(existing_rows) + rows
    meta = dict(pack.get("studioMeta") or {}) if isinstance(pack.get("studioMeta"), dict) else {}
    meta["coverage"] = {
        "plan_only": True,
        "rendered": False,
        "clip_count": plan["clip_count"],
        "scene_s": plan["scene_s"],
    }
    pack["studioMeta"] = meta
    revision.pack_json = pack
    flag_modified(revision, "pack_json")
    revision.gate_snapshot = gate_snapshot(pack)
    revision.all_gates_green = all_gates_green(pack)
    episode.updated_at = utcnow()
    db.flush()
    shots = sync_shots_from_pack(db, episode, revision)
    return list(shots)
