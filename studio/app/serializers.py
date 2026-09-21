from .models import Episode, PackRevision, Project, Shot
from .schemas import CandidateOut, ContinuityReceiptOut, EpisodeOut, PackRevisionSummary, ProjectOut, ShotOut


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
        synopsis=episode.synopsis or "",
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
