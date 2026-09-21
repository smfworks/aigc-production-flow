"""Continuity panel summary: entity-schedule + lock-diff from the imported pack.

Read/visualize + navigate only. Not a full NLE.
"""

from __future__ import annotations

from typing import Any

from .consistency import entity_schedule_problems, is_filled_schedule, lock_diff_problems
from .deps import latest_revision
from .gates import as_list, as_record, gate_snapshot
from .identity import identity_href, identity_lock_diff_problems, identity_summary
from .models import Episode


def _href(episode: Episode, shot_id: str | None = None) -> str:
    project_id = episode.project_id
    if shot_id:
        return f"#/projects/{project_id}/episodes/{episode.id}/shots/{shot_id}"
    return f"#/projects/{project_id}/episodes/{episode.id}"


def continuity_summary(episode: Episode) -> dict[str, Any]:
    revision = latest_revision(episode)
    pack = revision.pack_json if revision and isinstance(revision.pack_json, dict) else {}
    snapshot = (
        revision.gate_snapshot
        if revision and isinstance(revision.gate_snapshot, dict)
        else gate_snapshot(pack)
        if pack
        else {"all_green": False, "gates": []}
    )
    gates = snapshot.get("gates") if isinstance(snapshot.get("gates"), list) else []
    red = [gate for gate in gates if isinstance(gate, dict) and not gate.get("ok")]
    schedule_problems = entity_schedule_problems(pack) if pack else ["No pack imported yet."]
    diff_problems = lock_diff_problems(pack) if pack else []
    identity = identity_summary(episode)
    identity_problems = identity_lock_diff_problems(episode, pack) if pack else []
    schedule_rows = [
        as_record(row) for row in as_list(pack.get("entitySchedule")) if is_filled_schedule(as_record(row))
    ]
    shots: list[dict[str, Any]] = []
    mismatches: list[str] = list(schedule_problems) + list(diff_problems) + list(identity_problems)
    names = _entity_names(pack)
    for shot in episode.shots:
        issues: list[str] = []
        for problem in schedule_problems:
            token = f"#{shot.sort_index + 1}"
            if token in problem or (shot.take and f"take {shot.take}" in problem.lower()):
                issues.append(problem)
        for problem in diff_problems:
            entities = (shot.entities or "").lower()
            if any(name.lower() in entities for name in names if name):
                if any(name.lower() in problem.lower() for name in names if name.lower() in entities):
                    issues.append(problem)
        linked = [
            asset
            for asset in episode.media
            if asset.kind == "plate"
            and (
                (asset.shot_id or "") == shot.id
                or ((asset.edit_row_id or "") and (asset.edit_row_id or "") == (shot.edit_row_id or ""))
            )
        ]
        identity_hrefs = [identity_href(episode, asset.id) for asset in linked]
        shots.append(
            {
                "shot_id": shot.id,
                "edit_row_id": shot.edit_row_id,
                "sort_index": shot.sort_index,
                "take": shot.take or "",
                "join": shot.join or "",
                "entities": shot.entities or "",
                "issues": issues,
                "href": _href(episode, shot.id),
                "identity_hrefs": identity_hrefs,
                "identity_href": identity_hrefs[0] if identity_hrefs else f"{_href(episode)}/identity",
            }
        )
    return {
        "episode_id": episode.id,
        "project_id": episode.project_id,
        "honesty": (
            "Read/visualize + navigate only. Not a full NLE. Pack zip remains the contract. "
            "Identity store is approved sheets/plates — not embeddings."
        ),
        "all_green": bool(snapshot.get("all_green")),
        "red_gates": red,
        "entity_schedule": schedule_rows,
        "entity_schedule_problems": schedule_problems,
        "lock_diff_problems": diff_problems,
        "identity_lock_diff_problems": identity_problems,
        "mismatches": mismatches,
        "shots": shots,
        "identity": identity,
        "identity_href": f"#/projects/{episode.project_id}/episodes/{episode.id}/identity",
    }


def _entity_names(pack: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for raw in as_list(pack.get("characters")) + as_list(pack.get("props")):
        name = str(as_record(raw).get("name") or "").strip()
        if name:
            names.append(name)
    return names
