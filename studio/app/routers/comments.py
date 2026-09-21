from fastapi import APIRouter, HTTPException, Query, status

from ..audit import COMMENT_CREATE, COMMENT_RESOLVE, record
from ..deps import DbDep, get_episode, touch
from ..models import Comment, Shot, utcnow
from ..rbac import CommentUser, ReadUser
from ..schemas import CommentCreate, CommentOut

router = APIRouter(tags=["comments"])


def _comment_out(row: Comment) -> CommentOut:
    return CommentOut.model_validate(row)


@router.get("/api/episodes/{episode_id}/comments", response_model=list[CommentOut])
def list_comments(
    episode_id: str,
    user: ReadUser,
    db: DbDep,
    shot_id: str | None = None,
    board_node_id: str | None = None,
    include_resolved: bool = Query(default=True),
) -> list[CommentOut]:
    episode = get_episode(db, episode_id, user)
    query = db.query(Comment).filter(Comment.episode_id == episode.id)
    if shot_id:
        query = query.filter(Comment.shot_id == shot_id)
    if board_node_id:
        query = query.filter(Comment.board_node_id == board_node_id)
    if not include_resolved:
        query = query.filter(Comment.resolved.is_(False))
    rows = query.order_by(Comment.created_at.asc()).all()
    return [_comment_out(row) for row in rows]


@router.post(
    "/api/episodes/{episode_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    episode_id: str, body: CommentCreate, user: CommentUser, db: DbDep
) -> CommentOut:
    episode = get_episode(db, episode_id, user)
    author = (body.author or user.name).strip() or user.name
    shot_id = (body.shot_id or "").strip() or None
    if shot_id:
        shot = db.get(Shot, shot_id)
        if not shot or shot.episode_id != episode.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shot not found.")
    comment = Comment(
        episode_id=episode.id,
        shot_id=shot_id,
        board_node_id=(body.board_node_id or "").strip(),
        author=author,
        body=body.body.strip(),
    )
    if not comment.body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment body is empty.")
    db.add(comment)
    episode.updated_at = utcnow()
    touch(episode.project)
    db.flush()
    record(
        db,
        actor=user.name,
        action=COMMENT_CREATE,
        project_id=episode.project_id,
        episode_id=episode.id,
        entity_type="comment",
        entity_id=comment.id,
        detail={
            "shot_id": shot_id,
            "board_node_id": comment.board_node_id,
        },
    )
    from ..notify import notify_comment

    org_id = episode.project.organization_id if episode.project else user.org_id
    if org_id:
        notify_comment(db, comment, org_id=org_id)
    db.commit()
    db.refresh(comment)
    return _comment_out(comment)


@router.post("/api/comments/{comment_id}/resolve", response_model=CommentOut)
def resolve_comment(comment_id: str, user: CommentUser, db: DbDep) -> CommentOut:
    comment = db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")
    get_episode(db, comment.episode_id, user)
    if not comment.resolved:
        comment.resolved = True
        comment.resolved_by = user.name
        comment.resolved_at = utcnow()
        record(
            db,
            actor=user.name,
            action=COMMENT_RESOLVE,
            project_id=comment.episode.project_id if comment.episode else None,
            episode_id=comment.episode_id,
            entity_type="comment",
            entity_id=comment.id,
            detail={"shot_id": comment.shot_id},
        )
        db.commit()
        db.refresh(comment)
    return _comment_out(comment)
