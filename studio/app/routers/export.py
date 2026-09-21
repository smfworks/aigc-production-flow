from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from ..deps import DbDep, get_episode
from ..rbac import ReadUser
from ..timeline import playlist_json, render_edl, render_fcpxml, render_playlist

router = APIRouter(tags=["export"])


def _require_shots(episode) -> None:
    if not episode.shots:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No edit-list shots yet. Import a pack zip first.",
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
