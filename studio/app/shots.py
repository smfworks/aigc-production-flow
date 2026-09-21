"""Map pack edit-list rows to shots and run human-in-the-loop candidate confirm."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .gates import as_list, as_record
from .models import (
    CANDIDATE_STATUSES,
    ENTITY_TYPES,
    SHOT_READINESS,
    Episode,
    MediaAsset,
    PackRevision,
    Shot,
    ShotCandidate,
    utcnow,
)


def _shot_out_ready(shot: Shot) -> None:
    pending = [row for row in shot.candidates if row.status == "pending"]
    accepted = [row for row in shot.candidates if row.status == "accepted"]
    linked = [row for row in shot.candidates if row.status == "linked"]
    if shot.readiness == "ready":
        if pending or accepted:
            shot.readiness = "candidates" if pending else "linked"
        return
    if pending or accepted:
        shot.readiness = "candidates"
    elif linked:
        shot.readiness = "linked"
    else:
        shot.readiness = "draft"


def refresh_readiness(shot: Shot) -> None:
    if shot.readiness == "ready":
        pending = any(row.status == "pending" for row in shot.candidates)
        unlinked = any(row.status == "accepted" for row in shot.candidates)
        if pending or unlinked:
            shot.readiness = "candidates" if pending or unlinked else "linked"
        return
    _shot_out_ready(shot)
    shot.updated_at = utcnow()


def _row_fields(raw: Any, index: int) -> dict[str, Any]:
    row = as_record(raw)
    return {
        "edit_row_id": str(row.get("id") or f"row-{index + 1}"),
        "sort_index": index,
        "song_t": str(row.get("songT") or ""),
        "join": str(row.get("join") or ""),
        "take": str(row.get("take") or ""),
        "location_grade": str(row.get("locationGrade") or ""),
        "camera_verb": str(row.get("cameraVerb") or ""),
        "action": str(row.get("action") or ""),
        "entities": str(row.get("entities") or ""),
    }


def sync_shots_from_pack(db: Session, episode: Episode, revision: PackRevision) -> list[Shot]:
    pack = revision.pack_json if isinstance(revision.pack_json, dict) else {}
    rows = as_list(pack.get("editList"))
    keep_ids: set[str] = set()
    existing = {shot.edit_row_id: shot for shot in episode.shots}
    for index, raw in enumerate(rows):
        fields = _row_fields(raw, index)
        keep_ids.add(fields["edit_row_id"])
        shot = existing.get(fields["edit_row_id"])
        if shot is None:
            shot = Shot(episode_id=episode.id, readiness="draft")
            db.add(shot)
        shot.pack_revision_id = revision.id
        for key, value in fields.items():
            setattr(shot, key, value)
        refresh_readiness(shot)
    for shot in list(episode.shots):
        if shot.edit_row_id not in keep_ids:
            db.delete(shot)
    db.flush()
    return list(episode.shots)


def known_entities(pack: dict[str, Any], media: list[MediaAsset]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for raw in as_list(pack.get("characters")):
        name = str(as_record(raw).get("name") or "").strip()
        if name:
            found.append(("character", name))
    for raw in as_list(pack.get("props")):
        name = str(as_record(raw).get("name") or "").strip()
        if name:
            found.append(("prop", name))
    for asset in media:
        label = (asset.entity_label or "").strip()
        if not label:
            continue
        kind = asset.entity_type if asset.entity_type in ENTITY_TYPES else (
            "costume" if asset.kind == "costume" else "scene"
        )
        found.append((kind, label))
    return found


def extract_candidates_for_shot(
    shot: Shot,
    pack: dict[str, Any],
    media: list[MediaAsset],
) -> list[ShotCandidate]:
    blob = " ".join([shot.action, shot.entities, shot.location_grade, shot.take])
    created: list[ShotCandidate] = []
    existing = {(row.kind, row.label.strip().lower()) for row in shot.candidates}
    for kind, name in known_entities(pack, media):
        if not re.search(rf"\b{re.escape(name)}\b", blob, flags=re.I):
            continue
        key = (kind, name.strip().lower())
        if key in existing:
            continue
        candidate = ShotCandidate(
            shot_id=shot.id,
            kind=kind,
            label=name,
            evidence=f"Stub extract from shot text ({kind}:{name}). Confirm by hand — never auto generate-ok.",
            status="pending",
            source="stub",
        )
        shot.candidates.append(candidate)
        existing.add(key)
        created.append(candidate)
    location = shot.location_grade.split("/")[0].strip()
    if location and ("scene", location.lower()) not in existing:
        if location.lower() not in {"", "—", "-"}:
            candidate = ShotCandidate(
                shot_id=shot.id,
                kind="scene",
                label=location,
                evidence="Stub scene from location / grade. Confirm or ignore.",
                status="pending",
                source="stub",
            )
            shot.candidates.append(candidate)
            created.append(candidate)
    if re.search(r"\b(costume|wardrobe|cloak|tunic)\b", blob, flags=re.I):
        if ("costume", "wardrobe") not in existing:
            candidate = ShotCandidate(
                shot_id=shot.id,
                kind="costume",
                label="wardrobe",
                evidence="Stub costume mention. Link a costume asset or ignore.",
                status="pending",
                source="stub",
            )
            shot.candidates.append(candidate)
            created.append(candidate)
    refresh_readiness(shot)
    return created


def set_readiness(shot: Shot, readiness: str) -> None:
    if readiness not in SHOT_READINESS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown shot readiness.")
    pending = [row for row in shot.candidates if row.status == "pending"]
    accepted = [row for row in shot.candidates if row.status == "accepted"]
    if readiness == "ready" and (pending or accepted):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "shot_not_prepared",
                "message": (
                    "Refuse ready until pending/accepted candidates are ignored or linked. "
                    "ready means prepared, not generating. generate-ok is a separate review stamp."
                ),
            },
        )
    shot.readiness = readiness
    shot.updated_at = utcnow()


def apply_candidate_update(
    db: Session,
    candidate: ShotCandidate,
    status_value: str | None,
    linked_asset_id: str | None,
    linked_ref: str | None,
) -> None:
    if status_value and status_value not in CANDIDATE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown candidate status.")
    if linked_asset_id:
        asset = db.get(MediaAsset, linked_asset_id)
        if not asset or asset.episode_id != candidate.shot.episode_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found on this episode.")
        candidate.linked_asset_id = linked_asset_id
        if not status_value:
            status_value = "linked"
    if linked_ref is not None:
        candidate.linked_ref = linked_ref.strip()
        if candidate.linked_ref and not status_value:
            status_value = "linked"
    if status_value == "linked" and not candidate.linked_asset_id and not candidate.linked_ref:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link requires a media asset or a pack ref (character:name / prop:name / scene:name / costume:name).",
        )
    if status_value:
        candidate.status = status_value
    candidate.updated_at = utcnow()
    refresh_readiness(candidate.shot)
