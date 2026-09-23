"""Exact prompt preview before a still or clip job is queued."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .adapters.health import health_for
from .adapters.registry import resolve_adapter_name
from .adapters.role_workflow import (
    RoleWorkflowError,
    h3_profile_text,
    h3_sections,
    parse_workflow,
)
from .config import get_settings
from .models import Episode, PromptDraft, Shot, utcnow
from .precheck import hop1_enqueue_blockers
from .preview import extend_ok, receipt_blockers
from .mentions import asset_mention_refs, mention_tokens
from .workflows import filled_graph, get_workflow, workflow_has_video_input

GENERATE_TYPES = {"still-sheet", "still-plate", "clip-hop1", "clip-extend"}
REF_ROLES = ("identity-lock", "motion", "environment", "audio")
_ROLE_CANONICAL = {
    "identity-lock": "character",
    "motion": "video",
    "environment": "location",
    "audio": "audio",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _pack(episode: Episode) -> dict[str, Any]:
    revision = episode.revisions[0] if episode.revisions else None
    if revision is None or not isinstance(revision.pack_json, dict):
        return {}
    return revision.pack_json


def _scope(pack: dict[str, Any]) -> dict[str, Any]:
    meta = pack.get("studioMeta") if isinstance(pack.get("studioMeta"), dict) else {}
    director = meta.get("director") if isinstance(meta.get("director"), dict) else {}
    scope = director.get("scope") if isinstance(director.get("scope"), dict) else {}
    return scope


def _negative(payload: dict[str, Any], pack: dict[str, Any]) -> str:
    explicit = _text(payload.get("negative"))
    if explicit:
        return explicit[:4000]
    scope = _scope(pack)
    parts = [
        _text(scope.get("negative_constraints")),
        _text(scope.get("must_nots")),
        _text(scope.get("claim_bans")),
    ]
    return "\n".join(part for part in parts if part)[:4000]


def _base_prompt(payload: dict[str, Any], episode: Episode, shot: Shot | None) -> str:
    explicit = _text(payload.get("prompt") or payload.get("text"))
    if explicit:
        return explicit[:8000]
    if shot is not None and _text(shot.action):
        return _text(shot.action)[:8000]
    if _text(episode.log_line):
        return _text(episode.log_line)[:8000]
    return _text(episode.synopsis)[:8000]


def _refs(episode: Episode, shot: Shot | None, payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    supplied = payload.get("refs")
    if isinstance(supplied, list):
        for ref in supplied:
            if not isinstance(ref, dict):
                continue
            rows.append(
                {
                    "role": _text(ref.get("role")) or "image",
                    "label": _text(ref.get("label")),
                    "value": _text(ref.get("value")),
                    "source": "payload",
                }
            )
    for asset in episode.media:
        role = _text(getattr(asset, "ref_role", ""))
        if role not in REF_ROLES:
            continue
        if shot is not None and asset.shot_id and asset.shot_id not in {shot.id, ""}:
            continue
        rows.append(
            {
                "role": _ROLE_CANONICAL[role],
                "ref_role": role,
                "label": asset.entity_label or asset.original_name,
                "value": asset.original_name,
                "media_id": asset.id,
                "source": "asset",
            }
        )
    mentioned, unresolved = asset_mention_refs(_text(payload.get("prompt") or payload.get("text")), list(episode.media))
    seen = {str(row.get("media_id") or "") for row in rows}
    for ref in mentioned:
        if ref.get("media_id") and str(ref["media_id"]) in seen:
            continue
        rows.append(ref)
    if unresolved and mention_tokens(_text(payload.get("prompt") or payload.get("text"))):
        rows.append(
            {
                "role": "",
                "label": ", ".join(f"@{token}" for token in unresolved),
                "value": "",
                "source": "mention",
                "bound": False,
            }
        )
    return rows


def _previous_shot(episode: Episode, shot: Shot | None, token: str) -> Shot | None:
    ordered = sorted(episode.shots, key=lambda row: (row.sort_index, row.id))
    if token and token not in {"previous", "timeline", "auto"}:
        return next((row for row in ordered if row.id == token), None)
    if shot is None:
        return ordered[-1] if ordered else None
    prior = [row for row in ordered if row.sort_index < shot.sort_index]
    return prior[-1] if prior else None


def _video_file(episode: Episode, shot: Shot | None) -> tuple[bool, str]:
    if shot is None:
        return False, ""
    fixture = ""
    for asset in episode.media:
        if asset.shot_id != shot.id and asset.edit_row_id != shot.edit_row_id:
            continue
        name = (asset.original_name or "").lower()
        ctype = (asset.content_type or "").lower()
        if name.endswith(".json") or ctype == "application/json":
            fixture = asset.original_name or "fixture.json"
            continue
        if ctype.startswith("video/") or name.endswith((".mp4", ".webm", ".mov")):
            return True, asset.path or asset.original_name
    if fixture:
        return False, f"fixture:{fixture}"
    return False, ""


def continue_decision(
    episode: Episode,
    shot: Shot | None,
    payload: dict[str, Any],
    *,
    live: bool,
) -> dict[str, Any]:
    token = _text(payload.get("continue_from"))
    requested = bool(token) or bool(payload.get("continue"))
    if not requested and shot is not None and shot.join == "continue" and payload.get("honor_join"):
        requested = True
        token = token or "previous"
    workflow_id = _text(payload.get("workflow_id"))
    has_video = workflow_has_video_input(workflow_id) if workflow_id else False
    previous = _previous_shot(episode, shot, token) if requested else None
    video_ok, video_note = _video_file(episode, previous) if previous else (False, "")
    warning = ""
    allowed = True
    if requested and not workflow_id:
        allowed = False
        warning = (
            "Continue-from-previous needs a role-tagged workflow with (Input:video). "
            "None is selected, so Generate stays off."
        )
    elif requested and not has_video:
        allowed = False
        warning = (
            f"Workflow {workflow_id} has no (Input:video) role. "
            "Continue-from-previous is disabled. Generate stays off until you pick an extend workflow."
        )
    elif requested and previous is None:
        allowed = False
        warning = "No previous timeline clip to continue from. Generate stays off."
    elif requested and not video_ok:
        if live:
            allowed = False
            warning = (
                "The previous clip is not a local video file"
                + (f" ({video_note})." if video_note else ".")
                + " A live lane will not be sent a fixture receipt. Generate stays off."
            )
        else:
            warning = (
                "The previous clip is not a local video file"
                + (f" ({video_note})." if video_note else ".")
                + " Stub enqueue will not pretend a latent was loaded."
            )
    return {
        "requested": requested,
        "allowed": allowed,
        "warning": warning,
        "workflow_id": workflow_id,
        "has_video_input": has_video,
        "previous_shot_id": previous.id if previous else "",
        "previous_edit_row": previous.edit_row_id if previous else "",
        "video_resolved": video_ok,
        "video_note": video_note,
    }


def _cause(adapter: str) -> tuple[bool, str]:
    report = health_for(adapter)
    live = bool(report.get("live")) and not bool(report.get("not_live"))
    detail = _text(report.get("detail")) or "No health detail."
    if adapter == "stub" or not live:
        return False, detail
    if not report.get("ok"):
        return True, f"Live adapter {adapter} is not usable. Cause: {detail}"
    return True, detail


def _gate_block(job_type: str, episode: Episode, shot: Shot | None) -> str:
    if job_type == "clip-hop1":
        blocked = hop1_enqueue_blockers(episode, shot)
        if not blocked:
            return ""
        if isinstance(blocked, dict):
            return _text(blocked.get("message")) or "Hop-1 gates are not green."
        return str(blocked)
    if job_type == "clip-extend":
        if shot is None or not extend_ok(shot.receipt):
            blockers = ["clip-extend requires a shot."] if shot is None else receipt_blockers(shot.receipt, for_extend=True)
            return " ".join(blockers) or "Extend is blocked until hop-1 is watched."
    return ""


def build_preview(
    db: Session,
    *,
    episode: Episode,
    user_name: str,
    job_type: str,
    shot: Shot | None,
    payload: dict[str, Any] | None,
    adapter: str | None,
) -> PromptDraft:
    if job_type not in GENERATE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Prompt preview is for {', '.join(sorted(GENERATE_TYPES))}.",
        )
    body = dict(payload) if isinstance(payload, dict) else {}
    cfg = get_settings()
    project = episode.project
    resolved = resolve_adapter_name(job_type, cfg, requested=adapter or _text(body.get("adapter")) or None, project=project)
    pack = _pack(episode)
    prompt = _base_prompt(body, episode, shot)
    negative = _negative(body, pack)
    refs = _refs(episode, shot, {**body, "prompt": prompt})
    workflow_id = _text(body.get("workflow_id"))
    contract: dict[str, Any] = {}
    if workflow_id:
        try:
            loaded = get_workflow(workflow_id)
        except HTTPException:
            raise
        graph = loaded["graph"]
        try:
            contract = parse_workflow(graph)
        except RoleWorkflowError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        filled_graph(
            workflow_id,
            {
                "prompt": prompt,
                "negative": negative,
                "refs": refs,
                "duration": body.get("duration", body.get("seconds")),
                "seed": body.get("seed"),
                "width": body.get("width"),
                "height": body.get("height"),
                "video": body.get("video"),
            },
        )
    live, cause = _cause(resolved)
    decision = continue_decision(episode, shot, {**body, "workflow_id": workflow_id}, live=live)
    gate = _gate_block(job_type, episode, shot)
    generate_enabled = True
    warning = decision["warning"]
    if decision["requested"] and not decision["allowed"]:
        generate_enabled = False
    if live and "not usable" in cause:
        generate_enabled = False
        warning = warning or cause
    if gate:
        generate_enabled = False
        warning = warning or gate
    unbound = [str(ref.get("label") or "") for ref in refs if ref.get("source") == "mention" and ref.get("bound") is False]
    if unbound:
        mention_warning = (
            f"{unbound[0]} has no sheet or plate slot. The mention was not bound. Nothing was created."
        )
        warning = f"{warning} {mention_warning}".strip() if warning else mention_warning
    profile = contract.get("prompt_profile") or ""
    sections = None
    if profile == "h3":
        scope = _scope(pack)
        subjects = ", ".join(
            str(ref.get("label") or ref.get("value") or "")
            for ref in refs
            if ref.get("role") in {"character", "identity-lock"}
        )
        look = ""
        if isinstance(pack.get("look"), dict):
            look = _text(pack["look"].get("styleLine"))
        sections = h3_sections(
            prompt=prompt,
            subjects=subjects,
            location=_text(shot.location_grade) if shot else "",
            action=prompt,
            camera=_text(shot.camera_verb) if shot else "",
            look=look,
            audio=_text(pack.get("speech")) or _text(scope.get("deliverables")),
        )
    preview = {
        "prompt": prompt,
        "negative": negative,
        "refs": refs,
        "adapter": resolved,
        "live": live and resolved != "stub",
        "called_comfy": False,
        "stub": resolved == "stub" or not live,
        "cause": cause,
        "workflow_id": workflow_id,
        "roles": contract.get("slots") or [],
        "prompt_profile": profile,
        "h3_sections": sections,
        "continue": decision,
        "gate_block": gate,
        "generate_enabled": generate_enabled,
        "warning": warning,
        "honesty": (
            "Preview only. Nothing was queued. "
            "Stub means a fixture receipt, not a Comfy render. "
            "called_comfy stays false until a live lane accepts a prompt."
        ),
    }
    draft = PromptDraft(
        episode_id=episode.id,
        shot_id=shot.id if shot else None,
        job_type=job_type,
        adapter=resolved,
        status="draft",
        body=preview,
        created_by=user_name,
    )
    db.add(draft)
    db.flush()
    return draft


def get_draft(db: Session, draft_id: str, episode_id: str | None = None) -> PromptDraft:
    draft = db.get(PromptDraft, draft_id)
    if draft is None or (episode_id and draft.episode_id != episode_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt draft not found.")
    return draft


def update_draft(draft: PromptDraft, *, prompt: str | None, negative: str | None) -> PromptDraft:
    if draft.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Prompt draft is {draft.status}. Save only works on an open draft.",
        )
    body = dict(draft.body) if isinstance(draft.body, dict) else {}
    if prompt is not None:
        body["prompt"] = prompt.strip()[:8000]
    if negative is not None:
        body["negative"] = negative.strip()[:4000]
    body["called_comfy"] = False
    draft.body = body
    flag_modified(draft, "body")
    draft.updated_at = utcnow()
    return draft


def rewrite_draft(draft: PromptDraft) -> PromptDraft:
    if draft.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Prompt draft is {draft.status}. Rewrite only works on an open draft.",
        )
    body = dict(draft.body) if isinstance(draft.body, dict) else {}
    if body.get("prompt_profile") != "h3":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "profile_not_requested",
                "message": (
                    "This workflow does not ask for an H3 6-section profile. "
                    "Rewrite stays off. Tag the prompt node with (Profile:h3) when you want it."
                ),
            },
        )
    sections = body.get("h3_sections") if isinstance(body.get("h3_sections"), dict) else None
    if not sections:
        sections = h3_sections(prompt=_text(body.get("prompt")))
    text = h3_profile_text(sections)
    body["prompt"] = text
    body["h3_sections"] = sections
    body["rewrite_source"] = "structured"
    body["model_ran"] = False
    body["called_comfy"] = False
    draft.body = body
    flag_modified(draft, "body")
    draft.updated_at = utcnow()
    return draft


def cancel_draft(draft: PromptDraft) -> PromptDraft:
    if draft.status == "enqueued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This preview was already used to enqueue. Cancel the job instead.",
        )
    draft.status = "cancelled"
    draft.updated_at = utcnow()
    return draft


def consume_preview(db: Session, preview_id: str, episode: Episode, job_type: str) -> dict[str, Any]:
    draft = get_draft(db, preview_id, episode.id)
    if draft.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "preview_cancelled", "message": "This prompt draft was cancelled. Nothing was queued."},
        )
    if draft.status == "enqueued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "preview_used", "message": "This prompt draft was already enqueued."},
        )
    if draft.job_type != job_type:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "preview_mismatch", "message": "Preview job type does not match this enqueue."},
        )
    body = dict(draft.body) if isinstance(draft.body, dict) else {}
    decision = body.get("continue") if isinstance(body.get("continue"), dict) else {}
    if decision.get("requested") and not decision.get("allowed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "continue_blocked",
                "message": decision.get("warning") or "Continue-from-previous is disabled.",
            },
        )
    if body.get("generate_enabled") is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "preview_blocked",
                "message": body.get("warning") or "Generate is disabled for this preview.",
                "warning": body.get("warning") or "",
            },
        )
    return {
        "prompt": body.get("prompt") or "",
        "negative": body.get("negative") or "",
        "refs": body.get("refs") or [],
        "workflow_id": body.get("workflow_id") or "",
        "continue_from": (decision.get("previous_shot_id") or "") if decision.get("requested") else "",
        "continue_requested": bool(decision.get("requested")),
        "adapter": draft.adapter or "stub",
        "preview_id": draft.id,
        "called_comfy": False,
        "stub": bool(body.get("stub")),
    }


def mark_preview_enqueued(db: Session, preview_id: str) -> None:
    if not preview_id:
        return
    draft = db.get(PromptDraft, preview_id)
    if draft is None or draft.status != "draft":
        return
    draft.status = "enqueued"
    draft.updated_at = utcnow()


def require_preview_or_raise(payload: dict[str, Any], job_type: str) -> None:
    if job_type not in GENERATE_TYPES:
        return
    if not get_settings().require_prompt_preview:
        return
    if _text(payload.get("preview_id")):
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "preview_required",
            "message": (
                "Generate opens a prompt preview first. "
                "Edit, save a draft, or cancel. Nothing was queued."
            ),
        },
    )
