from fastapi import APIRouter, HTTPException, status

from ..deps import DbDep, UserDep, get_episode, touch
from ..models import Comment, utcnow
from ..schemas import CommentCreate, CommentOut

router = APIRouter(tags=["comments"])


@router.get("/api/episodes/{episode_id}/comments", response_model=list[CommentOut])
def list_comments(episode_id: str, _user: UserDep, db: DbDep) -> list[CommentOut]:
    episode = get_episode(db, episode_id)
    return [CommentOut.model_validate(row) for row in episode.comments]


@router.post(
    "/api/episodes/{episode_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    episode_id: str, body: CommentCreate, user: UserDep, db: DbDep
) -> CommentOut:
    episode = get_episode(db, episode_id)
    author = (body.author or user.name).strip() or user.name
    comment = Comment(episode_id=episode.id, author=author, body=body.body.strip())
    if not comment.body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment body is empty.")
    db.add(comment)
    episode.updated_at = utcnow()
    touch(episode.project)
    db.commit()
    db.refresh(comment)
    return CommentOut.model_validate(comment)
