"""Registered Comfy workflows. Builtins ship with the repo. Imports land on disk."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from .adapters.role_workflow import RoleWorkflowError, fill_workflow, parse_workflow, values_from_payload
from .config import get_settings
from .packzip import slugify

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,60}$")


def builtin_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "workflows"


def workflow_root() -> Path:
    raw = (get_settings().workflow_root or "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        path = get_settings().media_path.parent / "workflows"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _load_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow {path.name} is not valid JSON: {exc}",
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow {path.name} must be an API-format object.",
        )
    return data


def _summary(workflow_id: str, graph: dict[str, Any], *, source: str) -> dict[str, Any]:
    try:
        contract = parse_workflow(graph)
    except RoleWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {
        "id": workflow_id,
        "source": source,
        "prompt_profile": contract["prompt_profile"],
        "has_video_input": contract["has_video_input"],
        "asks_h3": contract["asks_h3"],
        "roles": [
            {
                "node_id": slot["node_id"],
                "direction": slot["direction"],
                "role": slot["role"],
                "canonical": slot["canonical"],
                "title": slot["title"],
            }
            for slot in contract["slots"]
        ],
        "note": (
            "Role tags are the contract. Import does not call Comfy. "
            "A registered graph is not proof a render ran."
        ),
    }


def list_workflows() -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(builtin_dir().glob("*.json")):
        workflow_id = path.stem
        graph = _load_file(path)
        found[workflow_id] = _summary(workflow_id, graph, source="builtin")
    root = workflow_root()
    for path in sorted(root.glob("*.json")):
        workflow_id = path.stem
        if not _ID.match(workflow_id):
            continue
        graph = _load_file(path)
        found[workflow_id] = _summary(workflow_id, graph, source="registered")
    return [found[key] for key in sorted(found)]


def _path_for(workflow_id: str) -> tuple[Path, str] | None:
    if not _ID.match(workflow_id):
        return None
    registered = workflow_root() / f"{workflow_id}.json"
    if registered.is_file():
        return registered, "registered"
    builtin = builtin_dir() / f"{workflow_id}.json"
    if builtin.is_file():
        return builtin, "builtin"
    return None


def get_workflow(workflow_id: str) -> dict[str, Any]:
    found = _path_for((workflow_id or "").strip())
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No role-tagged workflow named {workflow_id}.",
        )
    path, source = found
    graph = _load_file(path)
    summary = _summary(path.stem, graph, source=source)
    summary["graph"] = graph
    return summary


def register_workflow(name: str, graph: dict[str, Any]) -> dict[str, Any]:
    workflow_id = slugify(name or "", "workflow")
    if not _ID.match(workflow_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow name must slug to letters, numbers, and hyphens.",
        )
    if not isinstance(graph, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="graph must be Comfy API-format JSON (an object of nodes).",
        )
    try:
        parse_workflow(graph)
    except RoleWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    path = workflow_root() / f"{workflow_id}.json"
    path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    return get_workflow(workflow_id)


def load_graph(workflow_id: str) -> dict[str, Any]:
    return get_workflow(workflow_id)["graph"]


def filled_graph(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    graph = load_graph(workflow_id)
    try:
        return fill_workflow(graph, values_from_payload(payload))
    except RoleWorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def workflow_has_video_input(workflow_id: str) -> bool:
    if not (workflow_id or "").strip():
        return False
    try:
        contract = parse_workflow(load_graph(workflow_id))
    except (HTTPException, RoleWorkflowError):
        return False
    return bool(contract["has_video_input"])
