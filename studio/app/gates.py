"""Gate honesty for pack.json stored on a PackRevision.

This is the studio spine's refuse-path, not a rewrite of the TypeScript builder.
The builder in `app/` remains the operator UI. Studio re-evaluates the same
README gates (nine plus entity-schedule and lock-diff) so `generate-ok` cannot
be stamped on a red pack.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

GATE_DEFS = [
    {"id": "log-line", "n": 1, "label": "Log line (one sentence)"},
    {"id": "map", "n": 2, "label": "Map (clock → beat, not shots)"},
    {"id": "edit-list", "n": 3, "label": "Edit list (join + one camera verb)"},
    {"id": "takes", "n": 4, "label": "Take cards (one location + one grade)"},
    {"id": "characters", "n": 5, "label": "Character cards (lock + forbidden)"},
    {"id": "props", "n": 6, "label": "Prop cards (units + still or none)"},
    {"id": "look", "n": 7, "label": "Look card (one style line)"},
    {"id": "audio", "n": 8, "label": "Audio path (exactly one)"},
    {"id": "smoke", "n": 9, "label": "Hop-1 smoke plan (I2VA if a plate exists, else T2V)"},
    {"id": "entity-schedule", "n": 10, "label": "Entity schedule (who persists on which windows)"},
    {"id": "lock-diff", "n": 11, "label": "Lock diff (same keywords every hop)"},
]

JOIN_TYPES = {"continue", "cut", "fadeblack"}
CAMERA_VERBS = {
    "push",
    "pull",
    "pan",
    "truck",
    "tilt",
    "pedestal",
    "arc",
    "track",
    "static",
    "shake",
}
AUDIO_PATHS = {"na-mute", "prompt-score", "silence"}
SPEECH_MODES = {"none", "finish-by-8s"}
ENERGY_VALUES = {"title", "verse", "chorus", "bridge", "outro"}
PROP_FIELD_KEYS = (
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
DEFAULT_STILL_CANVAS = "1344×768"
PIN_PLACEHOLDER = (
    "none",
    "tbd",
    "n/a",
    "n.a.",
    "na",
    "unknown",
    "unresolved",
    "unset",
    "todo",
)


def filled(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_placeholder_pin(value: str) -> bool:
    v = value.strip().replace("*", "").replace("_", "").lower()
    if not v:
        return True
    head = v.split()[0] if v.split() else v
    return head in PIN_PLACEHOLDER or v in PIN_PLACEHOLDER


def is_numeric_pin(value: Any) -> bool:
    if not isinstance(value, str) or is_placeholder_pin(value):
        return False
    return any(ch.isdigit() for ch in value)


def still_ok(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not v:
        return False
    if "wikipedia" in v.lower():
        return False
    if v.lower().startswith("none"):
        rest = v[4:].lstrip(" .:;,!—-")
        return any(ch.isalpha() for ch in rest)
    return True


def is_none_still(file: str) -> bool:
    return file.strip().lower().startswith("none")


def is_real_still_file(file: str) -> bool:
    return still_ok(file) and not is_none_still(file)


def hop1_mode_for_plate(plate_file: str) -> str:
    if not filled(plate_file):
        return ""
    if is_none_still(plate_file):
        return "t2v" if still_ok(plate_file) else ""
    return "i2va" if still_ok(plate_file) else ""


def normalize_canvas(canvas: str) -> str:
    return canvas.strip().replace("x", "×").replace("X", "×").replace("✕", "×").replace(" ", "")


def canvas_matches_hop1(canvas: str) -> bool:
    return normalize_canvas(canvas) == normalize_canvas(DEFAULT_STILL_CANVAS)


def canvas_looks_stretched(canvas: str) -> bool:
    return "1024" in canvas


def looks_like_shot(text: str) -> bool:
    low = text.lower()
    if "shot" in low and any(ch.isdigit() for ch in low):
        import re

        if re.search(r"\bshot\s*\d+\b", low):
            return True
    if any(token in low for token in ("ecu", "wide shot", "close-up", "close up", "medium shot", "long shot")):
        return True
    import re

    without_ms = re.sub(r"\d+\s*ms\b", " ", text, flags=re.I)
    return bool(re.search(r"(^|[\s,/])(cu|ms|ws)([\s,/]|$)", without_ms, flags=re.I))


def hold_ok_for_join(join: str, hold: str) -> bool:
    h = " ".join(hold.strip().lower().replace("*", "").split())
    if not h:
        return False
    no_hold = h in {"no", "no hold"}
    yes_hold = h in {"yes", "yes before fade", "yes before fadeblack"}
    if join in {"cut", "continue"}:
        return no_hold
    if join == "fadeblack":
        return yes_hold
    return False


def take_ok(join: str, take: str) -> bool:
    t = take.strip()
    if not t:
        return False
    if t in {"—", "-"}:
        return join == "cut"
    return True


def mentions_research(text: str) -> bool:
    import re

    return bool(re.search(r"\bresearch\b", text, flags=re.I))


def as_record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _gate(index: int, ok: bool, detail: str) -> dict[str, Any]:
    return {**GATE_DEFS[index], "ok": ok, "detail": detail}


def evaluate_log_line(pack: dict[str, Any]) -> dict[str, Any]:
    ok = filled(pack.get("logLine"))
    return _gate(0, ok, "One sentence locked." if ok else "Need a one-sentence log line.")


def evaluate_map(pack: dict[str, Any]) -> dict[str, Any]:
    rows = as_list(pack.get("map"))
    if not rows:
        return _gate(1, False, "Map is empty.")
    incomplete = [
        row
        for row in rows
        if not filled(as_record(row).get("clock"))
        or not filled(as_record(row).get("beat"))
        or as_record(row).get("energy", "").strip().lower() not in ENERGY_VALUES
    ]
    if incomplete:
        return _gate(
            1,
            False,
            f"{len(incomplete)} row(s) missing clock, beat, or energy (verse/chorus/bridge).",
        )
    shotty = [
        row
        for row in rows
        if looks_like_shot(str(as_record(row).get("clock") or ""))
        or looks_like_shot(str(as_record(row).get("beat") or ""))
    ]
    if shotty:
        return _gate(1, False, "Map is clocks and beats, not shots. Move camera to the edit list.")
    return _gate(1, True, f"{len(rows)} clock → beat row(s).")


def evaluate_edit_list(pack: dict[str, Any]) -> dict[str, Any]:
    rows = as_list(pack.get("editList"))
    if not rows:
        return _gate(2, False, "Edit list is empty.")
    takes = {
        str(as_record(item).get("take") or "").strip()
        for item in as_list(pack.get("takes"))
        if filled(as_record(item).get("take"))
    }
    problems: list[str] = []
    for i, raw in enumerate(rows, start=1):
        row = as_record(raw)
        join = str(row.get("join") or "").strip()
        if join not in JOIN_TYPES:
            problems.append(f"#{i} join must be continue, cut, or fadeblack")
        if not filled(row.get("songT")):
            problems.append(f"#{i} needs song t")
        if not take_ok(join, str(row.get("take") or "")):
            problems.append(f"#{i} needs a take")
        if not filled(row.get("locationGrade")):
            problems.append(f"#{i} needs location / grade")
        if not filled(row.get("action")):
            problems.append(f"#{i} needs action")
        verb = str(row.get("cameraVerb") or "").strip()
        amp = str(row.get("cameraAmplitude") or "")
        speed = str(row.get("cameraSpeed") or "")
        if verb not in CAMERA_VERBS or not filled(amp) or not filled(speed):
            problems.append(f"#{i} needs exactly one official camera verb (type + amplitude + speed)")
        if join and not hold_ok_for_join(join, str(row.get("hold") or "")):
            problems.append(f"#{i} hold does not match join {join}")
        take_name = str(row.get("take") or "").strip()
        if take_name and take_name not in {"—", "-"} and take_name not in takes:
            problems.append(f"#{i} take {take_name} is not on the take cards")
    if problems:
        return _gate(2, False, "; ".join(problems[:3]))
    return _gate(2, True, f"{len(rows)} row(s), each one join, clock, take, action, and one verb.")


def evaluate_takes(pack: dict[str, Any]) -> dict[str, Any]:
    rows = as_list(pack.get("takes"))
    if not rows:
        return _gate(3, False, "No takes.")
    incomplete = [
        row
        for row in rows
        if not all(
            filled(as_record(row).get(key))
            for key in ("take", "location", "grade", "windows", "prefix")
        )
    ]
    if incomplete:
        return _gate(
            3,
            False,
            f"{len(incomplete)} take(s) missing location, grade, windows, or prefix.",
        )
    return _gate(3, True, f"{len(rows)} take(s), one location and grade each.")


def _sheet_still_problems(card: dict[str, Any], kind: str) -> list[str]:
    label = str(card.get("name") or "").strip() or f"unnamed {kind}"
    problems: list[str] = []
    if not still_ok(card.get("stillFile")):
        problems.append(f"{label}: sheet path or none + why")
    source = str(card.get("stillSource") or "").strip()
    file = str(card.get("stillFile") or "")
    if source == "none" and still_ok(file) and not is_none_still(file):
        problems.append(f"{label}: sheet source (photo / qwen-t2i / qwen-edit / none) must match the file")
    elif source and source != "none" and is_none_still(file):
        problems.append(f"{label}: sheet source (photo / qwen-t2i / qwen-edit / none) must match the file")
    canvas = str(card.get("stillCanvas") or "")
    if not canvas_matches_hop1(canvas) or canvas_looks_stretched(canvas):
        problems.append(f"{label}: sheet canvas must be {DEFAULT_STILL_CANVAS} (do not stretch 1024²)")
    return problems


def evaluate_characters(pack: dict[str, Any]) -> dict[str, Any]:
    rows = as_list(pack.get("characters"))
    if not rows:
        return _gate(4, False, "Need at least one character card.")
    problems: list[str] = []
    for raw in rows:
        card = as_record(raw)
        if not filled(card.get("name")) or not filled(card.get("lockParagraph")) or not filled(card.get("forbidden")):
            label = str(card.get("name") or "").strip() or "unnamed character"
            problems.append(f"{label}: name, lock paragraph, forbidden")
        problems.extend(_sheet_still_problems(card, "character"))
    if problems:
        return _gate(4, False, f"{'; '.join(problems[:3])}. Plates live on still cards.")
    return _gate(4, True, f"{len(rows)} character card(s) locked. Sheets only — plates live on still cards.")


def evaluate_props(pack: dict[str, Any]) -> dict[str, Any]:
    rows = as_list(pack.get("props"))
    if not rows:
        return _gate(5, False, "Need at least one prop card.")
    problems: list[str] = []
    for raw in rows:
        prop = as_record(raw)
        label = str(prop.get("name") or "").strip() or "unnamed prop"
        if not filled(prop.get("name")) or not filled(prop.get("lockParagraph")) or not filled(prop.get("forbidden")):
            problems.append(f"{label}: lock paragraph + forbidden required")
        fields = as_record(prop.get("fields"))
        overall = as_record(fields.get("overallLength"))
        haft = as_record(fields.get("haftLength"))
        if not is_numeric_pin(overall.get("value")) or not is_numeric_pin(haft.get("value")):
            problems.append(f"{label}: overall vs haft length unresolved")
        if not still_ok(prop.get("stillFile")):
            problems.append(f"{label}: no still and no reason")
        else:
            problems.extend(
                item for item in _sheet_still_problems(prop, "prop") if "sheet path" not in item
            )
        missing = []
        for key in PROP_FIELD_KEYS:
            measurement = as_record(fields.get(key))
            if not filled(measurement.get("value")) or not filled(measurement.get("unit")):
                missing.append(key)
        if missing:
            problems.append(f"{label}: {len(missing)} field(s) missing value/unit")
        blob = " ".join(
            [
                str(prop.get("name") or ""),
                str(prop.get("lockParagraph") or ""),
                str(prop.get("forbidden") or ""),
                *[str(as_record(fields.get(key)).get("value") or "") for key in PROP_FIELD_KEYS],
            ]
        )
        if mentions_research(blob):
            problems.append(f"{label}: “research” is treatment homework, not generate-time")
    if problems:
        return _gate(5, False, "; ".join(problems[:3]))
    return _gate(5, True, f"{len(rows)} prop card(s) with units and still or none.")


def evaluate_look(pack: dict[str, Any]) -> dict[str, Any]:
    look = as_record(pack.get("look"))
    ok = filled(look.get("styleLine"))
    return _gate(6, ok, "One style line locked." if ok else "Look card needs one style line.")


def evaluate_audio(pack: dict[str, Any]) -> dict[str, Any]:
    audio = pack.get("audioPath")
    if audio not in AUDIO_PATHS:
        return _gate(7, False, "Pick exactly one: N/A + mute, prompt score, or silence.")
    if pack.get("speech") not in SPEECH_MODES:
        return _gate(7, False, "Speech: none, or lines finish by 8.0 s.")
    labels = {
        "na-mute": "N/A + mute in NLE",
        "prompt-score": "prompt score",
        "silence": "silence",
    }
    speech = "none" if pack.get("speech") == "none" else "finish by 8.0 s"
    return _gate(7, True, f"{labels[audio]}. Speech: {speech}.")


def evaluate_smoke(pack: dict[str, Any]) -> dict[str, Any]:
    takes = as_list(pack.get("takes"))
    if not takes:
        return _gate(8, False, "No takes to smoke.")
    if not filled(pack.get("smokeNotes")):
        return _gate(8, False, "Smoke plan notes are empty.")
    problems: list[str] = []
    unplanned = [
        row
        for row in takes
        if not as_record(row).get("hop1Planned") or not as_record(row).get("watched")
    ]
    if unplanned:
        problems.append(f"{len(unplanned)} take(s) missing hop-1 planned + watched")
    prefixes = [
        str(as_record(row).get("prefix") or "").strip().lower()
        for row in takes
    ]
    filled_prefixes = [item for item in prefixes if item]
    if len(filled_prefixes) != len(takes) or len(set(filled_prefixes)) != len(filled_prefixes):
        problems.append("Each take needs a unique hop-1 prefix")
    for raw in takes:
        take = as_record(raw)
        label = f"take {take.get('take')}" if filled(take.get("take")) else "unnamed take"
        plate = str(take.get("hop1Plate") or "")
        derived = hop1_mode_for_plate(plate)
        mode = str(take.get("hop1Mode") or "")
        if mode not in {"i2va", "t2v"}:
            problems.append(f"{label}: hop-1 mode I2VA or T2V")
            continue
        if not still_ok(plate):
            problems.append(f"{label}: plate file or none + why")
            continue
        if mode == "i2va" and not is_real_still_file(plate):
            problems.append(f"{label}: I2VA needs a plate file")
        if mode == "t2v" and is_real_still_file(plate):
            problems.append(f"{label}: a plate exists — hop-1 must be I2VA, not T2V")
        if derived and mode != derived:
            problems.append(
                f"{label}: hop-1 is {mode.upper()} but the plate implies {derived.upper()}"
            )
    if problems:
        return _gate(8, False, "; ".join(problems[:3]))
    i2va = sum(1 for row in takes if as_record(row).get("hop1Mode") == "i2va")
    t2v = sum(1 for row in takes if as_record(row).get("hop1Mode") == "t2v")
    return _gate(
        8,
        True,
        f"{len(takes)} hop-1(s) planned and watched ({i2va} I2VA, {t2v} T2V). continue hop 2+ is the latent.",
    )


def evaluate_entity_schedule(pack: dict[str, Any]) -> dict[str, Any]:
    from .consistency import entity_schedule_problems, is_filled_schedule

    problems = entity_schedule_problems(pack)
    if problems:
        return _gate(9, False, "; ".join(problems[:3]))
    n = sum(1 for row in as_list(pack.get("entitySchedule")) if is_filled_schedule(as_record(row)))
    noun = "y" if n == 1 else "ies"
    return _gate(
        9,
        True,
        f"{n} scheduled entit{noun}; windows list them; cut/fadeblack identity holds have plates.",
    )


def evaluate_lock_diff(pack: dict[str, Any]) -> dict[str, Any]:
    from .consistency import lock_diff_problems

    texts_ok = any(
        filled(as_record(card).get("name")) and filled(as_record(card).get("lockParagraph"))
        for card in [*as_list(pack.get("characters")), *as_list(pack.get("props"))]
    )
    if not texts_ok:
        return _gate(10, False, "Need lock paragraphs on named entities before a lock-diff can pass.")
    problems = lock_diff_problems(pack)
    if problems:
        return _gate(10, False, "; ".join(problems[:3]))
    return _gate(10, True, "Lock keywords match across cards and stills. No rotating synonyms.")


EVALUATORS = [
    evaluate_log_line,
    evaluate_map,
    evaluate_edit_list,
    evaluate_takes,
    evaluate_characters,
    evaluate_props,
    evaluate_look,
    evaluate_audio,
    evaluate_smoke,
    evaluate_entity_schedule,
    evaluate_lock_diff,
]


def evaluate_gates(pack: dict[str, Any] | None) -> list[dict[str, Any]]:
    body = pack if isinstance(pack, dict) else {}
    return [fn(body) for fn in EVALUATORS]


def all_gates_green(pack: dict[str, Any] | None) -> bool:
    return all(gate["ok"] for gate in evaluate_gates(pack))


def gate_snapshot(pack: dict[str, Any] | None) -> dict[str, Any]:
    gates = evaluate_gates(pack)
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "all_green": all(gate["ok"] for gate in gates),
        "gates": gates,
    }
