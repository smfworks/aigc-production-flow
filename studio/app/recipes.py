"""Local Create recipes. JSON on disk. Not a plaza and not a generate."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from .config import get_settings
from .director import tree_for
from .packzip import slugify
from .wizardpack import normalize_answers

RECIPE_KIND = "aigc-create-recipe"
_RECIPE_ID = re.compile(r"^skill_[a-z0-9_]+_v\d+\.\d+\.json$")
_VERSION = re.compile(r"_v(\d+)\.(\d+)\.json$")
_ORG = re.compile(r"^[A-Za-z0-9_-]{1,80}$")

HONESTY = {
    "called_comfy": False,
    "hermes_ran": False,
    "produced_mp4": False,
    "agents_ran": False,
    "note": (
        "A recipe prefills the Create wizard and the task tree. "
        "It does not generate, approve identities, call Comfy, start Hermes, or skip gates."
    ),
}


def recipe_root() -> Path:
    raw = (get_settings().recipe_root or "").strip()
    if raw:
        path = Path(raw).expanduser()
    else:
        path = get_settings().media_path.parent / "recipes"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _org_dir(org_id: str) -> Path:
    if not _ORG.fullmatch(org_id or ""):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization.")
    path = recipe_root() / org_id
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _filename(slug: str, version: str) -> str:
    return f"skill_{slug}_v{version}.json"


def _next_version(directory: Path, slug: str) -> str:
    best = (0, 0)
    for path in directory.glob(f"skill_{slug}_v*.json"):
        match = _VERSION.search(path.name)
        if not match:
            continue
        best = max(best, (int(match.group(1)), int(match.group(2))))
    if best == (0, 0):
        return "0.1"
    return f"{best[0]}.{best[1] + 1}"


def _check_id(recipe_id: str) -> str:
    name = Path(recipe_id or "").name
    if not _RECIPE_ID.fullmatch(name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found.")
    return name


def _summary(body: dict[str, Any], filename: str) -> dict[str, Any]:
    answers = body.get("answers") if isinstance(body.get("answers"), dict) else {}
    return {
        "id": filename,
        "filename": filename,
        "name": str(body.get("name") or filename),
        "version": str(body.get("version") or ""),
        "kind": RECIPE_KIND,
        "saved_at": str(body.get("saved_at") or ""),
        "format": str(answers.get("format") or ""),
        "honesty": HONESTY,
    }


def list_recipes(org_id: str) -> list[dict[str, Any]]:
    directory = _org_dir(org_id)
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("skill_*_v*.json")):
        if not _RECIPE_ID.fullmatch(path.name):
            continue
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(body, dict) or body.get("kind") != RECIPE_KIND:
            continue
        rows.append(_summary(body, path.name))
    rows.sort(key=lambda row: row["saved_at"], reverse=True)
    return rows


def read_recipe(org_id: str, recipe_id: str) -> dict[str, Any]:
    filename = _check_id(recipe_id)
    path = _org_dir(org_id) / filename
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found.")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found.") from exc
    if not isinstance(body, dict) or body.get("kind") != RECIPE_KIND:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found.")
    answers = body.get("answers") if isinstance(body.get("answers"), dict) else {}
    tree = body.get("task_tree") if isinstance(body.get("task_tree"), list) else answers.get("task_tree") or []
    return {
        **_summary(body, filename),
        "answers": answers,
        "task_tree": tree,
    }


def save_recipe(org_id: str, name: str, answers: dict[str, Any]) -> dict[str, Any]:
    title = (name or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name the recipe.")
    slug = slugify(title, "recipe").replace("-", "_")
    directory = _org_dir(org_id)
    version = _next_version(directory, slug)
    filename = _filename(slug, version)
    normalized = normalize_answers(answers)
    tree = tree_for(normalized)
    normalized["task_tree"] = tree
    body = {
        "kind": RECIPE_KIND,
        "version": version,
        "name": title[:80],
        "slug": slug,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "answers": normalized,
        "task_tree": tree,
        "honesty": HONESTY,
    }
    path = directory / filename
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return read_recipe(org_id, filename)
