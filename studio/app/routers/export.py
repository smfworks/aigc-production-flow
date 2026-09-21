from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from ..agentbrief import agent_zip_bytes
from ..audit import AGENT_EXPORT, record
from ..deps import DbDep, get_episode, latest_revision
from ..rbac import ReadUser
from ..timeline import playlist_json, render_edl, render_fcpxml, render_playlist

router = APIRouter(tags=["export"])


def _require_shots(episode) -> None:
    if not episode.shots:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No edit-list shots yet. Fill the storyboard stage, or import a zip.",
        )


@router.get("/api/episodes/{episode_id}/export/edl")
def export_edl(episode_id: str, user: ReadUser, db: DbDep) -> PlainTextResponse:
    episode = get_episode(db, episode_id, user)
    _require_shots(episode)
    body = render_edl(episode)
    filename = f"{episode.title or 'episode'}.edl"
    return PlainTextResponse(
        body,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/episodes/{episode_id}/export/fcpxml")
def export_fcpxml(episode_id: str, user: ReadUser, db: DbDep) -> Response:
    episode = get_episode(db, episode_id, user)
    _require_shots(episode)
    body = render_fcpxml(episode)
    filename = f"{episode.title or 'episode'}.xml"
    return Response(
        content=body,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/episodes/{episode_id}/export/playlist")
def export_playlist(episode_id: str, user: ReadUser, db: DbDep) -> JSONResponse:
    episode = get_episode(db, episode_id, user)
    _require_shots(episode)
    filename = f"{episode.title or 'episode'}-playlist.json"
    return JSONResponse(
        content=render_playlist(episode),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/episodes/{episode_id}/export/playlist.txt")
def export_playlist_download(episode_id: str, user: ReadUser, db: DbDep) -> PlainTextResponse:
    episode = get_episode(db, episode_id, user)
    _require_shots(episode)
    filename = f"{episode.title or 'episode'}-playlist.json"
    return PlainTextResponse(
        playlist_json(episode),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/episodes/{episode_id}/export/agent")
def export_agent(episode_id: str, user: ReadUser, db: DbDep) -> Response:
    """Zip for Hermes / OpenClaw / Grok: pack + brief. Does not call Comfy."""
    episode = get_episode(db, episode_id, user)
    revision = latest_revision(episode)
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pack yet. Start a blank pack, template, or brain dump before exporting for an agent.",
        )
    data, filename = agent_zip_bytes(episode, revision)
    record(
        db,
        actor=user.name,
        action=AGENT_EXPORT,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="pack",
        entity_id=revision.id,
        detail={"filename": filename, "called_comfy": False, "generate_ready": False},
    )
    db.commit()
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
