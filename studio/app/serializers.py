from .models import Episode, PackRevision, Project
from .schemas import EpisodeOut, PackRevisionSummary, ProjectOut


def project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        slug=project.slug,
        description=project.description or "",
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
