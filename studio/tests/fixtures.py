"""Shared capture-pack fixtures for studio API tests."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

PROP_KEYS = (
    "overallLength",
    "haftLength",
    "headMass",
    "edgeWidth",
    "headShape",
    "poll",
    "eye",
    "socket",
    "haftWoodColor",
    "bindings",
    "decoration",
    "wearFinish",
)


def _fields(**overrides: dict[str, str]) -> dict[str, dict[str, str]]:
    fields = {
        key: {"value": "1", "unit": "cm", "source": "pin"} for key in PROP_KEYS
    }
    fields["headMass"] = {"value": "600", "unit": "g", "source": "lyric"}
    fields["headShape"] = {"value": "wedge", "unit": "—", "source": "pin"}
    fields["poll"] = {"value": "square", "unit": "—", "source": "lyric"}
    fields["eye"] = {"value": "teardrop", "unit": "—", "source": "lyric"}
    fields["socket"] = {"value": "tapered", "unit": "—", "source": "pin"}
    fields["haftWoodColor"] = {"value": "ash", "unit": "—", "source": "pin"}
    fields["bindings"] = {"value": "none listed", "unit": "—", "source": "pin"}
    fields["decoration"] = {"value": "none listed", "unit": "—", "source": "pin"}
    fields["wearFinish"] = {"value": "forge scale", "unit": "—", "source": "pin"}
    fields["overallLength"] = {"value": "45", "unit": "cm", "source": "lyric"}
    fields["haftLength"] = {"value": "32", "unit": "cm", "source": "measured stand-in"}
    fields["edgeWidth"] = {"value": "10", "unit": "cm", "source": "lyric"}
    for key, value in overrides.items():
        fields[key] = value
    return fields


def empty_pack() -> dict[str, Any]:
    return {
        "title": "",
        "logLine": "",
        "durationTarget": "",
        "songNarrativeClock": "",
        "audioPath": "",
        "speech": "",
        "forbiddenGlobal": "no plate armor",
        "map": [{"id": "m1", "clock": "", "beat": "", "energy": ""}],
        "takes": [
            {
                "id": "t1",
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
                "id": "e1",
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
                "id": "c1",
                "name": "",
                "stillFile": "",
                "stillSource": "",
                "stillCanvas": "1344×768",
                "lockParagraph": "",
                "forbidden": "",
            }
        ],
        "props": [
            {
                "id": "p1",
                "name": "",
                "stillFile": "",
                "stillSource": "",
                "stillCanvas": "1344×768",
                "fields": {key: {"value": "", "unit": "cm", "source": ""} for key in PROP_KEYS},
                "lockParagraph": "",
                "forbidden": "",
            }
        ],
        "look": {"styleLine": ""},
        "stills": [],
        "entitySchedule": [],
        "smokeNotes": "",
        "continuityRows": [],
        "polaroidPath": "",
    }


def green_pack() -> dict[str, Any]:
    none_still = "none — no public likeness still in this example"
    none_plate = "none — no public plate; hop-1 stays T2V until a still conditions first_frame"
    return {
        "title": "Green fixture",
        "logLine": "A one-sentence log line that locks the piece.",
        "durationTarget": "1:00",
        "songNarrativeClock": "0:00 verse",
        "audioPath": "na-mute",
        "speech": "none",
        "forbiddenGlobal": "no plate armor",
        "map": [{"id": "m1", "clock": "0:00", "beat": "verse", "energy": "verse"}],
        "takes": [
            {
                "id": "t1",
                "take": "A",
                "location": "forge interior",
                "grade": "dusk / gold ember",
                "windows": "hop-1",
                "prefix": "green-a",
                "hop1Seed": "1",
                "hop1Mode": "t2v",
                "hop1Plate": none_plate,
                "hop1Planned": True,
                "watched": True,
            }
        ],
        "editList": [
            {
                "id": "e1",
                "songT": "0:00",
                "durS": "10.125",
                "join": "fadeblack",
                "take": "A",
                "locationGrade": "forge interior / dusk gold ember",
                "cameraVerb": "static",
                "cameraAmplitude": "none",
                "cameraSpeed": "hold",
                "action": "title overlay",
                "hold": "yes before fade",
                "notes": "",
                "entities": "smith, francisca",
            }
        ],
        "characters": [
            {
                "id": "c1",
                "name": "smith",
                "stillFile": none_still,
                "stillSource": "none",
                "stillCanvas": "1344×768",
                "lockParagraph": "Same face every hop.",
                "forbidden": "glasses, plate, horns",
            }
        ],
        "props": [
            {
                "id": "p1",
                "name": "francisca",
                "stillFile": "none — lyric numbers pinned before any browser call",
                "stillSource": "none",
                "stillCanvas": "1344×768",
                "fields": _fields(),
                "lockParagraph": "Francisca: overall 45 cm, head 600 g, 10 cm bite.",
                "forbidden": "bearded blade, double bit",
            }
        ],
        "look": {"styleLine": "Live-action, photoreal cinematic, crushed blacks."},
        "stills": [
            {
                "id": "s1",
                "entity": "smith",
                "role": "hop-1 plate",
                "source": "none",
                "canvas": "1344×768",
                "file": none_plate,
                "conditions": "hop-1 of take A",
                "lookLock": "",
                "lockFromStill": "",
                "forbidden": "",
                "notes": "Identity hold — public fixture, none + why.",
            },
            {
                "id": "s2",
                "entity": "francisca",
                "role": "hop-1 plate",
                "source": "none",
                "canvas": "1344×768",
                "file": none_plate,
                "conditions": "hop-1 of take A",
                "lookLock": "",
                "lockFromStill": "",
                "forbidden": "",
                "notes": "Identity hold — public fixture, none + why.",
            },
        ],
        "entitySchedule": [
            {
                "id": "sch1",
                "entityKind": "character",
                "entityName": "smith",
                "take": "A",
                "windows": "all",
                "identityHold": True,
            },
            {
                "id": "sch2",
                "entityKind": "prop",
                "entityName": "francisca",
                "take": "A",
                "windows": "all",
                "identityHold": True,
            },
        ],
        "smokeNotes": "One hop-1 per take, watched before hopping.",
        "continuityRows": [],
        "polaroidPath": "",
    }


def red_haft_pack() -> dict[str, Any]:
    pack = green_pack()
    pack["title"] = "Red haft fixture"
    pack["props"][0]["fields"]["haftLength"] = {
        "value": "none — not in public example",
        "unit": "cm",
        "source": "pin before GPU",
    }
    return pack


def pack_zip_bytes(pack: dict[str, Any], folder: str = "packs/fixture") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            f"{folder}/pack.json",
            json.dumps({"v": 2, "pack": pack}, indent=2),
        )
        archive.writestr(f"{folder}/README.md", f"# {pack.get('title') or 'pack'}\n")
    return buf.getvalue()
