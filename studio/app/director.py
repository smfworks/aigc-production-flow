"""Director front door for the Create wizard.

Task tree, craft lanes, checkpoints, and deliverable scope are planning labels.
Nothing here calls Comfy, starts Hermes, approves an identity, or writes an MP4.
"""

from __future__ import annotations

import re
from typing import Any

from .clarify import clarify_questions
from .gates import GATE_DEFS, evaluate_gates, is_real_still_file

PLATFORM_FORMATS = ("9:16", "16:9", "1:1", "4:5", "4:3")
_FORMAT_SET = set(PLATFORM_FORMATS)

DIRECTOR_NOTE = (
    "Craft lanes are routing labels for the brief. They are not cloud agents, "
    "and this plan does not run them. Checkpoints repeat the real gates. "
    "Create does not turn gates green, approve identities, or sign off."
)

_AUTO_CASCADE = {"audio-notes", "identity-sheets", "plates", "hop-1"}


def _shot_count(answers: dict[str, Any]) -> int:
    try:
        count = int(answers.get("shot_count") or 0)
    except (TypeError, ValueError):
        count = 0
    if count < 1:
        try:
            length = float(answers.get("target_length_s") or 0)
        except (TypeError, ValueError):
            length = 0
        if length > 0:
            count = max(1, min(24, int(round(length / 10.125))))
        else:
            return 0
    return max(1, min(24, count))


def _takes(answers: dict[str, Any]) -> list[str]:
    count = _shot_count(answers)
    if count < 1:
        return []
    if answers.get("format") == "music-video":
        return ["A"]
    rows = []
    for index in range(count):
        if index < 26:
            rows.append(chr(ord("A") + index))
        else:
            rows.append(f"T{index + 1}")
    return rows


def _node(
    *,
    order: int,
    node_id: str,
    kind: str,
    label: str,
    lane: str,
    depends_on: list[str],
    note: str,
    take: str = "",
    prunable: bool = True,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "kind": kind,
        "label": label,
        "lane": lane,
        "depends_on": list(depends_on),
        "enabled": True,
        "deleted": False,
        "take": take,
        "note": note,
        "prunable": prunable,
        "executes": False,
        "order": order,
    }


def default_task_tree(answers: dict[str, Any]) -> list[dict[str, Any]]:
    """Studio's real order. Nodes do not execute."""
    takes = _takes(answers) or ["A"]
    hop_ids = [f"hop-1:{take}" for take in takes]
    nodes = [
        _node(
            order=1,
            node_id="script-beats",
            kind="script-beats",
            label="Script / beats",
            lane="writer",
            depends_on=[],
            note="Copy and beats. This node does not run a model.",
        ),
        _node(
            order=2,
            node_id="audio-notes",
            kind="audio-notes",
            label="Audio notes",
            lane="sound",
            depends_on=["script-beats"],
            note="Sound lane notes only. Not a mix and not a generate.",
        ),
        _node(
            order=3,
            node_id="identity-sheets",
            kind="identity-sheets",
            label="Identity sheets",
            lane="art",
            depends_on=["script-beats"],
            note="Draft sheets only. Cast text is not an approval.",
        ),
        _node(
            order=4,
            node_id="plates",
            kind="plates",
            label="Plates",
            lane="picture",
            depends_on=["identity-sheets"],
            note="Hop-1 first frames. A plate is not the sheet.",
        ),
    ]
    order = 5
    for take, hop_id in zip(takes, hop_ids, strict=True):
        nodes.append(
            _node(
                order=order,
                node_id=hop_id,
                kind="hop-1",
                label=f"Hop-1 {take}",
                lane="picture",
                depends_on=["plates"],
                take=take,
                note="One hop-1 for this take. Watch it before any extend. This node does not enqueue.",
            )
        )
        order += 1
    nodes.append(
        _node(
            order=order,
            node_id="stitch",
            kind="stitch",
            label="Stitch",
            lane="picture",
            depends_on=hop_ids,
            note="Concat plan after hop-1. No MP4 is invented from this tree.",
        )
    )
    order += 1
    nodes.append(
        _node(
            order=order,
            node_id="review-gates",
            kind="review-gates",
            label="Review gates",
            lane="review",
            depends_on=["stitch"],
            note="Log line through lock-diff, plus hop-1 watch and sign-off. Cannot be pruned.",
            prunable=False,
        )
    )
    return nodes


