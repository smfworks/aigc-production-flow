"""Blank capture packs created inside Studio. Look stays blank. Gates stay red."""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from typing import Any

from .packzip import slugify

DEFAULT_STILL_CANVAS = "1344×768"
DEFAULT_GLOBAL_FORBIDDEN = (
    "no plate armor, no horned helms, no on-screen lettering, no modern clothing"
)
DEFAULT_CHARACTER_FORBIDDEN = "glasses, plate, horns, logos, on-screen text"
DEFAULT_PROP_FORBIDDEN = "bearded blade, double bit, horns, chrome, leather wrap unless listed"
DEFAULT_LOOK_FORBIDDEN = "no cars, no text, no logos, no modern clothing"
DEFAULT_SMOKE_NOTES = (
    "One hop-1 per take — I2VA if a plate exists, else T2V — watched before hopping. "
    "continue = plate on hop-1 only; hop 2+ is Motion-Context latent (no new Qwen still). "
    "cut / fadeblack = new plate → I2VA hop-1."
)

PROP_UNITS = {
    "overallLength": "cm",
    "haftLength": "cm",
    "headMass": "g",
    "edgeWidth": "cm",
    "headShape": "—",
    "poll": "—",
    "eye": "—",
    "socket": "—",
    "haftWoodColor": "—",
    "bindings": "—",
    "decoration": "—",
    "wearFinish": "—",
}


def _id() -> str:
    return str(uuid.uuid4())


def _measurement(unit: str) -> dict[str, str]:
    return {"value": "", "unit": unit, "source": ""}


def empty_prop_fields() -> dict[str, dict[str, str]]:
    return {key: _measurement(unit) for key, unit in PROP_UNITS.items()}


def studio_meta(*, source: str, note: str, model: str = "none", model_ran: bool = False) -> dict[str, Any]:
    return {
        "status": "draft",
        "source": source,
        "model": model,
        "model_ran": bool(model_ran),
        "generate_ready": False,
        "note": note,
    }


def empty_pack(title: str = "", *, source: str = "blank", note: str | None = None) -> dict[str, Any]:
    """Same shape as the pack builder `emptyPack()`. Look style line is blank."""
    return {
        "title": title or "",
        "logLine": "",
        "durationTarget": "",
        "songNarrativeClock": "",
        "audioPath": "",
        "speech": "",
        "forbiddenGlobal": DEFAULT_GLOBAL_FORBIDDEN,
        "map": [{"id": _id(), "clock": "", "beat": "", "energy": ""}],
        "takes": [
            {
                "id": _id(),
                "take": "A",
                "location": "",
                "grade": "",
                "windows": "",
                "prefix": "",
                "hop1Seed": "",
                "hop1Mode": "",
                "hop1Plate": "",
                "hop1Planned": False,
                "watched": False,
            }
        ],
        "editList": [
            {
                "id": _id(),
                "songT": "",
                "durS": "10.125",
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
        ],
        "characters": [
            {
                "id": _id(),
                "name": "",
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
                "motionNotes": "",
            }
        ],
        "props": [
            {
                "id": _id(),
                "name": "",
                "stillFile": "",
                "stillSource": "",
                "stillCanvas": DEFAULT_STILL_CANVAS,
                "fields": empty_prop_fields(),
                "lockParagraph": "",
                "forbidden": DEFAULT_PROP_FORBIDDEN,
            }
        ],
        "look": {
            "styleLine": "",
            "paletteGrade": "",
            "era": "",
            "lensGrain": "",
            "extrasForbidden": DEFAULT_LOOK_FORBIDDEN,
        },
        "stills": [
            {
                "id": _id(),
                "entity": "",
                "role": "",
                "source": "",
                "canvas": DEFAULT_STILL_CANVAS,
                "file": "",
                "conditions": "",
                "lookLock": "",
                "lockFromStill": "",
                "forbidden": "",
                "notes": "",
            }
        ],
        "entitySchedule": [
            {
                "id": _id(),
                "entityKind": "",
                "entityName": "",
                "take": "",
                "windows": "all",
                "identityHold": True,
            }
        ],
        "smokeNotes": DEFAULT_SMOKE_NOTES,
        "continuityRows": [
            {
                "id": _id(),
                "take": "",
                "hop": "",
                "seed": "",
                "wallS": "",
                "peakC": "",
                "ffprobe": "",
                "stillVsLock": "",
                "circleNg": "",
                "why": "",
            }
        ],
        "polaroidPath": "",
        "studioMeta": studio_meta(
            source=source,
            model="none",
            model_ran=False,
            note=note
            or (
                "Blank pack created in Studio. Look is blank. Gates stay red until filled. "
                "Not generate-ready. No model ran."
            ),
        ),
    }


def pack_zip_bytes(pack: dict[str, Any]) -> bytes:
    """Collaboration zip with pack.json. Not an MP4 and not a generate."""
    title = str(pack.get("title") or "untitled-pack")
    folder = f"packs/{slugify(title)}"
    body = json.dumps({"v": 2, "pack": pack}, indent=2, ensure_ascii=False)
    readme = (
        "# Draft pack\n\n"
        "Created in AIGC Studio. This zip is the collaboration contract (markdown/JSON), "
        "not a generate and not an MP4.\n\n"
        "Gates are red until the four stages are filled. `generate-ok` is a separate review stamp.\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{folder}/pack.json", body)
        archive.writestr(f"{folder}/README.md", readme)
    return buf.getvalue()
