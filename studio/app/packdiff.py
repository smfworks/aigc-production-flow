"""Diff two pack.json snapshots (stored revisions or a candidate import).

Compares gates, entity-schedule, edit-list, and identity keywords.
Does not rewrite synonym lock-diff groups. Not a generate.
"""

from __future__ import annotations

from typing import Any

from .consistency import collect_lock_texts, tokenize_lock
from .gates import as_list, as_record, gate_snapshot
from .models import PackRevision

IDENTITY_KEYWORD_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "same",
        "every",
        "hop",
        "none",
    }
)


def _gate_map(snapshot: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    body = snapshot if isinstance(snapshot, dict) else {}
    rows = body.get("gates") if isinstance(body.get("gates"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        gate_id = str(raw.get("id") or "").strip()
        if gate_id:
            out[gate_id] = raw
    return out


def _schedule_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("entityKind") or "").strip().lower(),
            str(row.get("entityName") or "").strip().lower(),
            str(row.get("take") or "").strip(),
            str(row.get("windows") or "").strip().lower(),
        ]
    )


def _edit_key(row: dict[str, Any], index: int) -> str:
    row_id = str(row.get("id") or "").strip()
    if row_id:
        return row_id
    return f"#{index + 1}|{row.get('take') or ''}|{row.get('join') or ''}|{row.get('songT') or ''}"


def _summary_row(row: dict[str, Any], keys: tuple[str, ...]) -> dict[str, str]:
    return {key: str(row.get(key) or "") for key in keys}


def _changed_fields(left: dict[str, Any], right: dict[str, Any]) -> dict[str, dict[str, str]]:
    keys = sorted(set(left) | set(right))
    out: dict[str, dict[str, str]] = {}
    for key in keys:
        lv = str(left.get(key) or "")
        rv = str(right.get(key) or "")
        if lv != rv:
            out[key] = {"from": lv, "to": rv}
    return out


def identity_keywords(pack: dict[str, Any]) -> dict[str, list[str]]:
    """Explicit identity tokens from lock paragraphs / still lockFromStill. Not embeddings."""
    grouped: dict[str, set[str]] = {}
    for row in collect_lock_texts(pack):
        name = f"{row['entityKind']}:{row['entityName']}".lower()
        tokens = [
            token
            for token in tokenize_lock(row.get("text") or "")
            if token not in IDENTITY_KEYWORD_STOP and len(token) > 1
        ]
        grouped.setdefault(name, set()).update(tokens)
    return {key: sorted(values) for key, values in sorted(grouped.items())}


