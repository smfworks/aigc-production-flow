import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..deps import DbDep, get_episode
from ..presence import heartbeat, list_active, prune, ttl_seconds
from ..rbac import ReadUser
from ..schemas import PresenceBeat, PresenceOut

router = APIRouter(tags=["presence"])


def _out(row, ttl: int) -> PresenceOut:
    return PresenceOut(
        user_name=row.user_name,
        role=row.role or "",
        shot_id=row.shot_id or "",
        last_seen=row.last_seen,
        ttl_seconds=ttl,
    )


@router.post("/api/episodes/{episode_id}/presence", response_model=list[PresenceOut])
def beat(
    episode_id: str,
    user: ReadUser,
    db: DbDep,
    body: PresenceBeat | None = None,
) -> list[PresenceOut]:
    episode = get_episode(db, episode_id)
    prune(db)
    payload = body or PresenceBeat()
    heartbeat(
        db,
        episode_id=episode.id,
        user_name=user.name,
        role=user.role,
        shot_id=payload.shot_id,
    )
    ttl = ttl_seconds()
    return [_out(row, ttl) for row in list_active(db, episode.id)]


@router.get("/api/episodes/{episode_id}/presence", response_model=list[PresenceOut])
def who(
    episode_id: str,
    _user: ReadUser,
    db: DbDep,
) -> list[PresenceOut]:
    episode = get_episode(db, episode_id)
    prune(db)
    ttl = ttl_seconds()
    return [_out(row, ttl) for row in list_active(db, episode.id)]


@router.get("/api/episodes/{episode_id}/presence/stream")
async def stream_presence(
    episode_id: str,
    user: ReadUser,
    db: DbDep,
    shot_id: str | None = Query(default=None),
):
    """Optional SSE of who's on the episode. Poll GET if EventSource is awkward."""
    get_episode(db, episode_id)
    ttl = ttl_seconds()

    async def events():
        from ..database import SessionLocal

        while True:
            session = SessionLocal()
            try:
                prune(session)
                heartbeat(
                    session,
                    episode_id=episode_id,
                    user_name=user.name,
                    role=user.role,
                    shot_id=shot_id,
                )
                rows = list_active(session, episode_id)
                payload = [
                    {
                        "user_name": row.user_name,
                        "role": row.role or "",
                        "shot_id": row.shot_id or "",
                        "last_seen": row.last_seen.isoformat() if row.last_seen else None,
                        "ttl_seconds": ttl,
                    }
                    for row in rows
                ]
                yield f"data: {json.dumps(payload)}\n\n"
            finally:
                session.close()
            await asyncio.sleep(min(15, max(3, ttl / 4)))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
