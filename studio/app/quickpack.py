"""Local quick-create plans and the pack mirror.

Studio plans shots on this machine. Cast notes become cast rows. When a plan
carries staging, the mirror keeps that map on ``studioMeta.staging``, copies
each shot's blocking onto the edit row and ``studioMeta.shot_stages``, and
fills ``entities`` from the visible blocks. ``who_is_where`` is the read-only
line for one shot. This module does not call a network and does not invent an MP4.

Camera cards on a shot become Studio edit-list camera fields with this table.
Unlisted moves stay blank so the edit-list gate can fail honestly.

| Plan ``camera.move`` | Studio ``cameraVerb`` |
|---|---|
| ``dolly_in`` | ``push`` |
| ``dolly_out`` | ``pull`` |
| ``orbit`` | ``arc`` |
| ``pan`` | ``pan`` |
| ``whip_pan`` | ``pan`` |
| ``tilt`` | ``tilt`` |
| ``handheld`` | ``shake`` |
| ``static`` | ``static`` |

| Plan ``camera.scale`` | Studio ``cameraAmplitude`` |
|---|---|
| ``wide`` | ``wide`` |
| ``medium`` | ``medium`` |
| ``close`` | ``close`` |
| ``extreme_close`` | ``tight`` |

There is no speed token. ``cameraSpeed`` stays empty.

Beat roles become map energy (the pack gate's verse/chorus/bridge set):

| Beat role | Studio ``energy`` |
|---|---|
| ``setup`` | ``verse`` |
| ``turn`` | ``bridge`` |
| ``climax`` | ``chorus`` |
| ``button`` | ``outro`` |

Map clocks are cumulative shot durations (``m:ss``) at the first shot of that beat.
A plan with no staging leaves ``studioMeta.staging`` unset. Cast names still fill
``entities`` when the plan names a cast.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from .blankpack import empty_pack, studio_meta

CAMERA_MOVE_TO_VERB: dict[str, str] = {
    "dolly_in": "push",
    "dolly_out": "pull",
    "orbit": "arc",
    "pan": "pan",
    "whip_pan": "pan",
    "tilt": "tilt",
    "handheld": "shake",
    "static": "static",
}

CAMERA_SCALE_TO_AMPLITUDE: dict[str, str] = {
    "wide": "wide",
    "medium": "medium",
    "close": "close",
    "extreme_close": "tight",
}

BEAT_ROLE_TO_ENERGY: dict[str, str] = {
    "setup": "verse",
    "turn": "bridge",
    "climax": "chorus",
    "button": "outro",
}


def studio_pack_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Mirror a quick-create plan into a Studio pack.json. Does not call a renderer.

    Gates are whatever ``evaluate_gates`` says about this dict. Nothing here
    sets ``all_gates_green`` or stamps generate-ok.
    """
    title = _text(plan.get("title")) or "Quick episode"
    pack = empty_pack(
        title,
        source="quick-plan",
        note=(
            "Pack mirrored from a local quick-create plan. Gates are evaluated as written. "
            "This mirror does not render and does not invent an MP4."
        ),
    )
    pack["logLine"] = _text(plan.get("logline"))
    shots = [row for row in _list(plan.get("shots")) if isinstance(row, dict)]
    starts, total = _shot_clocks(shots)
    pack["durationTarget"] = f"{total}s" if total else ""
    pack["map"] = _map_rows(plan, shots, starts)
    pack["editList"] = _edit_rows(plan, shots, starts)
    pack["look"]["styleLine"] = _style_line(plan.get("look_bible"))
    characters = _mirror_characters(plan)
    if characters:
        pack["characters"] = characters
    pack["studioMeta"] = studio_meta(
        source="quick-plan",
        model="none",
        model_ran=False,
        note=(
            "Mirrored from a local quick-create plan. model_ran is false because this JSON is not a render. "
            "Gates stay whatever the pack actually satisfies. called_comfy is false."
        ),
    )
    pack["studioMeta"]["called_comfy"] = False
    pack["studioMeta"]["produced_mp4"] = False
    pack["studioMeta"]["generate_ready"] = False
    staging = plan.get("staging") if isinstance(plan.get("staging"), dict) else None
    if staging is not None:
        pack["studioMeta"]["staging"] = copy.deepcopy(staging)
    if "lock_staging" in plan:
        pack["studioMeta"]["lock_staging"] = bool(plan.get("lock_staging"))
    aspect = _text(plan.get("aspect_ratio"))
    if aspect:
        pack["studioMeta"]["aspect_ratio"] = aspect
    shot_stages = _shot_stages(shots)
    if shot_stages:
        pack["studioMeta"]["shot_stages"] = shot_stages
    return pack


