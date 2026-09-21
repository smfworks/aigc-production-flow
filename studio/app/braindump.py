"""Brain dump → draft pack skeleton.

Optional OpenAI-compatible endpoint (`STUDIO_LLM_BASE_URL`). When that env is unset,
expansion is a deterministic template over the dump text. This module never claims
a model ran unless the HTTP call returned a usable JSON skeleton.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .blankpack import (
    DEFAULT_CHARACTER_FORBIDDEN,
    DEFAULT_PROP_FORBIDDEN,
    DEFAULT_STILL_CANVAS,
    empty_pack,
    empty_prop_fields,
)
from .config import Settings, get_settings
from .gates import all_gates_green

_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_LABELED = re.compile(
    r"^(character|lead|who|hero|presenter|prop|object|item)\s*[:\-]\s*(.+)$",
    re.IGNORECASE,
)
NO_MODEL_NOTE = (
    "No model configured (STUDIO_LLM_BASE_URL unset). "
    "Deterministic template expansion from the dump text. Not generate-ready."
)
FAILED_MODEL_NOTE = (
    "STUDIO_LLM_BASE_URL is set, but the call failed or did not return a skeleton. "
    "Deterministic template expansion was used. No model output was applied."
)
RAN_MODEL_NOTE = (
    "Draft skeleton from the configured local/OpenAI-compatible endpoint. "
    "Look stays blank. Gates stay red until filled. Not generate-ready."
)


def _sentences(text: str) -> list[str]:
    parts = [part.strip(" \t-•*") for part in _SENTENCE.split(text or "")]
    return [part for part in parts if part]


def _clip(value: str, limit: int) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _labeled(text: str, kinds: set[str]) -> list[str]:
    found: list[str] = []
    for line in (text or "").splitlines():
        match = _LABELED.match(line.strip())
        if not match:
            continue
        kind = match.group(1).lower()
        if kind not in kinds:
            continue
        name = _clip(match.group(2), 80)
        if name and name not in found:
            found.append(name)
    return found


def _character(name: str, note: str) -> dict[str, Any]:
    return {
        "id": _fresh_id(),
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
        "distinguishingMarks": "",
        "eraForbiddenModern": "",
        "lockParagraph": "",
        "forbidden": DEFAULT_CHARACTER_FORBIDDEN,
        "motionNotes": note,
    }


def _prop(name: str) -> dict[str, Any]:
    return {
        "id": _fresh_id(),
        "name": name,
        "stillFile": "",
        "stillSource": "",
        "stillCanvas": DEFAULT_STILL_CANVAS,
        "fields": empty_prop_fields(),
        "lockParagraph": "",
        "forbidden": DEFAULT_PROP_FORBIDDEN,
    }


def _fresh_id() -> str:
    import uuid

    return str(uuid.uuid4())


def _map_row(beat: str) -> dict[str, str]:
    return {"id": _fresh_id(), "clock": "", "beat": _clip(beat, 180), "energy": ""}


def _apply_skeleton(pack: dict[str, Any], *, title: str, log_line: str, beats: list[str], characters: list[str], props: list[str], duration: str, note: str) -> None:
    pack["title"] = _clip(title, 120) or pack.get("title") or "Untitled draft"
    pack["logLine"] = _clip(log_line, 400)
    pack["durationTarget"] = _clip(duration, 40)
    pack["songNarrativeClock"] = "draft beats from the brain dump — clocks not locked"
    pack["audioPath"] = ""
    pack["speech"] = ""
    pack["look"]["styleLine"] = ""
    if beats:
        pack["map"] = [_map_row(beat) for beat in beats[:6]]
    names = characters[:4] or ["lead"]
    pack["characters"] = [
        _character(name, "Placeholder from the brain dump. Lock paragraph is empty — not generate-ready.")
        for name in names
    ]
    prop_names = props[:4] or ["prop"]
    pack["props"] = [_prop(name) for name in prop_names]
    pack["entitySchedule"] = [
        {
            "id": _fresh_id(),
            "entityKind": "character" if index == 0 else "prop",
            "entityName": name,
            "take": "",
            "windows": "",
            "identityHold": True,
        }
        for index, name in enumerate([*names[:1], *prop_names[:1]])
    ]
    # Edit rows stay join-empty so the storyboard gate cannot go green.
    pack["editList"] = [
        {
            "id": _fresh_id(),
            "songT": "",
            "durS": "10.125",
            "join": "",
            "take": "A",
            "locationGrade": "",
            "cameraVerb": "",
            "cameraAmplitude": "",
            "cameraSpeed": "",
            "action": _clip(beat, 180),
            "hold": "",
            "notes": "Draft beat. Not a camera row.",
            "entities": ", ".join(names[:1] + prop_names[:1]),
        }
        for beat in (beats[:4] or ["draft beat"])
    ]
    pack["studioMeta"]["note"] = note


def deterministic_hints(text: str, title: str = "") -> dict[str, Any]:
    sentences = _sentences(text)
    first = sentences[0] if sentences else ""
    beats = sentences[1:6] or ([first] if first else ["draft beat"])
    characters = _labeled(text, {"character", "lead", "who", "hero", "presenter"})
    props = _labeled(text, {"prop", "object", "item"})
    guessed = _clip(title or first or "Untitled draft", 80)
    return {
        "title": guessed,
        "logLine": _clip(first, 400),
        "beats": [_clip(beat, 180) for beat in beats],
        "characters": characters,
        "props": props,
        "durationTarget": "",
    }


def _extract_json(content: str) -> str:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def llm_hints(text: str, settings: Settings) -> dict[str, Any] | None:
    base = (settings.llm_base_url or "").strip().rstrip("/")
    if not base:
        return None
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    model = (settings.llm_model or "").strip() or "local"
    headers = {"Content-Type": "application/json"}
    key = (settings.llm_api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return only a JSON object with keys title, logLine, beats (array of beat strings, "
                    "not shots), characters (array of names), props (array of names), durationTarget. "
                    "Do not invent measurements, lock paragraphs, a look style line, an audio path, "
                    "or camera verbs. This is a draft skeleton, not a generate."
                ),
            },
            {"role": "user", "content": (text or "")[:8000]},
        ],
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(_extract_json(str(content)))
    except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    beats = parsed.get("beats") if isinstance(parsed.get("beats"), list) else []
    characters = parsed.get("characters") if isinstance(parsed.get("characters"), list) else []
    props = parsed.get("props") if isinstance(parsed.get("props"), list) else []
    return {
        "title": str(parsed.get("title") or ""),
        "logLine": str(parsed.get("logLine") or ""),
        "beats": [str(item) for item in beats if str(item).strip()][:6],
        "characters": [str(item) for item in characters if str(item).strip()][:4],
        "props": [str(item) for item in props if str(item).strip()][:4],
        "durationTarget": str(parsed.get("durationTarget") or ""),
    }


def draft_from_dump(text: str, *, title: str = "", settings: Settings | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (pack, honesty). Look style line is always blank. generate_ready is always false."""
    cfg = settings or get_settings()
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Brain dump is empty.")
    fallback = deterministic_hints(raw, title)
    configured = bool((cfg.llm_base_url or "").strip())
    model_name = (cfg.llm_model or "").strip() or "local"
    used = llm_hints(raw, cfg) if configured else None
    if configured and used:
        hints = {
            "title": used["title"] or fallback["title"],
            "logLine": used["logLine"] or fallback["logLine"],
            "beats": used["beats"] or fallback["beats"],
            "characters": used["characters"] or fallback["characters"],
            "props": used["props"] or fallback["props"],
            "durationTarget": used["durationTarget"],
        }
        honesty = {
            "model_ran": True,
            "model": model_name,
            "source": "brain-dump",
            "note": RAN_MODEL_NOTE,
        }
    elif configured:
        hints = fallback
        honesty = {
            "model_ran": False,
            "model": "none",
            "source": "brain-dump",
            "note": FAILED_MODEL_NOTE,
        }
    else:
        hints = fallback
        honesty = {
            "model_ran": False,
            "model": "none",
            "source": "brain-dump",
            "note": NO_MODEL_NOTE,
        }
    pack = empty_pack(str(hints["title"]), source="brain-dump", note=honesty["note"])
    _apply_skeleton(
        pack,
        title=str(hints["title"]),
        log_line=str(hints["logLine"]),
        beats=list(hints["beats"]),
        characters=list(hints["characters"]),
        props=list(hints["props"]),
        duration=str(hints["durationTarget"] or ""),
        note=honesty["note"],
    )
    pack["studioMeta"] = {
        "status": "draft",
        "source": "brain-dump",
        "model": honesty["model"],
        "model_ran": honesty["model_ran"],
        "generate_ready": False,
        "note": honesty["note"],
    }
    # A dump must not become a generate. Blank the look even if a caller filled it.
    pack["look"]["styleLine"] = ""
    if all_gates_green(pack):
        pack["audioPath"] = ""
        pack["speech"] = ""
    honesty["generate_ready"] = False
    honesty["all_gates_green"] = all_gates_green(pack)
    return pack, honesty
