from .models import Episode, MediaAsset, PackRevision, Project, Shot
from .schemas import (
    CandidateOut,
    ContinuityReceiptOut,
    EpisodeOut,
    MediaAssetOut,
    PackRevisionSummary,
    ProjectOut,
    ShotOut,
)


def media_out(asset: MediaAsset) -> MediaAssetOut:
    status = asset.approval_status if asset.approval_status in {"draft", "approved"} else "draft"
    return MediaAssetOut(
        id=asset.id,
        episode_id=asset.episode_id,
        kind=asset.kind,  # type: ignore[arg-type]
        original_name=asset.original_name,
        stored_name=asset.stored_name,
        content_type=asset.content_type,
        path=asset.path,
        entity_label=asset.entity_label or "",
        entity_type=asset.entity_type or "",
        notes=asset.notes or "",
        created_by=asset.created_by,
        created_at=asset.created_at,
        approval_status=status,  # type: ignore[arg-type]
        approved_by=asset.approved_by or "",
        approved_at=asset.approved_at,
        shot_id=asset.shot_id or None,
        edit_row_id=asset.edit_row_id or "",
        lock_keywords=asset.lock_keywords or "",
        approved=status == "approved",
    )


def project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        slug=project.slug,
        description=project.description or "",
        still_adapter=project.still_adapter or "stub",
        clip_adapter=project.clip_adapter or "stub",
        budget_cap_units=project.budget_cap_units,
        budget_hard_stop=bool(project.budget_hard_stop),
        retention_days=project.retention_days,
        director_state=project.director_state if isinstance(project.director_state, dict) else {},
        episode_count=len(project.episodes),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def revision_summary(revision: PackRevision | None) -> PackRevisionSummary | None:
    if not revision:
        return None
    return PackRevisionSummary.model_validate(revision)


def episode_out(episode: Episode) -> EpisodeOut:
    latest = episode.revisions[0] if episode.revisions else None
    return EpisodeOut(
        id=episode.id,
        project_id=episode.project_id,
        title=episode.title,
        chapter=episode.chapter,
        season=episode.season or 1,
        sequence=episode.sequence_index or episode.chapter or 1,
        synopsis=episode.synopsis or "",
        log_line=episode.log_line or "",
        map_notes=episode.map_notes or "",
        dialogue=episode.dialogue or "",
        review_state=episode.review_state,  # type: ignore[arg-type]
        latest_revision=revision_summary(latest),
        comment_count=len(episode.comments),
        media_count=len(episode.media),
        shot_count=len(episode.shots),
        created_at=episode.created_at,
        updated_at=episode.updated_at,
    )


def shot_out(shot: Shot) -> ShotOut:
    from .preview import is_hop1_required, pack_of, receipt_out

    pack = pack_of(shot.episode) if shot.episode else {}
    preview: ContinuityReceiptOut | None = receipt_out(shot.receipt)
    return ShotOut(
        id=shot.id,
        episode_id=shot.episode_id,
        pack_revision_id=shot.pack_revision_id,
        edit_row_id=shot.edit_row_id,
        sort_index=shot.sort_index,
        song_t=shot.song_t or "",
        join=shot.join or "",
        take=shot.take or "",
        location_grade=shot.location_grade or "",
        camera_verb=shot.camera_verb or "",
        action=shot.action or "",
        entities=shot.entities or "",
        readiness=shot.readiness,  # type: ignore[arg-type]
        candidates=[CandidateOut.model_validate(row) for row in shot.candidates],
        hop1_required=is_hop1_required(shot, pack) if shot.episode else False,
        preview=preview,
        created_at=shot.created_at,
        updated_at=shot.updated_at,
    )
