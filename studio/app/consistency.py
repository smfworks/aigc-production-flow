"""Phase 2 pack consistency: entity schedule + lock-diff.

Mirrors `app/src/lib/entitySchedule.ts` and `app/src/lib/lockDiff.ts` so the
studio refuse-path cannot stamp generate-ok on a red pack. Keep the rules
boring and explicit — no embeddings.
"""

from __future__ import annotations

import re
from typing import Any

from .gates import as_list, as_record, filled, still_ok

LOCK_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("brown", "brunette", "chestnut"),
    ("blond", "blonde"),
    ("grey", "gray"),
    ("red", "ginger", "auburn", "redhead"),
    ("cloak", "cape"),
    ("tunic", "shirt"),
    ("beard", "goatee"),
)

CHARACTER_LOCK_FIELDS = (
    ("ageSex", "Age / sex"),
    ("faceHairBeard", "Face / hair / beard"),
    ("body", "Body"),
    ("wardrobe", "Wardrobe"),
    ("footwear", "Footwear"),
    ("distinguishingMarks", "Distinguishing marks"),
    ("eraForbiddenModern", "Era / forbidden modern"),
)

TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


def tokenize_lock(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def synonym_hits(tokens: list[str]) -> list[tuple[tuple[str, ...], str]]:
    bag = set(tokens)
    hits: list[tuple[tuple[str, ...], str]] = []
    for group in LOCK_SYNONYM_GROUPS:
        for token in group:
            if token in bag:
                hits.append((group, token))
    return hits


def _named_kind(pack: dict[str, Any], name: str) -> str | None:
    target = name.strip().lower()
    for card in as_list(pack.get("characters")):
        if str(as_record(card).get("name") or "").strip().lower() == target:
            return "character"
    for card in as_list(pack.get("props")):
        if str(as_record(card).get("name") or "").strip().lower() == target:
            return "prop"
    return None


def collect_lock_texts(pack: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in as_list(pack.get("characters")):
        card = as_record(raw)
        name = str(card.get("name") or "").strip()
        if not name:
            continue
        if filled(card.get("lockParagraph")):
            rows.append(
                {
                    "entityName": name,
                    "entityKind": "character",
                    "source": "character lock paragraph",
                    "text": str(card.get("lockParagraph") or ""),
                }
            )
        for key, label in CHARACTER_LOCK_FIELDS:
            value = str(card.get(key) or "")
            if not filled(value) or value.strip().lower().startswith("none"):
                continue
            rows.append(
                {
                    "entityName": name,
                    "entityKind": "character",
                    "source": f"character field {label}",
                    "text": value,
                }
            )
    for raw in as_list(pack.get("props")):
        card = as_record(raw)
        name = str(card.get("name") or "").strip()
        if not name or not filled(card.get("lockParagraph")):
            continue
        rows.append(
            {
                "entityName": name,
                "entityKind": "prop",
                "source": "prop lock paragraph",
                "text": str(card.get("lockParagraph") or ""),
            }
        )
    for raw in as_list(pack.get("stills")):
        card = as_record(raw)
        entity = str(card.get("entity") or "").strip()
        lock = str(card.get("lockFromStill") or "")
        if not entity or not filled(lock):
            continue
        kind = _named_kind(pack, entity)
        if not kind:
            continue
        role = str(card.get("role") or "card")
        rows.append(
            {
                "entityName": entity,
                "entityKind": kind,
                "source": f"still {role} · {entity}",
                "text": lock,
            }
        )
    return rows


def lock_diff_problems(pack: dict[str, Any]) -> list[str]:
    texts = collect_lock_texts(pack)
    problems: list[str] = []
    for i, left in enumerate(texts):
        for right in texts[i + 1 :]:
            if left["entityKind"] != right["entityKind"]:
                continue
            if left["entityName"].strip().lower() != right["entityName"].strip().lower():
                continue
            left_hits = synonym_hits(tokenize_lock(left["text"]))
            right_hits = synonym_hits(tokenize_lock(right["text"]))
            for group, ltok in left_hits:
                match = next((tok for g, tok in right_hits if g is group or g == group), None)
                if match is None or match == ltok:
                    continue
                problems.append(
                    f"{left['entityName']}: rotating synonym {ltok} / {match} "
                    f"({'/'.join(group)}) — {left['source']} vs {right['source']}. "
                    "Same keywords every hop."
                )
    return problems


def parse_entity_list(raw: Any) -> list[str]:
    if not isinstance(raw, str):
        return []
    return [item.strip() for item in re.split(r"[,;/]+", raw) if item.strip()]


def row_has_entity(row: dict[str, Any], name: str) -> bool:
    target = name.strip().lower()
    if not target:
        return False
    return any(item.lower() == target for item in parse_entity_list(row.get("entities")))


def is_hop1_edit_row(pack: dict[str, Any], index: int) -> bool:
    rows = as_list(pack.get("editList"))
    if index < 0 or index >= len(rows):
        return False
    row = as_record(rows[index])
    join = str(row.get("join") or "").strip()
    take = str(row.get("take") or "").strip()
    if not take or take in {"—", "-"}:
        return join in {"cut", "fadeblack"}
    for i, raw in enumerate(rows):
        if str(as_record(raw).get("take") or "").strip() == take:
            return i == index
    return False


def _conditions_mentions_take(conditions: str, take: str) -> bool:
    token = re.escape(take.strip())
    if not token:
        return False
    return bool(
        re.search(rf"(?:\btake\s*{token}\b|\bhop-1\s+of\s+(?:take\s*)?{token}\b)", conditions, flags=re.I)
    )


def _conditions_mentions_cut_row(conditions: str, n: int) -> bool:
    return bool(re.search(rf"\bcut\s*(?:row|#)?\s*{n}\b", conditions, flags=re.I))


def _is_plate_role(role: str) -> bool:
    return role in {"hop-1 plate", "cut plate", "last-frame"}


def entity_plate_for_row(pack: dict[str, Any], entity_name: str, index: int) -> str:
    rows = as_list(pack.get("editList"))
    if index < 0 or index >= len(rows):
        return ""
    row = as_record(rows[index])
    name = entity_name.strip().lower()
    take = str(row.get("take") or "")
    for raw in as_list(pack.get("stills")):
        card = as_record(raw)
        if str(card.get("entity") or "").strip().lower() != name:
            continue
        role = str(card.get("role") or "")
        if not _is_plate_role(role):
            continue
        conditions = str(card.get("conditions") or "")
        if role == "cut plate" and (
            _conditions_mentions_cut_row(conditions, index + 1) or _conditions_mentions_take(conditions, take)
        ):
            return str(card.get("file") or "")
        if role == "hop-1 plate" and _conditions_mentions_take(conditions, take):
            return str(card.get("file") or "")
    return ""


def _window_tokens(windows: str) -> list[str]:
    return [item.strip().lower() for item in re.split(r"[,;]+", windows) if item.strip()]


def _row_number_match(token: str, index: int) -> bool:
    n = index + 1
    cleaned = re.sub(r"^#", "", token)
    cleaned = re.sub(r"^row\s+", "", cleaned)
    if cleaned.isdigit():
        return int(cleaned) == n
    range_match = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", cleaned)
    if not range_match:
        return False
    return int(range_match.group(1)) <= n <= int(range_match.group(2))


def schedule_applies_to_row(pack: dict[str, Any], schedule: dict[str, Any], index: int) -> bool:
    rows = as_list(pack.get("editList"))
    if index < 0 or index >= len(rows):
        return False
    row = as_record(rows[index])
    take = str(schedule.get("take") or "").strip()
    row_take = str(row.get("take") or "").strip()
    if not take or (take != "*" and take != row_take):
        return False
    windows = str(schedule.get("windows") or "").strip().lower()
    if not windows or windows == "all":
        return True
    song_t = str(row.get("songT") or "").strip().lower()
    for token in _window_tokens(windows):
        if token == "all":
            return True
        if token == "hop-1" and is_hop1_edit_row(pack, index):
            return True
        if song_t == token:
            return True
        if _row_number_match(token, index):
            return True
    return False


def is_filled_schedule(row: dict[str, Any]) -> bool:
    windows = str(row.get("windows") or "").strip().lower()
    return filled(row.get("entityName")) or filled(row.get("take")) or (filled(windows) and windows != "all")


def missing_identity_hold_plate(pack: dict[str, Any], schedule: dict[str, Any], index: int) -> str | None:
    if not schedule.get("identityHold"):
        return None
    rows = as_list(pack.get("editList"))
    if index < 0 or index >= len(rows):
        return None
    row = as_record(rows[index])
    join = str(row.get("join") or "").strip()
    if join not in {"cut", "fadeblack"}:
        return None
    file = entity_plate_for_row(pack, str(schedule.get("entityName") or ""), index)
    if still_ok(file):
        return None
    name = str(schedule.get("entityName") or "").strip() or "unnamed entity"
    n = index + 1
    if join == "fadeblack":
        return (
            f"{name} on #{n} fadeblack: identity hold needs a hop-1 plate "
            "bound to this entity (or none + why)"
        )
    return (
        f"{name} on #{n} cut: identity hold needs a cut/hop-1 plate "
        "bound to this entity (or none + why)"
    )


def named_entities(pack: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for raw in as_list(pack.get("characters")):
        name = str(as_record(raw).get("name") or "").strip()
        if name:
            rows.append(("character", name))
    for raw in as_list(pack.get("props")):
        name = str(as_record(raw).get("name") or "").strip()
        if name:
            rows.append(("prop", name))
    return rows


def known_take(pack: dict[str, Any], take: str) -> bool:
    t = take.strip()
    if not t:
        return False
    if t == "*":
        return True
    return any(str(as_record(item).get("take") or "").strip() == t for item in as_list(pack.get("takes")))


def entity_schedule_problems(pack: dict[str, Any]) -> list[str]:
    filled_rows = [as_record(row) for row in as_list(pack.get("entitySchedule")) if is_filled_schedule(as_record(row))]
    if not filled_rows:
        return ["Entity schedule is empty. Say who persists on which takes/windows."]
    problems: list[str] = []
    known = named_entities(pack)
    edit_list = as_list(pack.get("editList"))
    for row in filled_rows:
        label = str(row.get("entityName") or "").strip() or "unnamed entity"
        kind = str(row.get("entityKind") or "").strip()
        if kind not in {"character", "prop"}:
            problems.append(f"{label}: kind must be character or prop")
        if not filled(row.get("entityName")):
            problems.append("Schedule row needs an entity name")
            continue
        match = next(
            (
                item
                for item in known
                if item[1].lower() == label.lower() and (not kind or item[0] == kind)
            ),
            None,
        )
        if not match:
            problems.append(f"{label}: not a named character or prop card")
        take = str(row.get("take") or "")
        if not filled(take) or not known_take(pack, take):
            problems.append(f"{label}: take must be a take letter or *")
        windows = str(row.get("windows") or "").strip() or "all"
        matching = [
            index
            for index in range(len(edit_list))
            if schedule_applies_to_row(pack, {**row, "windows": windows}, index)
        ]
        if not matching:
            problems.append(f"{label}: no edit-list window matches take {take.strip() or '?'} / {windows}")
            continue
        for index in matching:
            edit = as_record(edit_list[index])
            if not row_has_entity(edit, label):
                problems.append(
                    f"{label} scheduled on #{index + 1} (take {edit.get('take') or '—'}, "
                    f"{edit.get('join') or 'no join'}) but missing from that window's entities"
                )
            plate_gap = missing_identity_hold_plate(pack, row, index)
            if plate_gap:
                problems.append(plate_gap)
    for kind, name in known:
        scheduled = any(
            str(row.get("entityName") or "").strip().lower() == name.lower()
            and (not str(row.get("entityKind") or "").strip() or row.get("entityKind") == kind)
            for row in filled_rows
        )
        if not scheduled:
            problems.append(f"{name}: named {kind} is not on the entity schedule")
    return problems