def _shot_clocks(shots: list[dict[str, Any]]) -> tuple[list[int], int]:
    starts: list[int] = []
    cursor = 0
    for shot in shots:
        starts.append(cursor)
        try:
            duration = int(shot.get("duration_sec") or 0)
        except (TypeError, ValueError):
            duration = 0
        cursor += max(0, duration)
    return starts, cursor


def _map_rows(
    plan: dict[str, Any],
    shots: list[dict[str, Any]],
    starts: list[int],
) -> list[dict[str, str]]:
    from .blankpack import _id

    beats = [row for row in _list(plan.get("beat_map")) if isinstance(row, dict)]
    if not beats:
        seen: list[str] = []
        for shot in shots:
            role = _text(shot.get("beat"))
            if role and role not in seen:
                seen.append(role)
        beats = [{"role": role, "summary": role} for role in seen]
    rows: list[dict[str, str]] = []
    for beat in beats:
        role = _text(beat.get("role")).lower()
        summary = _text(beat.get("summary")) or role
        clock = ""
        for shot, start in zip(shots, starts, strict=False):
            if _text(shot.get("beat")).lower() == role and role:
                clock = _clock(start)
                break
        rows.append(
            {
                "id": _id(),
                "clock": clock,
                "beat": summary,
                "energy": BEAT_ROLE_TO_ENERGY.get(role, ""),
            }
        )
    if not rows:
        rows.append({"id": _id(), "clock": "", "beat": "", "energy": ""})
    return rows


def _edit_rows(
    plan: dict[str, Any],
    shots: list[dict[str, Any]],
    starts: list[int],
) -> list[dict[str, Any]]:
    from .blankpack import _id

    if not shots:
        return [
            {
                "id": _id(),
                "songT": "",
                "durS": "",
                "join": "",
                "take": "",
                "locationGrade": "",
                "cameraVerb": "",
                "cameraAmplitude": "",
                "cameraSpeed": "",
                "action": "",
                "hold": "",
                "notes": "",
                "entities": "",
            }
        ]
    rows: list[dict[str, Any]] = []
    for index, (shot, start) in enumerate(zip(shots, starts, strict=False)):
        camera = shot.get("camera") if isinstance(shot.get("camera"), dict) else {}
        move = _text(camera.get("move")).lower()
        scale = _text(camera.get("scale")).lower()
        try:
            duration = int(shot.get("duration_sec") or 0)
        except (TypeError, ValueError):
            duration = 0
        notes = []
        if _text(shot.get("start_state")):
            notes.append(f"start: {_text(shot.get('start_state'))}")
        if _text(shot.get("end_state")):
            notes.append(f"end: {_text(shot.get('end_state'))}")
        if _text(camera.get("exit_frame")):
            notes.append(f"exit: {_text(camera.get('exit_frame'))}")
        where = who_is_where(plan, shot)
        if where:
            notes.append(f"staging: {where}")
        row: dict[str, Any] = {
            "id": _id(),
            "songT": _clock(start),
            "durS": str(duration) if duration else "",
            "join": "cut" if index == 0 else "continue",
            "take": "A",
            "locationGrade": "",
            "cameraVerb": CAMERA_MOVE_TO_VERB.get(move, ""),
            "cameraAmplitude": CAMERA_SCALE_TO_AMPLITUDE.get(scale, ""),
            "cameraSpeed": "",
            "action": _text(shot.get("prompt_motion")),
            "hold": "no",
            "notes": " ".join(notes),
            "entities": _entity_names_for_shot(plan, shot),
        }
        stage = shot.get("stage")
        if isinstance(stage, dict):
            row["stage"] = copy.deepcopy(stage)
        rows.append(row)
    return rows


