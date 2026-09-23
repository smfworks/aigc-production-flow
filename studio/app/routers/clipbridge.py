"""CLIP_BRIDGE plan, prompt files, and conform. Does not call Comfy or start Hermes."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..clipbridge import (
    ClipItem,
    StoryLock,
    apply_bridge,
    bridge_rows,
    clips_on,
    conform_execute,
    conform_plan,
    copy_handoff_states,
    load_forge_fixture,
    preflight,
    project_dir,
    retry_clip,
)
from ..deps import DbDep, get_episode
from ..rbac import EditUser, ReadUser
from ..serializers import shot_out

router = APIRouter(tags=["clip-bridge"])

HONESTY = (
    "CLIP_BRIDGE plan only. Comfy was not called. Hermes was not started. "
    "called_comfy is false. An MP4 is produced only when ffmpeg can conform real local videos."
)


class ClipBridgePut(BaseModel):
    story_lock: StoryLock
    clips: list[ClipItem]
    replace: bool = True


class FixtureIn(BaseModel):
    name: str = "forge_dawn"


class ConformIn(BaseModel):
    execute: bool = False


class RetryIn(BaseModel):
    clip_id: str = Field(min_length=1)


def _public(episode_id: str, lock: dict, clips: list, issues: list, shots: list | None = None) -> dict:
    return {
        "episode_id": episode_id,
        "ok": not issues,
        "issues": issues,
        "story_lock": lock,
        "clips": clips,
        "shots": shots or [],
        "project_dir": str(project_dir(episode_id)),
        "called_comfy": False,
        "hermes_ran": False,
        "produced_mp4": False,
        "honesty": HONESTY,
    }


def _issue_dicts(issues) -> list[dict]:
    return [issue.as_dict() for issue in issues]


@router.get("/api/episodes/{episode_id}/clip-bridge")
def get_bridge(episode_id: str, user: ReadUser, db: DbDep) -> dict:
    episode = get_episode(db, episode_id, user)
    lock = episode.story_lock if isinstance(episode.story_lock, dict) else {}
    if not lock.get("project_id"):
        return _public(episode.id, {}, [], [])
    parsed_lock = StoryLock.model_validate(lock)
    clips = clips_on(episode)
    issues = _issue_dicts(preflight(parsed_lock, clips))
    return _public(
        episode.id,
        parsed_lock.model_dump(),
        [clip.model_dump() for clip in clips],
        issues,
        [shot_out(shot) for shot in bridge_rows(episode)],
    )


@router.put("/api/episodes/{episode_id}/clip-bridge")
def put_bridge(episode_id: str, body: ClipBridgePut, user: EditUser, db: DbDep) -> dict:
    episode = get_episode(db, episode_id, user)
    result = apply_bridge(db, episode, body.story_lock, body.clips, replace=body.replace)
    db.commit()
    for shot in result["shots"]:
        db.refresh(shot)
    return _public(
        episode.id,
        body.story_lock.model_dump(),
        [clip.model_dump() for clip in result["clips"]],
        _issue_dicts(result["issues"]),
        [shot_out(shot) for shot in result["shots"]],
    )


@router.post("/api/episodes/{episode_id}/clip-bridge/fixture")
def post_fixture(episode_id: str, body: FixtureIn, user: EditUser, db: DbDep) -> dict:
    if body.name != "forge_dawn":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown CLIP_BRIDGE fixture.")
    episode = get_episode(db, episode_id, user)
    lock, clips = load_forge_fixture()
    result = apply_bridge(db, episode, lock, clips, replace=True)
    db.commit()
    for shot in result["shots"]:
        db.refresh(shot)
    return _public(
        episode.id,
        lock.model_dump(),
        [clip.model_dump() for clip in result["clips"]],
        _issue_dicts(result["issues"]),
        [shot_out(shot) for shot in result["shots"]],
    )


@router.post("/api/episodes/{episode_id}/clip-bridge/copy-handoff")
def post_copy(episode_id: str, user: EditUser, db: DbDep) -> dict:
    """Copy end_state into the next start_state with strip() only."""
    episode = get_episode(db, episode_id, user)
    lock_raw = episode.story_lock if isinstance(episode.story_lock, dict) else {}
    if not lock_raw.get("project_id"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No story lock on this episode.")
    lock = StoryLock.model_validate(lock_raw)
    copied = copy_handoff_states(clips_on(episode))
    result = apply_bridge(db, episode, lock, copied, replace=True)
    db.commit()
    for shot in result["shots"]:
        db.refresh(shot)
    return _public(
        episode.id,
        lock.model_dump(),
        [clip.model_dump() for clip in result["clips"]],
        _issue_dicts(result["issues"]),
        [shot_out(shot) for shot in result["shots"]],
    )


@router.post("/api/episodes/{episode_id}/clip-bridge/retry")
def post_retry(episode_id: str, body: RetryIn, user: EditUser, db: DbDep) -> dict:
    episode = get_episode(db, episode_id, user)
    try:
        result = retry_clip(db, episode, body.clip_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found on this bridge.") from exc
    db.commit()
    db.refresh(episode)
    lock = StoryLock.model_validate(episode.story_lock)
    clips = clips_on(episode)
    issues = _issue_dicts(preflight(lock, clips))
    payload = _public(
        episode.id,
        lock.model_dump(),
        [clip.model_dump() for clip in clips],
        issues,
        [shot_out(shot) for shot in bridge_rows(episode)],
    )
    payload["retried_clip_id"] = body.clip_id
    payload["states_before"] = result["states_before"]
    payload["lock_unchanged"] = json_equal(result["lock_before"], episode.story_lock)
    return payload


@router.post("/api/episodes/{episode_id}/clip-bridge/conform")
def post_conform(episode_id: str, body: ConformIn, user: EditUser, db: DbDep) -> dict:
    episode = get_episode(db, episode_id, user)
    clips = clips_on(episode)
    plan = conform_execute(project_dir(episode.id), clips) if body.execute else conform_plan(clips)
    plan["episode_id"] = episode.id
    plan["honesty"] = HONESTY
    plan["called_comfy"] = False
    plan["hermes_ran"] = False
    if not body.execute:
        plan["produced_mp4"] = False
        plan["reason"] = (
            "Conform plan only. Pass execute when every clip video is a real local file. "
            "No MP4 was invented."
        )
    return plan


def json_equal(before: str, after: dict) -> bool:
    return before == json.dumps(after, sort_keys=True)
