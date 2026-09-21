import { useEffect, useState, type FormEvent } from "react";
import { api } from "./api.ts";
import type { Comment } from "./types.ts";

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

export function CommentsDrawer({
  episodeId,
  shotId,
  boardNodeId,
  canComment,
  onError,
  onNotice,
}: {
  episodeId: string;
  shotId?: string | null;
  boardNodeId?: string;
  canComment: boolean;
  onError: (err: unknown) => void;
  onNotice?: (msg: string) => void;
}) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!shotId && !boardNodeId) {
      setComments([]);
      return;
    }
    void api
      .comments(episodeId, { shot_id: shotId || undefined })
      .then((rows) =>
        setComments(
          boardNodeId
            ? rows.filter((row) => row.board_node_id === boardNodeId || row.shot_id === shotId)
            : rows.filter((row) => row.shot_id === shotId),
        ),
      )
      .catch(onError);
  }, [episodeId, shotId, boardNodeId, onError]);

  if (!shotId && !boardNodeId) return null;

  async function add(event: FormEvent) {
    event.preventDefault();
    if (!body.trim() || !canComment) return;
    setBusy(true);
    try {
      await api.addComment(episodeId, body.trim(), {
        shot_id: shotId || undefined,
        board_node_id: boardNodeId,
      });
      setBody("");
      const rows = await api.comments(episodeId, { shot_id: shotId || undefined });
      setComments(rows.filter((row) => (shotId ? row.shot_id === shotId : true)));
      onNotice?.("Comment added");
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  async function resolve(id: string) {
    try {
      await api.resolveComment(id);
      setComments((current) =>
        current.map((row) =>
          row.id === id ? { ...row, resolved: true, resolved_by: row.resolved_by || "me" } : row,
        ),
      );
    } catch (err) {
      onError(err);
    }
  }

  return (
    <div className="comments-drawer">
      <h4>Shot comments</h4>
      <ul className="thread">
        {comments.length === 0 ? <li className="empty">No comments on this shot yet.</li> : null}
        {comments.map((comment) => (
          <li key={comment.id} className={comment.resolved ? "is-resolved" : ""}>
            <strong>{comment.author}</strong>
            <span>
              {formatWhen(comment.created_at)}
              {comment.resolved ? ` · resolved by ${comment.resolved_by}` : ""}
            </span>
            <p>{comment.body}</p>
            {canComment && !comment.resolved ? (
              <button type="button" className="text-btn" onClick={() => void resolve(comment.id)}>
                Resolve
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {canComment ? (
        <form className="stack" onSubmit={add}>
          <textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder="Note on this shot. Pack zip remains the contract."
            rows={2}
          />
          <button type="submit" className="btn" disabled={busy}>
            Comment on shot
          </button>
        </form>
      ) : (
        <p className="hint">Viewers are read-only. A producer can promote you to comment.</p>
      )}
    </div>
  );
}