def _style_line(bible: Any) -> str:
    if isinstance(bible, str):
        return bible.strip()
    if not isinstance(bible, dict):
        return ""
    lines = []
    for label in ("Cast", "Wardrobe", "Palette", "Lighting", "Camera"):
        value = _text(bible.get(label.lower()))
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _characters(cast: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _list(cast):
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        if not name:
            continue
        rows.append(_character_row(name, _text(item.get("markers"))))
    return rows


def _character_row(name: str, marks: str = "") -> dict[str, Any]:
    from .blankpack import DEFAULT_CHARACTER_FORBIDDEN, DEFAULT_STILL_CANVAS, _id

    return {
        "id": _id(),
        "name": name,
        "stillFile": "",
        "stillSource": "",
        "stillCanvas": DEFAULT_STILL_CANVAS,
        "speakerId": "none",
        "ageSex": "",
        "faceHairBeard": "",
        "body": "",
        "wardrobe": "",
        "footwear": "",
        "distinguishingMarks": marks,
        "eraForbiddenModern": "",
        "lockParagraph": "",
        "forbidden": DEFAULT_CHARACTER_FORBIDDEN,
        "motionNotes": "",
    }


def _mirror_characters(plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Cast cards, plus staging figures that are not already named."""
    rows = _characters(plan.get("cast"))
    seen = {row["name"].strip().lower() for row in rows if row.get("name")}
    names = _name_index(plan)
    staging = plan.get("staging") if isinstance(plan.get("staging"), dict) else {}
    for scene in _list(staging.get("scenes")):
        if not isinstance(scene, dict):
            continue
        for entity in _list(scene.get("entities")):
            if not isinstance(entity, dict):
                continue
            kind = _text(entity.get("kind") or "character").lower().replace("-", "_").replace(" ", "_")
            if kind in {"prop", "location"}:
                continue
            eid = _text(entity.get("id"))
            name = names.get(eid) or _text(entity.get("label"))
            if not name or name.lower() in seen:
                continue
            label = _text(entity.get("label"))
            marks = label if label and label != name else ""
            rows.append(_character_row(name, marks))
            seen.add(name.lower())
    return rows


_CAST_ROLES = {"character", "prop", "location"}
_CAST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_MAX_CAST = 8
_SKIP_CAST_NAMES = {"character", "prop", "location", "the", "a", "an"}
_WORD_ALIASES = {
    "screen_left": "screen-left",
    "screen_right": "screen-right",
    "toward_camera": "toward camera",
    "away_from_camera": "away from camera",
}


def cast_payload_for_plan(
    *,
    cast: Any = None,
    cast_notes: str = "",
    prompt: str = "",
) -> list[dict[str, str]]:
    """Cast rows from a structured list, cast notes, or a Cast: block.

    Empty input returns an empty list. Nothing here invents a lead.
    """
    structured = _structured_cast(cast)
    if structured:
        return structured
    notes = (cast_notes or "").strip() or _cast_section(prompt)
    return _cast_from_notes(notes)


def who_is_where(plan: dict[str, Any], shot: dict[str, Any]) -> str:
    """Compact 'who is where' line from a shot's blocking. Empty when there is none."""
    stage = shot.get("stage") if isinstance(shot.get("stage"), dict) else None
    blocks = _blocking_blocks(stage)
    if not blocks:
        return ""
    names = _name_index(plan)
    relations = _relations_for(plan, shot)
    parts: list[str] = []
    for block in blocks:
        if block.get("visible") is False:
            continue
        eid = _text(block.get("id"))
        if not eid:
            continue
        name = names.get(eid, eid)
        place = _place_words(block)
        relation = _relation_phrase(eid, relations, names, _words(block.get("depth")))
        if place and relation:
            parts.append(f"{name}: {place}, {relation}")
        elif place:
            parts.append(f"{name}: {place}")
        elif relation:
            parts.append(f"{name}: {relation}")
        else:
            parts.append(name)
    return "; ".join(parts)


def _entity_names_for_shot(plan: dict[str, Any], shot: dict[str, Any]) -> str:
    names = _name_index(plan)
    stage = shot.get("stage") if isinstance(shot.get("stage"), dict) else None
    blocks = _blocking_blocks(stage)
    if blocks:
        picked = [
            names.get(_text(block.get("id")), _text(block.get("id")))
            for block in blocks
            if block.get("visible") is not False and _text(block.get("id"))
        ]
        joined = _join_names(picked)
        if joined:
            return joined
    scene = _scene_for(plan, shot)
    if scene:
        picked = []
        for entity in _list(scene.get("entities")):
            if not isinstance(entity, dict):
                continue
            kind = _text(entity.get("kind") or "character").lower()
            if kind == "location":
                continue
            eid = _text(entity.get("id"))
            if eid:
                picked.append(names.get(eid, eid))
        joined = _join_names(picked)
        if joined:
            return joined
    cast_names = [
        _text(item.get("name"))
        for item in _list(plan.get("cast"))
        if isinstance(item, dict) and _text(item.get("name"))
    ]
    return _join_names(cast_names)


def _shot_stages(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-shot blocking kept on studioMeta so a later pack edit still has it.

    The in-studio editor keeps ``studioMeta`` and the ``entities`` string. It does
    not keep an extra object on an edit row.
    """
    rows: list[dict[str, Any]] = []
    for shot in shots:
        stage = shot.get("stage")
        if not isinstance(stage, dict):
            continue
        rows.append({"id": _text(shot.get("id")), "stage": copy.deepcopy(stage)})
    return rows


def _blocking_blocks(stage: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(stage, dict):
        return []
    start = stage.get("start")
    if isinstance(start, list) and start:
        return [block for block in start if isinstance(block, dict)]
    end = stage.get("end")
    if isinstance(end, list) and end:
        return [block for block in end if isinstance(block, dict)]
    return []


def _name_index(plan: dict[str, Any]) -> dict[str, str]:
    cast_by_id: dict[str, str] = {}
    for item in _list(plan.get("cast")):
        if not isinstance(item, dict):
            continue
        cid = _text(item.get("id"))
        name = _text(item.get("name"))
        if cid and name:
            cast_by_id[cid] = name
    names: dict[str, str] = {}
    staging = plan.get("staging") if isinstance(plan.get("staging"), dict) else {}
    for scene in _list(staging.get("scenes")):
        if not isinstance(scene, dict):
            continue
        for entity in _list(scene.get("entities")):
            if not isinstance(entity, dict):
                continue
            eid = _text(entity.get("id"))
            if not eid:
                continue
            cast_id = _text(entity.get("cast_id"))
            label = _text(entity.get("label"))
            if cast_id and cast_id in cast_by_id:
                names[eid] = cast_by_id[cast_id]
            elif label:
                names[eid] = label[:80]
            else:
                names[eid] = eid
    for cid, name in cast_by_id.items():
        names.setdefault(cid, name)
    return names


def _scene_for(plan: dict[str, Any], shot: dict[str, Any]) -> dict[str, Any]:
    staging = plan.get("staging") if isinstance(plan.get("staging"), dict) else {}
    scenes = [scene for scene in _list(staging.get("scenes")) if isinstance(scene, dict)]
    stage = shot.get("stage") if isinstance(shot.get("stage"), dict) else {}
    scene_id = _text(stage.get("scene_id"))
    shot_id = _text(shot.get("id"))
    for scene in scenes:
        if scene_id and _text(scene.get("id")) == scene_id:
            return scene
    for scene in scenes:
        shot_ids = [_text(item) for item in _list(scene.get("shot_ids"))]
        if shot_id and shot_id in shot_ids:
            return scene
    if len(scenes) == 1:
        return scenes[0]
    return {}


def _relations_for(plan: dict[str, Any], shot: dict[str, Any]) -> list[dict[str, Any]]:
    stage = shot.get("stage") if isinstance(shot.get("stage"), dict) else {}
    own = [row for row in _list(stage.get("relations")) if isinstance(row, dict)]
    if own:
        return own
    scene = _scene_for(plan, shot)
    return [row for row in _list(scene.get("relations")) if isinstance(row, dict)]


def _place_words(block: dict[str, Any]) -> str:
    bits = [_words(block.get("x")), _words(block.get("depth"))]
    facing = _token(block.get("facing"))
    look = _token(block.get("look"))
    if look and look != facing:
        bits.append(f"looking {_words(look)}")
    return ", ".join(bit for bit in bits if bit)


def _relation_phrase(
    entity_id: str,
    relations: list[dict[str, Any]],
    names: dict[str, str],
    depth: str,
) -> str:
    for rel in relations:
        if _text(rel.get("a")) != entity_id:
            continue
        other_id = _text(rel.get("b"))
        other = names.get(other_id, other_id)
        word = _words(rel.get("rel"))
        if not word or not other:
            continue
        gap = _words(rel.get("gap"))
        if gap and gap != depth:
            return f"{gap} {word} {other}"
        return f"{word} {other}"
    return ""


def _words(value: Any) -> str:
    key = _token(value)
    if not key:
        return ""
    if key in _WORD_ALIASES:
        return _WORD_ALIASES[key]
    return key.replace("_", " ")


def _token(value: Any) -> str:
    return _text(value).lower().replace("-", "_").replace(" ", "_")


def _join_names(names: list[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for name in names:
        cleaned = name.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    while unique and len(", ".join(unique)) > 400:
        unique.pop()
    return ", ".join(unique)


def _structured_cast(cast: Any) -> list[dict[str, str]]:
    if not isinstance(cast, list):
        return []
    used: set[str] = set()
    rows: list[dict[str, str]] = []
    for item in cast:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))[:80]
        if not name:
            continue
        role = _text(item.get("role")).lower() or "character"
        if role not in _CAST_ROLES:
            role = "character"
        supplied = _text(item.get("id"))
        if supplied and _CAST_ID.fullmatch(supplied) and supplied.lower() not in used:
            cid = supplied
            used.add(supplied.lower())
        else:
            cid = _slug_id(name, used)
        rows.append(
            {
                "id": cid,
                "name": name,
                "role": role,
                "markers": _text(item.get("markers"))[:400],
                "image_path": _safe_image_path(item.get("image_path")),
            }
        )
        if len(rows) >= _MAX_CAST:
            break
    return rows


def _cast_from_notes(notes: str) -> list[dict[str, str]]:
    text = (notes or "").strip()
    if not text:
        return []
    parsed: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        row = line.strip().lstrip("-*").strip()
        if not row:
            continue
        role = "character"
        lower = row.lower()
        for prefix, kind in (("character:", "character"), ("prop:", "prop"), ("location:", "location")):
            if lower.startswith(prefix):
                role = kind
                row = row.split(":", 1)[1].strip()
                lower = row.lower()
                break
        if not row:
            continue
        if any(sep in row for sep in ("—", "–", " - ", ":")):
            name, markers = _split_cast_line(row)
            parsed.append((name, role, markers))
            continue
        if "," in row and len(row) < 180 and not row.endswith("."):
            for part in row.split(","):
                parsed.append((part.strip(), role, ""))
            continue
        parsed.append((row, role, ""))
    used: set[str] = set()
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for name, role, markers in parsed:
        cleaned = name.strip(" .")[:80]
        key = cleaned.lower()
        if not cleaned or key in _SKIP_CAST_NAMES or key in seen_names:
            continue
        seen_names.add(key)
        rows.append(
            {
                "id": _slug_id(cleaned, used),
                "name": cleaned,
                "role": role if role in _CAST_ROLES else "character",
                "markers": markers.strip()[:400],
                "image_path": "",
            }
        )
        if len(rows) >= _MAX_CAST:
            break
    return rows


def _split_cast_line(row: str) -> tuple[str, str]:
    for sep in ("—", "–", " - "):
        if sep in row:
            name, markers = row.split(sep, 1)
            return name.strip(), markers.strip()
    if ":" in row:
        name, markers = row.split(":", 1)
        return name.strip(), markers.strip()
    return row.strip(), ""


def _cast_section(prompt: str) -> str:
    lines = (prompt or "").splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        match = re.fullmatch(r"cast\s*:\s*(.*)", stripped, flags=re.IGNORECASE)
        if match:
            inline = match.group(1).strip()
            if inline:
                return inline
            return _following_cast_lines(lines, index + 1)
        if re.fullmatch(r"cast", stripped, flags=re.IGNORECASE):
            return _following_cast_lines(lines, index + 1)
    return ""


def _following_cast_lines(lines: list[str], start: int) -> str:
    kept: list[str] = []
    for line in lines[start:]:
        if not line.strip():
            break
        kept.append(line)
    return "\n".join(kept)


def _slug_id(name: str, used: set[str]) -> str:
    raw = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_")[:60]
    if not raw or not raw[0].isalnum():
        raw = f"c{raw}" if raw else "cast"
    candidate = raw[:64]
    number = 2
    while candidate.lower() in used or not _CAST_ID.fullmatch(candidate):
        suffix = f"_{number}"
        candidate = f"{raw[: 64 - len(suffix)]}{suffix}"
        number += 1
        if number > 100:
            break
    used.add(candidate.lower())
    return candidate


def _safe_image_path(value: Any) -> str:
    cleaned = _text(value).replace("\\", "/")
    if not cleaned or cleaned.startswith("/") or ".." in cleaned.split("/"):
        return ""
    return cleaned[:240]


def _clock(seconds: int) -> str:
    total = max(0, int(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []



_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_CAST_LINE = re.compile(r"^cast\s*:\s*", re.IGNORECASE)
_CAST_ONLY = re.compile(r"^cast\s*$", re.IGNORECASE)
_PLACES = ("left_third", "center", "right_third")
_MAX_SHOTS = 8


def local_plan(
    *,
    prompt: str,
    target_duration_sec: int,
    aspect_ratio: str | None = None,
    resolution: str | None = None,
    title: str | None = None,
    style_preset: str | None = None,
    cast: Any = None,
    cast_notes: str | None = None,
) -> dict[str, Any]:
    """Deterministic shot list. No model call. Staging is filled only from named cast."""
    raw = (prompt or "").strip()
    story = _story_without_cast(raw) or raw
    sentences = _sentences(story) or [story]
    duration = max(1, int(target_duration_sec))
    count = min(len(sentences), duration, _MAX_SHOTS)
    sentences = sentences[:count]
    durations = _split_duration(duration, count)
    named = cast_payload_for_plan(cast=cast, cast_notes=cast_notes or "", prompt=raw)
    shots: list[dict[str, Any]] = []
    for index, (sentence, seconds) in enumerate(zip(sentences, durations, strict=False)):
        if index == 0:
            beat = "setup"
        elif index == count - 1:
            beat = "button"
        else:
            beat = "turn"
        shots.append(
            {
                "id": f"s{index + 1}",
                "prompt_still": sentence,
                "prompt_motion": sentence,
                "duration_sec": seconds,
                "start_state": "",
                "end_state": "",
                "beat": beat,
            }
        )
    heading = _text(title) or _clip(sentences[0], 80)
    plan: dict[str, Any] = {
        "title": heading or "Quick episode",
        "logline": _clip(sentences[0], 400),
        "aspect_ratio": _text(aspect_ratio),
        "resolution": _text(resolution),
        "look_bible": {},
        "beat_map": _beat_map(shots),
        "cast": named,
        "shots": shots,
        "lock_staging": True,
    }
    preset = _text(style_preset)
    if preset:
        plan["style_preset"] = preset
    if named:
        _attach_local_staging(plan)
    return plan


def _sentences(text: str) -> list[str]:
    parts = [part.strip(" \t-•*") for part in _SENTENCE.split(text or "")]
    return [part for part in parts if part]


def _clip(value: str, limit: int) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _story_without_cast(prompt: str) -> str:
    kept: list[str] = []
    skipping = False
    for line in (prompt or "").splitlines():
        stripped = line.strip()
        if not skipping and (_CAST_ONLY.match(stripped) or _CAST_LINE.match(stripped)):
            skipping = True
            continue
        if skipping:
            if not stripped:
                skipping = False
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _split_duration(total: int, count: int) -> list[int]:
    count = max(1, count)
    base = total // count
    extra = total % count
    return [base + (1 if index < extra else 0) for index in range(count)]


def _beat_map(shots: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for shot in shots:
        role = _text(shot.get("beat")).lower()
        if not role or role in seen:
            continue
        seen.add(role)
        rows.append({"role": role, "summary": role})
    return rows


def _attach_local_staging(plan: dict[str, Any]) -> None:
    """Place named cast on one scene so who-is-where has a line. No invented relations."""
    cast = [row for row in _list(plan.get("cast")) if isinstance(row, dict) and _text(row.get("name"))]
    if not cast:
        return
    shots = [row for row in _list(plan.get("shots")) if isinstance(row, dict)]
    entities = []
    blocks = []
    for index, item in enumerate(cast):
        cid = _text(item.get("id")) or _text(item.get("name"))
        role = _text(item.get("role")).lower() or "character"
        entities.append(
            {
                "id": cid,
                "label": _text(item.get("name")),
                "kind": role,
                "cast_id": cid,
                "count": 1,
            }
        )
        if role == "location":
            continue
        blocks.append(
            {
                "id": cid,
                "x": _PLACES[index % len(_PLACES)],
                "depth": "mid",
                "facing": "screen_right",
                "visible": True,
            }
        )
    scene = {
        "id": "sc1",
        "shot_ids": [_text(shot.get("id")) for shot in shots if _text(shot.get("id"))],
        "entities": entities,
        "relations": [],
    }
    plan["staging"] = {"scenes": [scene]}
    if not blocks:
        return
    for shot in shots:
        shot["stage"] = {
            "scene_id": "sc1",
            "camera_side": "same",
            "start": copy.deepcopy(blocks),
        }