def _ordered(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {node["id"]: node for node in nodes}
    pending = list(nodes)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _ in range(24):
        if not pending:
            break
        next_pending: list[dict[str, Any]] = []
        for node in pending:
            ready = all(dep in seen or dep not in by_id for dep in node.get("depends_on") or [])
            if ready:
                out.append(node)
                seen.add(node["id"])
            else:
                next_pending.append(node)
        if len(next_pending) == len(pending):
            out.extend(next_pending)
            break
        pending = next_pending
    return out


def _cascade(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = _ordered(nodes)
    by_id = {node["id"]: node for node in ordered}
    for _ in range(4):
        for node in ordered:
            if node["kind"] == "review-gates" or not node.get("prunable", True):
                node["enabled"] = True
                node["deleted"] = False
                node["prunable"] = False
                node["executes"] = False
                continue
            node["executes"] = False
            if node["kind"] not in _AUTO_CASCADE:
                if node["deleted"]:
                    node["enabled"] = False
                continue
            parents = [by_id[dep] for dep in node.get("depends_on") or [] if dep in by_id]
            if not parents:
                if node["deleted"]:
                    node["enabled"] = False
                continue
            if all(parent.get("deleted") for parent in parents):
                node["deleted"] = True
                node["enabled"] = False
            elif all(parent.get("deleted") or not parent.get("enabled") for parent in parents):
                node["enabled"] = False
    for index, node in enumerate(ordered, start=1):
        node["order"] = index
    return ordered


def resolve_tree(saved: list[Any] | None, answers: dict[str, Any]) -> list[dict[str, Any]]:
    default = default_task_tree(answers)
    incoming = saved if isinstance(saved, list) else []
    by_id: dict[str, dict[str, Any]] = {}
    for raw in incoming:
        if isinstance(raw, dict) and raw.get("id"):
            by_id[str(raw["id"])] = raw
    resolved: list[dict[str, Any]] = []
    for template in default:
        node = dict(template)
        node["depends_on"] = list(template["depends_on"])
        prev = by_id.get(node["id"])
        if isinstance(prev, dict):
            if "enabled" in prev:
                node["enabled"] = bool(prev.get("enabled"))
            if prev.get("deleted"):
                node["deleted"] = True
                node["enabled"] = False
        if node["kind"] == "review-gates":
            node["enabled"] = True
            node["deleted"] = False
            node["prunable"] = False
        resolved.append(node)
    return _cascade(resolved)


def normalize_stored_tree(saved: Any, answers: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep an operator tree. An absent tree stays empty until the plan is shown."""
    if not isinstance(saved, list) or not saved:
        return []
    if _shot_count(answers) < 1 and answers.get("format") != "music-video":
        return []
    return resolve_tree(saved, answers)


def tree_for(answers: dict[str, Any]) -> list[dict[str, Any]]:
    saved = answers.get("task_tree")
    if isinstance(saved, list) and saved:
        return resolve_tree(saved, answers)
    if _shot_count(answers) < 1:
        return default_task_tree({**answers, "shot_count": 1, "format": answers.get("format") or "custom"})
    return default_task_tree(answers)


def normalize_platform_formats(value: Any) -> list[str]:
    if isinstance(value, str):
        parts = re.split(r"[,;/]+", value)
    elif isinstance(value, list):
        parts = [str(part) for part in value]
    else:
        parts = []
    found: list[str] = []
    for part in parts:
        token = str(part).strip().lower().replace(" ", "")
        token = token.removesuffix("only")
        token = token.replace("×", ":").replace("x", ":")
        if token in _FORMAT_SET and token not in found:
            found.append(token)
        if len(found) >= 5:
            break
    return found


def normalize_scope(raw: dict[str, Any] | None) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    return {
        "audience": str(src.get("audience") or "").strip()[:500],
        "deliverables": str(src.get("deliverables") or "").strip()[:2000],
        "negative_constraints": str(src.get("negative_constraints") or "").strip()[:2000],
        "must_nots": str(src.get("must_nots") or "").strip()[:2000],
        "platform_formats": normalize_platform_formats(src.get("platform_formats")),
        "claim_bans": str(src.get("claim_bans") or "").strip()[:2000],
    }


def scope_note(scope: dict[str, Any]) -> str:
    parts: list[str] = []
    audience = str(scope.get("audience") or "").strip()
    deliverables = str(scope.get("deliverables") or "").strip()
    negative = str(scope.get("negative_constraints") or "").strip()
    must = str(scope.get("must_nots") or "").strip()
    bans = str(scope.get("claim_bans") or "").strip()
    formats = scope.get("platform_formats") or []
    if audience:
        parts.append(f"Audience: {audience}")
    if deliverables:
        parts.append(f"Deliverables: {deliverables}")
    if negative:
        parts.append(f"Negative constraints: {negative}")
    if must:
        parts.append(f"Must not: {must}")
    if formats:
        parts.append("Platform formats: " + ", ".join(str(item) for item in formats))
    if bans:
        parts.append(f"Claim bans: {bans}")
    return "\n".join(parts)


def _on(node: dict[str, Any]) -> bool:
    return bool(node.get("enabled")) and not bool(node.get("deleted"))


def _kind_on(tree: list[dict[str, Any]], kind: str) -> bool:
    nodes = [node for node in tree if node.get("kind") == kind]
    if not nodes:
        return True
    return any(_on(node) for node in nodes)


def craft_lanes(answers: dict[str, Any], tree: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prompt = str(answers.get("prompt") or "").strip()
    look = str(answers.get("look") or "").strip()
    cast = str(answers.get("cast_notes") or "").strip()
    audio = str(answers.get("audio_notes") or "").strip()
    art_bits = " ".join(bit for bit in (look, cast) if bit)
    windows = _shot_count(answers) or "unspecified"
    picture = (
        f"{answers.get('format') or 'custom'} · {windows} windows. "
        "Plates, then hop-1, then a stitch plan."
    )
    return [
        {
            "id": "writer",
            "label": "Writer",
            "covers": "copy/beats",
            "routing": (prompt or "Beats from the prompt.")[:500],
            "enabled": _kind_on(tree, "script-beats"),
            "ran": False,
        },
        {
            "id": "art",
            "label": "Art",
            "covers": "identity/look",
            "routing": (art_bits or "Identity drafts and look notes.")[:500],
            "enabled": _kind_on(tree, "identity-sheets"),
            "ran": False,
        },
        {
            "id": "picture",
            "label": "Picture",
            "covers": "plates/hop-1",
            "routing": picture[:500],
            "enabled": _kind_on(tree, "plates") or _kind_on(tree, "hop-1") or _kind_on(tree, "stitch"),
            "ran": False,
        },
        {
            "id": "sound",
            "label": "Sound",
            "covers": "audio notes",
            "routing": (audio or "Audio notes only. Not a mix.")[:500],
            "enabled": _kind_on(tree, "audio-notes"),
            "ran": False,
        },
    ]


def lane_for_kind(kind: str) -> str:
    return {
        "still-sheet": "art",
        "still-plate": "picture",
        "clip-hop1": "picture",
        "stitch": "picture",
    }.get(kind, "")


def job_enabled(tree: list[dict[str, Any]] | None, *, kind: str, take: str = "") -> bool:
    if not tree:
        return True
    if kind == "still-sheet":
        return _kind_on(tree, "identity-sheets")
    if kind == "still-plate":
        return _kind_on(tree, "plates")
    if kind == "clip-hop1":
        hops = [node for node in tree if node.get("kind") == "hop-1"]
        if not hops:
            return True
        wanted = (take or "").strip()
        if wanted:
            match = [node for node in hops if str(node.get("take") or "") == wanted]
            if match:
                return _on(match[0])
        return any(_on(node) for node in hops)
    if kind == "stitch":
        nodes = [node for node in tree if node.get("kind") == "stitch"]
        if not nodes:
            return True
        return _on(nodes[0])
    return True


def _rows(pack: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = pack.get(key)
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def build_checkpoints(
    pack: dict[str, Any] | None,
    *,
    approved_sheets: int = 0,
    draft_sheets: int = 0,
    signed_off: bool = False,
) -> dict[str, Any]:
    body = pack if isinstance(pack, dict) else {}
    gates = evaluate_gates(body)
    all_green = bool(gates) and all(bool(gate.get("ok")) for gate in gates)
    failing = [str(gate.get("label") or gate.get("id")) for gate in gates if not gate.get("ok")]
    plate_rows = [
        row
        for row in _rows(body, "stills")
        if "plate" in str(row.get("role") or "").lower()
    ]
    if not plate_rows:
        plates_cleared = False
        plates_detail = "No plate cards yet. A sheet is not a plate."
    else:
        missing = [
            row for row in plate_rows if not is_real_still_file(str(row.get("file") or ""))
        ]
        plates_cleared = not missing
        plates_detail = (
            "Plate files are on the still cards."
            if plates_cleared
            else f"{len(missing)} plate card(s) have no plate file. A sheet is not a plate."
        )
    takes = _rows(body, "takes")
    watched = [row for row in takes if row.get("watched") is True]
    hop_cleared = bool(takes) and len(watched) == len(takes)
    identities_cleared = approved_sheets > 0 and draft_sheets == 0
    if identities_cleared:
        identity_detail = f"{approved_sheets} approved sheet(s). The wizard did not approve them."
    elif draft_sheets:
        identity_detail = (
            f"{draft_sheets} identity draft(s), {approved_sheets} approved. "
            "Cast text is not an approval."
        )
    else:
        identity_detail = "No approved sheets. Cast text stays a draft."
    items = [
        {
            "id": "identities-draft",
            "label": "Identities still draft",
            "cleared": identities_cleared,
            "detail": identity_detail,
        },
        {
            "id": "plates-missing",
            "label": "Plates missing",
            "cleared": plates_cleared,
            "detail": plates_detail,
        },
        {
            "id": "gates-red",
            "label": "Gates red",
            "cleared": all_green,
            "detail": (
                "All gates are green."
                if all_green
                else "Still open: " + "; ".join(failing[:6]) + ("." if failing else "Pack gates are not green.")
            ),
        },
        {
            "id": "hop1-unwatched",
            "label": "Hop-1 unwatched",
            "cleared": hop_cleared,
            "detail": (
                "Every take has a watched hop-1."
                if hop_cleared
                else "Hop-1 is unwatched. Watch the smoke plan before any extend."
            ),
        },
        {
            "id": "no-signoff",
            "label": "No reviewer/producer sign-off",
            "cleared": bool(signed_off),
            "detail": (
                "Cut is this sign-off. A stitch file does not close it."
                if signed_off
                else (
                    "Cut is this sign-off. generate-ok still needs a reviewer or producer. "
                    "A stitch file does not close Cut and does not mark the episode completed."
                )
            ),
        },
    ]
    return {
        "items": items,
        "gates": [
            {
                "id": gate.get("id"),
                "n": gate.get("n"),
                "label": gate.get("label"),
                "ok": bool(gate.get("ok")),
                "detail": gate.get("detail") or "",
            }
            for gate in gates
        ],
        "gate_ids": [gate["id"] for gate in GATE_DEFS],
        "all_gates_green": all_green,
        "generate_ready": False,
        "note": (
            "These checkpoints use the real gate matrix. "
            "Brief is the structured intake pause. Cut is the existing sign-off. "
            "Create does not clear them and does not lower the bar. "
            "Prompt prose is not permission to generate."
        ),
    }


def public_director(
    answers: dict[str, Any],
    pack: dict[str, Any] | None = None,
    *,
    approved_sheets: int = 0,
    draft_sheets: int = 0,
    signed_off: bool = False,
) -> dict[str, Any]:
    tree = tree_for(answers)
    scope = normalize_scope(answers)
    questions = clarify_questions(answers)
    brief_open = bool(questions) and not answers.get("clarify_ack")
    note = scope_note(scope)
    bound_refs = [row for row in (answers.get("subject_refs") or []) if isinstance(row, dict) and row.get("bound")]
    if bound_refs:
        listed = ", ".join(f"@{row['token']} (identity draft)" for row in bound_refs)
        note = f"{note}\nSubject refs: {listed}".strip()
    return {
        "scope": scope,
        "scope_note": note,
        "task_tree": tree,
        "craft_lanes": craft_lanes(answers, tree),
        "checkpoints": build_checkpoints(
            pack,
            approved_sheets=approved_sheets,
            draft_sheets=draft_sheets,
            signed_off=signed_off,
        ),
        "clarify": {
            "questions": questions,
            "note": (
                "Clarify-before-run asks for missing brief fields. "
                "These are not gate checkpoints and they do not turn a gate green."
            ),
        },
        "execution_gates": {
            "brief": {
                "id": "brief",
                "label": "Brief",
                "cleared": not brief_open,
                "maps_to": "clarify",
                "detail": (
                    "Structured brief fields are filled or the gaps were named. "
                    "Prompt prose is not permission to generate."
                    if not brief_open
                    else (
                        "Audience, deliverables, cast, or a negative constraint is still empty. "
                        "This pause is not a pack gate."
                    )
                ),
            },
            "cut": {
                "id": "cut",
                "label": "Cut",
                "cleared": bool(signed_off),
                "maps_to": "no-signoff",
                "detail": (
                    "Cut is the existing reviewer or producer sign-off. "
                    "Hermes handoff still writes a brief while Cut is open. "
                    "A stitch file does not close Cut or mark the episode completed."
                ),
            },
        },
        "agents_ran": False,
        "subject_refs": [
            row for row in (answers.get("subject_refs") or []) if isinstance(row, dict)
        ],
        "called_comfy": False,
        "hermes_ran": False,
        "produced_mp4": False,
        "executes": False,
        "note": DIRECTOR_NOTE,
    }