def _list_diff(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    *,
    key_fn,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    left_map = {key_fn(row, i): row for i, row in enumerate(left_rows)}
    right_map = {key_fn(row, i): row for i, row in enumerate(right_rows)}
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    for key in sorted(set(left_map) | set(right_map)):
        if key not in left_map:
            added.append({"key": key, **_summary_row(right_map[key], fields)})
        elif key not in right_map:
            removed.append({"key": key, **_summary_row(left_map[key], fields)})
        else:
            delta = _changed_fields(
                _summary_row(left_map[key], fields),
                _summary_row(right_map[key], fields),
            )
            if delta:
                changed.append({"key": key, "fields": delta})
    return {"added": added, "removed": removed, "changed": changed}


def pack_payload(revision: PackRevision | None) -> dict[str, Any]:
    if revision is None or not isinstance(revision.pack_json, dict):
        return {}
    return revision.pack_json


def diff_packs(
    left_pack: dict[str, Any] | None,
    right_pack: dict[str, Any] | None,
    *,
    left_snapshot: dict[str, Any] | None = None,
    right_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    left = left_pack if isinstance(left_pack, dict) else {}
    right = right_pack if isinstance(right_pack, dict) else {}
    left_gates = _gate_map(left_snapshot or (gate_snapshot(left) if left else {"gates": []}))
    right_gates = _gate_map(right_snapshot or (gate_snapshot(right) if right else {"gates": []}))
    gate_ids = sorted(set(left_gates) | set(right_gates), key=lambda gid: left_gates.get(gid, right_gates.get(gid, {})).get("n") or gid)
    gates: list[dict[str, Any]] = []
    for gate_id in gate_ids:
        lg = left_gates.get(gate_id) or {}
        rg = right_gates.get(gate_id) or {}
        left_ok = bool(lg.get("ok")) if lg else None
        right_ok = bool(rg.get("ok")) if rg else None
        changed = left_ok != right_ok or str(lg.get("detail") or "") != str(rg.get("detail") or "")
        gates.append(
            {
                "id": gate_id,
                "n": rg.get("n") or lg.get("n") or 0,
                "label": rg.get("label") or lg.get("label") or gate_id,
                "left_ok": left_ok,
                "right_ok": right_ok,
                "left_detail": str(lg.get("detail") or ""),
                "right_detail": str(rg.get("detail") or ""),
                "changed": changed,
            }
        )

    schedule_fields = ("entityKind", "entityName", "take", "windows", "identityHold")
    entity_schedule = _list_diff(
        [as_record(row) for row in as_list(left.get("entitySchedule"))],
        [as_record(row) for row in as_list(right.get("entitySchedule"))],
        key_fn=lambda row, _i: _schedule_key(row),
        fields=schedule_fields,
    )

    edit_fields = (
        "songT",
        "durS",
        "join",
        "take",
        "locationGrade",
        "cameraVerb",
        "action",
        "entities",
    )
    edit_list = _list_diff(
        [as_record(row) for row in as_list(left.get("editList"))],
        [as_record(row) for row in as_list(right.get("editList"))],
        key_fn=_edit_key,
        fields=edit_fields,
    )

    left_keys = identity_keywords(left)
    right_keys = identity_keywords(right)
    keyword_names = sorted(set(left_keys) | set(right_keys))
    keywords_added: list[dict[str, Any]] = []
    keywords_removed: list[dict[str, Any]] = []
    keywords_changed: list[dict[str, Any]] = []
    for name in keyword_names:
        lv = set(left_keys.get(name) or [])
        rv = set(right_keys.get(name) or [])
        if name not in left_keys:
            keywords_added.append({"entity": name, "tokens": sorted(rv)})
        elif name not in right_keys:
            keywords_removed.append({"entity": name, "tokens": sorted(lv)})
        elif lv != rv:
            keywords_changed.append(
                {
                    "entity": name,
                    "added": sorted(rv - lv),
                    "removed": sorted(lv - rv),
                }
            )

    changed_count = (
        sum(1 for gate in gates if gate["changed"])
        + len(entity_schedule["added"])
        + len(entity_schedule["removed"])
        + len(entity_schedule["changed"])
        + len(edit_list["added"])
        + len(edit_list["removed"])
        + len(edit_list["changed"])
        + len(keywords_added)
        + len(keywords_removed)
        + len(keywords_changed)
    )
    return {
        "honesty": (
            "Structured pack revision diff (gates, entity-schedule, edit-list, "
            "identity keywords). Not embeddings. Confirm to apply an import. "
            "Never auto-generate."
        ),
        "gates": gates,
        "entity_schedule": entity_schedule,
        "edit_list": edit_list,
        "identity_keywords": {
            "added": keywords_added,
            "removed": keywords_removed,
            "changed": keywords_changed,
            "left": left_keys,
            "right": right_keys,
        },
        "summary": {
            "changed": changed_count > 0,
            "changed_count": changed_count,
            "gates_changed": sum(1 for gate in gates if gate["changed"]),
            "schedule_changed": bool(
                entity_schedule["added"] or entity_schedule["removed"] or entity_schedule["changed"]
            ),
            "edit_list_changed": bool(edit_list["added"] or edit_list["removed"] or edit_list["changed"]),
            "identity_keywords_changed": bool(
                keywords_added or keywords_removed or keywords_changed
            ),
            "left_title": str(left.get("title") or ""),
            "right_title": str(right.get("title") or ""),
        },
    }


def revision_ref(revision: PackRevision | None, *, label: str = "") -> dict[str, Any] | None:
    if revision is None:
        return None
    return {
        "id": revision.id,
        "filename": revision.filename,
        "all_gates_green": bool(revision.all_gates_green),
        "created_by": revision.created_by,
        "created_at": revision.created_at,
        "label": label or revision.filename,
    }
