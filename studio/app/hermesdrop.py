"""Write a Hermes brief bundle to a local drop folder. This does not invoke Hermes."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agentbrief import README, build_agent_brief
from .config import get_settings
from .models import Episode, PackRevision
from .stitch import HERMES_STITCH_CONTRACT
from .timeline import playlist_json, render_edl

DROP_FILES = (
    "README.md",
    "agent-brief.json",
    "gate-snapshot.json",
    "pack.json",
    "playlist.json",
    "edit.edl",
    "hermes-handoff.json",
)


def handoff_root() -> Path:
    cfg = get_settings()
    raw = (cfg.handoff_root or "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        path = cfg.media_path.parent / "handoff"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def deep_link(run_id: str) -> str:
    return f"hermes://aigc/brief?run={run_id}"


def _write_tree(root: Path, files: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")


def write_drop(
    episode: Episode,
    revision: PackRevision,
    *,
    run_id: str,
    wizard_id: str = "",
    engines: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist the brief. hermes_ran stays false. called_comfy stays false."""
    pack = revision.pack_json if isinstance(revision.pack_json, dict) else {}
    brief = build_agent_brief(episode, revision)
    snapshot = revision.gate_snapshot if isinstance(revision.gate_snapshot, dict) else {}
    root = handoff_root()
    drop = root / run_id
    link = deep_link(run_id)
    engine = engines or {}
    payload = {
        "v": 1,
        "kind": "aigc-hermes-handoff",
        "agent_run_id": run_id,
        "wizard_id": wizard_id,
        "project_id": episode.project_id,
        "episode_id": episode.id,
        "revision_id": revision.id,
        "deep_link": link,
        "drop_dir": str(drop),
        "files": list(DROP_FILES),
        "open_latest": str(root / "latest.json"),
        "honesty": {
            "called_comfy": False,
            "hermes_ran": False,
            "generate_ready": False,
            "all_gates_green": bool(revision.all_gates_green),
            "still_live": bool(engine.get("still_live")),
            "clip_live": bool(engine.get("clip_live")),
            "still_label": engine.get("still_label") or "",
            "clip_label": engine.get("clip_label") or "",
            "produced_mp4": False,
            "note": (
                "Studio wrote this brief. Hermes has not been invoked. Comfy has not been called. "
                "Stitch is a concat plan until real video files exist. No MP4 was invented."
            ),
        },
        "stitch_contract": HERMES_STITCH_CONTRACT,
    }
    director = brief.get("director") if isinstance(brief.get("director"), dict) else None
    if director:
        payload["director"] = {
            "craft_lanes": director.get("craft_lanes") or [],
            "scope": director.get("scope") or {},
            "scope_note": director.get("scope_note") or "",
            "task_tree": director.get("task_tree") or [],
            "agents_ran": False,
            "called_comfy": False,
            "hermes_ran": False,
            "produced_mp4": False,
            "executes": False,
            "note": director.get("note") or "",
        }
    readme = (
        README
        + "\n## Drop folder\n\n"
        + "This folder is the Hermes handoff. Watch `latest.json` beside it for the newest brief.\n"
        + f"Deep link: `{link}`\n\n"
        + HERMES_STITCH_CONTRACT
        + "\n"
    )
    files = {
        "README.md": readme,
        "agent-brief.json": json.dumps(brief, indent=2),
        "gate-snapshot.json": json.dumps(snapshot, indent=2),
        "pack.json": json.dumps({"v": 2, "pack": pack}, indent=2, ensure_ascii=False),
        "playlist.json": playlist_json(episode),
        "edit.edl": render_edl(episode),
        "hermes-handoff.json": json.dumps(payload, indent=2),
    }
    _write_tree(drop, files)
    latest = {
        "agent_run_id": run_id,
        "wizard_id": wizard_id,
        "drop_dir": str(drop),
        "deep_link": link,
        "open": "hermes-handoff.json",
        "written_at": datetime.now(timezone.utc).isoformat(),
        "called_comfy": False,
        "hermes_ran": False,
        "produced_mp4": False,
        "note": payload["honesty"]["note"],
    }
    (root / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")
    _write_tree(root / "latest", files)
    extra = (get_settings().hermes_drop or "").strip()
    if extra:
        mirror = Path(extra).expanduser()
        _write_tree(mirror / run_id, files)
        _write_tree(mirror / "latest", files)
        (mirror / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")
    payload["drop_dir"] = str(drop)
    return payload


def forget_drop_tree(path: Path) -> None:
    """Test helper. Not used by the API."""
    if path.exists():
        shutil.rmtree(path)
