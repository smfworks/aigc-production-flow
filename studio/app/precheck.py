"""batch-precheck: gates green + shot ready + plates bound before hop-1 enqueue."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .deps import latest_revision
from .models import Episode, Shot
from .preview import hop1_required_shots, pack_of, plates_bound_for_shot


def _shot_problems(episode: Episode, shot: Shot, pack: dict[str, Any]) -> list[dict[str, str]]:
    problems: list[dict[str, str]] = []
    if shot.readiness != "ready":
        problems.append(
            {
                "code": "shot_not_ready",
                "message": (
                    f"Shot #{shot.sort_index + 1} (take {shot.take or '—'}) is {shot.readiness}, "
                    "not ready. ready means prepared, not generating."
                ),
                "shot_id": shot.id,
            }
        )
    ok, detail = plates_bound_for_shot(shot, pack, list(episode.media))
    if not ok:
        problems.append(
            {
                "code": "plates_unbound",
                "message": f"Shot #{shot.sort_index + 1}: {detail}",
                "shot_id": shot.id,
            }
        )
    return problems


def run_batch_precheck(
    _db: Session,
    episode: Episode,
    shot: Shot | None = None,
) -> dict[str, Any]:
    revision = latest_revision(episode)
    pack = pack_of(episode)
    problems: list[dict[str, str]] = []
    gates_green = bool(revision and revision.all_gates_green)
    if not revision:
        problems.append(
            {
                "code": "no_pack",
                "message": "Import a pack zip before hop-1. Pack zip is the contract.",
                "shot_id": shot.id if shot else "",
            }
        )
    elif not gates_green:
        problems.append(
            {
                "code": "gates_not_green",
                "message": (
                    "Refuse hop-1 until the latest pack revision is all-green "
                    "(nine README gates plus entity-schedule and lock-diff)."
                ),
                "shot_id": shot.id if shot else "",
            }
        )

    targets: list[Shot]
    if shot is not None:
        targets = [shot]
    else:
        targets = hop1_required_shots(episode, pack)

    if not targets and revision:
        problems.append(
            {
                "code": "no_hop1",
                "message": "No required hop-1 shots. Import a pack with hop-1 planned takes.",
                "shot_id": "",
            }
        )

    shot_reports: list[dict[str, Any]] = []
    for row in targets:
        row_problems = _shot_problems(episode, row, pack) if revision else []
        problems.extend(row_problems)
        bound, bound_detail = plates_bound_for_shot(row, pack, list(episode.media)) if revision else (False, "no pack")
        shot_reports.append(
            {
                "shot_id": row.id,
                "take": row.take,
                "sort_index": row.sort_index,
                "readiness": row.readiness,
                "ready": row.readiness == "ready",
                "plates_bound": bound,
                "plates_detail": bound_detail,
            }
        )

    ok = not problems
    return {
        "ok": ok,
        "adapter": "stub",
        "engine": None,
        "claim": "Studio batch-precheck. No H3 or Qwen process ran.",
        "gates_green": gates_green,
        "shots": shot_reports,
        "problems": problems,
    }


def hop1_enqueue_blockers(episode: Episode, shot: Shot | None) -> dict[str, Any] | None:
    report = run_batch_precheck(None, episode, shot)  # type: ignore[arg-type]
    if report["ok"]:
        return None
    return {
        "code": "batch_precheck_failed",
        "message": (
            "Refuse clip-hop1 until batch-precheck is green: all gates, shot ready, plates bound."
        ),
        "problems": report["problems"],
        "precheck": report,
    }
