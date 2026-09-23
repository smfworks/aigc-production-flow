"""Draft pack from Create wizard answers. Gates stay red. No model is claimed."""

from __future__ import annotations

import re
import uuid
from typing import Any

from .adapters.registry import resolve_adapter_name
from .agentbrief import _label
from .blankpack import empty_pack, empty_prop_fields, studio_meta
from .config import get_settings
from .director import normalize_scope, normalize_stored_tree, public_director, scope_note, tree_for

FORMATS = ("short-drama", "vertical-ad", "music-video", "custom")
FORMAT_LABELS = {
    "short-drama": "short drama",
    "vertical-ad": "vertical ad",
    "music-video": "music video",
    "custom": "custom",
}
WIZARD_NOTE = (
    "Create wizard draft. Gates stay red. No model ran. Not generate-ready. "
    "Cast rows are identity drafts, not approvals."
)


def _id() -> str:
    return str(uuid.uuid4())


def _clean_name(raw: str) -> str:
    text = (raw or "").strip()
    for sep in ("—", "–", " - ", ":"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            break
    return text.strip(" .")[:80]


def parse_people(cast_notes: str) -> list[dict[str, str]]:
    notes = (cast_notes or "").strip()
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        cleaned = _clean_name(name)
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen or key in {"character", "prop", "the", "a", "an"}:
            return
        seen.add(key)
        found.append({"name": cleaned, "notes": notes})

    for line in notes.splitlines():
        row = line.strip().lstrip("-*").strip()
        if not row:
            continue
        lower = row.lower()
        if lower.startswith("prop:"):
            continue
        if lower.startswith("character:"):
            add(row.split(":", 1)[1])
            continue
        # "Mara — lead, tired eyes" is one person. A comma list is only
        # "Mara, Jonah" when the line has no role dash.
        if any(sep in row for sep in ("—", "–", " - ")):
            add(row)
            continue
        if "," in row and len(row) < 180 and not row.endswith("."):
            for part in row.split(","):
                add(part)
            continue
        add(row)
    if not found:
        found.append(
            {
                "name": "lead",
                "notes": notes or "No cast named. Draft only — not approved.",
            }
        )
    return found


def parse_props(*blobs: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for blob in blobs:
        for line in (blob or "").splitlines():
            row = line.strip()
            if not row.lower().startswith("prop:"):
                continue
            name = _clean_name(row.split(":", 1)[1])
            key = name.lower()
            if name and key not in seen:
                seen.add(key)
                names.append(name)
    return names


def _sentences(prompt: str) -> list[str]:
    text = (prompt or "").strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    rows = [part.strip() for part in parts if part.strip()]
    return rows or ([text] if text else ["Draft beat"])


def _first_sentence(prompt: str) -> str:
    return _sentences(prompt)[0][:240]


def _title(prompt: str) -> str:
    sentence = _first_sentence(prompt).rstrip(".!? ")
    return (sentence or "Untitled")[:80]


def _bounded_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def _bounded_float(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def audio_path_from_notes(notes: str) -> str:
    text = (notes or "").strip()
    low = text.lower()
    if low in {"n/a", "na", "mute"}:
        return "N/A"
    if low == "silence":
        return "silence"
    if low in {"prompt score", "prompt-score"}:
        return "prompt score"
    if low.startswith("path:"):
        return text.split(":", 1)[1].strip()[:300]
    return ""


def _character(person: dict[str, str]) -> dict[str, Any]:
    return {
        "id": _id(),
        "name": person["name"],
        "stillFile": "",
        "stillSource": "",
        "stillCanvas": "1344×768",
        "speakerId": "none",
        "ageSex": "",
        "faceHairBeard": "",
        "body": "",
        "wardrobe": "",
        "footwear": "",
        "distinguishingMarks": "",
        "eraForbiddenModern": "",
        "lockParagraph": "",
        "forbidden": "glasses, plate, horns, logos, on-screen text",
        "motionNotes": (person.get("notes") or "")[:500],
    }


def _prop(name: str) -> dict[str, Any]:
    return {
        "id": _id(),
        "name": name,
        "stillFile": "",
        "stillSource": "",
        "stillCanvas": "1344×768",
        "fields": empty_prop_fields(),
        "lockParagraph": "",
        "forbidden": "bearded blade, double bit, horns, chrome, leather wrap unless listed",
    }


def _take(letter: str, tone: str) -> dict[str, Any]:
    return {
        "id": _id(),
        "take": letter,
        "location": "",
        "grade": (tone or "")[:80],
        "windows": "",
        "prefix": "",
        "hop1Seed": "",
        "hop1Mode": "",
        "hop1Plate": "",
        "hop1Planned": False,
        "watched": False,
    }


def _edit_row(index: int, take: str, join: str, beat: str) -> dict[str, Any]:
    return {
        "id": _id(),
        "songT": "",
        "durS": "10.125",
        "join": join,
        "take": take,
        "locationGrade": "",
        "cameraVerb": "",
        "cameraAmplitude": "",
        "cameraSpeed": "",
        "action": beat[:400],
        "hold": "",
        "notes": "",
        "entities": "",
    }


def _plate(index: int, take: str) -> dict[str, Any]:
    return {
        "id": _id(),
        "entity": f"window {index + 1}",
        "role": "hop-1 plate",
        "source": "",
        "canvas": "1344×768",
        "file": "",
        "conditions": "",
        "lookLock": "",
        "lockFromStill": "",
        "forbidden": "",
        "notes": f"Draft plate for take {take}. Not a generated still.",
    }


def _letters(count: int) -> list[str]:
    rows = []
    for index in range(count):
        if index < 26:
            rows.append(chr(ord("A") + index))
        else:
            rows.append(f"T{index + 1}")
    return rows


def normalize_answers(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    fmt = str(src.get("format") or "").strip().lower()
    if fmt not in FORMATS:
        fmt = ""
    still_pref = str(src.get("still_pref") or "comfy-qwen").strip().lower()
    clip_pref = str(src.get("clip_pref") or "comfy-h3").strip().lower()
    if still_pref not in {"comfy-qwen", "stub"}:
        still_pref = "comfy-qwen"
    if clip_pref not in {"comfy-h3", "stub"}:
        clip_pref = "comfy-h3"
    shot_count = _bounded_int(src.get("shot_count"), 0, 0, 24)
    length = src.get("target_length_s")
    body = {
        "prompt": str(src.get("prompt") or "").strip()[:4000],
        "format": fmt,
        "shot_count": shot_count,
        "target_length_s": length if length not in {None, ""} else "",
        "tone": str(src.get("tone") or "").strip()[:500],
        "look": str(src.get("look") or "").strip()[:500],
        "cast_notes": str(src.get("cast_notes") or "").strip()[:4000],
        "audio_notes": str(src.get("audio_notes") or "").strip()[:2000],
        "still_pref": still_pref,
        "clip_pref": clip_pref,
    }
    body.update(normalize_scope(src))
    body["task_tree"] = normalize_stored_tree(src.get("task_tree"), body)
    body["clarify_ack"] = bool(src.get("clarify_ack"))
    gaps = src.get("clarify_gaps")
    body["clarify_gaps"] = [str(item) for item in gaps][:8] if isinstance(gaps, list) else []
    return body


def missing_answers(answers: dict[str, Any]) -> list[str]:
    missing = []
    if not str(answers.get("prompt") or "").strip():
        missing.append("prompt")
    if answers.get("format") not in FORMATS:
        missing.append("format")
    shots = int(answers.get("shot_count") or 0)
    length = answers.get("target_length_s")
    if shots < 1 and length in {None, "", 0}:
        missing.append("length")
    return missing


def pack_from_answers(
    raw: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    answers = normalize_answers(raw)
    answers["task_tree"] = tree_for(answers)
    prompt = answers["prompt"]
    fmt = answers["format"] or "custom"
    shot_count = int(answers["shot_count"] or 0)
    if shot_count < 1:
        length_guess = _bounded_float(answers.get("target_length_s"), 30.0, 1.0, 600.0)
        shot_count = _bounded_int(round(length_guess / 10.125), 1, 1, 24)
    else:
        shot_count = _bounded_int(shot_count, 1, 1, 24)
    length_s = _bounded_float(answers.get("target_length_s"), round(shot_count * 10.125, 3), 1.0, 600.0)
    tone = answers["tone"]
    look = answers["look"]
    people = parse_people(answers["cast_notes"])
    props = parse_props(answers["cast_notes"], prompt)
    label = FORMAT_LABELS.get(fmt, "custom")
    one_take = fmt == "music-video"
    letters = ["A"] * shot_count if one_take else _letters(shot_count)
    beats = _sentences(prompt)
    pack = empty_pack(str(_title(prompt)), source="wizard", note=WIZARD_NOTE)
    pack["logLine"] = _first_sentence(prompt)
    pack["durationTarget"] = f"{length_s:g}s · {shot_count} windows"
    pack["songNarrativeClock"] = f"{label} — draft beats, clocks not locked"
    pack["speech"] = answers["audio_notes"]
    pack["audioPath"] = audio_path_from_notes(answers["audio_notes"])
    pack["look"]["styleLine"] = look
    pack["look"]["paletteGrade"] = tone
    pack["map"] = [
        {"id": _id(), "clock": "", "beat": beat[:400], "energy": ""}
        for beat in beats[: max(shot_count, 1)]
    ] or pack["map"]
    pack["characters"] = [_character(person) for person in people]
    if props:
        pack["props"] = [_prop(name) for name in props]
    else:
        pack["props"] = [_prop("")]
    pack["takes"] = [_take(letter, tone) for letter in (["A"] if one_take else letters)]
    # de-dupe takes when music video reused A
    if one_take:
        pack["takes"] = [_take("A", tone)]
    rows = []
    plates = []
    for index in range(shot_count):
        take = letters[index]
        join = "cut" if index == 0 or not one_take else "continue"
        if one_take and index == 0:
            join = "cut"
        beat = beats[index] if index < len(beats) else beats[-1]
        rows.append(_edit_row(index, take, join, beat))
        plates.append(_plate(index, take))
    pack["editList"] = rows
    pack["stills"] = plates
    pack["entitySchedule"] = [
        {
            "id": _id(),
            "entityKind": "character",
            "entityName": person["name"],
            "take": "A" if one_take else "",
            "windows": "all",
            "identityHold": True,
        }
        for person in people
    ]
    meta = studio_meta(source="wizard", note=WIZARD_NOTE)
    meta["format"] = fmt
    meta["wizard"] = {
        "format": fmt,
        "shot_count": shot_count,
        "target_length_s": length_s,
        "still_pref": answers["still_pref"],
        "clip_pref": answers["clip_pref"],
    }
    scope = normalize_scope(answers)
    meta["notes"] = scope_note(scope)
    pack["studioMeta"] = meta
    director = public_director(
        answers,
        pack=pack,
        approved_sheets=0,
        draft_sheets=len(people),
        signed_off=False,
    )
    meta["director"] = director
    pack["studioMeta"] = meta
    honesty = {
        "model_ran": False,
        "model": "none",
        "source": "wizard",
        "note": WIZARD_NOTE,
        "generate_ready": False,
    }
    return pack, honesty, people, answers


def engine_report(raw: dict[str, Any] | None, project=None) -> dict[str, Any]:
    answers = normalize_answers(raw)
    cfg = get_settings()
    still_pref = answers["still_pref"]
    clip_pref = answers["clip_pref"]
    still_resolved = resolve_adapter_name("still-sheet", cfg, requested=still_pref, project=project)
    clip_resolved = resolve_adapter_name("clip-hop1", cfg, requested=clip_pref, project=project)
    still_label = _label(still_pref, still_resolved)
    clip_label = _label(clip_pref, clip_resolved)
    still_live = still_resolved == still_pref and still_resolved != "stub"
    clip_live = clip_resolved == clip_pref and clip_resolved != "stub"
    if still_live or clip_live:
        note = (
            "A lane on this desk resolves live. The wizard still does not call Comfy. "
            "Send to Hermes writes the brief. Live clip jobs wait until gates are green."
        )
    else:
        note = (
            f"Stills prefer {still_pref}. Clips prefer {clip_pref}. "
            f"On this desk they resolve to {still_label} and {clip_label}. "
            "The handoff tells Hermes to use stub receipts, or to refuse a live generate. "
            "Comfy has not been called."
        )
    return {
        "still_preference": still_pref,
        "clip_preference": clip_pref,
        "still_resolved": still_resolved,
        "clip_resolved": clip_resolved,
        "still_label": still_label,
        "clip_label": clip_label,
        "still_live": still_live,
        "clip_live": clip_live,
        "called_comfy": False,
        "note": note,
    }
