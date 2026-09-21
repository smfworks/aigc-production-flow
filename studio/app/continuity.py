"""Continuity panel summary: entity-schedule + lock-diff from the imported pack.

Read/visualize + navigate only. Not a full NLE.
"""

from __future__ import annotations

from typing import Any

from .consistency import entity_schedule_problems, is_filled_schedule, lock_diff_problems
from .gates import as_list, as_record
from .deps import latest_revision
from .gates import gate_snapshot
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
    schedule_rows = [
        as_record(row) for row in as_list(pack.get("entitySchedule")) if is_filled_schedule(as_record(row))
    ]
    shots: list[dict[str, Any]] = []
    mismatches: list[str] = list(schedule_problems) + list(diff_problems)
    for shot in episode.shots:
        issues: list[str] = []
        for problem in schedule_problems:
            token = f"#{shot.sort_index + 1}"
            if token in problem or (shot.take and f"take {shot.take}" in problem.lower()):
                issues.append(problem)
        for problem in diff_problems:
            entities = (shot.entities or "").lower()
            if any(name and name.lower() in entities for name in _entity_names(pack)):
                if any(name.lower() in problem.lower() for name in _entity_names(pack) if name.lower() in entities):
                    issues.append(problem)
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
            }
        )
    return {
        "episode_id": episode.id,
        "project_id": episode.project_id,
        "honesty": "Read/visualize + navigate only. Not a full NLE. Pack zip remains the contract.",
        "all_green": bool(snapshot.get("all_green")),
        "red_gates": red,
        "entity_schedule": schedule_rows,
        "entity_schedule_problems": schedule_problems,
        "lock_diff_problems": diff_problems,
        "mismatches": mismatches,
        "shots": shots,
    }


def _entity_names(pack: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for raw in as_list(pack.get("characters")) + as_list(pack.get("props")):
        name = str(as_record(raw).get("name") or "").strip()
        if name:
            names.append(name)
    return names
