import { useCallback, useEffect, useState } from "react";
import { api } from "./api.ts";
import type { StudioNotification } from "./types.ts";

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString();
}

export function NotificationBell({
  orgId,
  onError,
  onOpenHref,
}: {
  orgId?: string | null;
  onError: (err: unknown) => void;
  onOpenHref: (href: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<StudioNotification[]>([]);
  const [unread, setUnread] = useState(0);

  const load = useCallback(async () => {
    try {
      const next = await api.notifications();
      setItems(next.items);
      setUnread(next.unread_count);
    } catch (err) {
      onError(err);
    }
  }, [onError, orgId]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 12000);
    return () => window.clearInterval(id);
  }, [load]);

  async function mark(id: string) {
    try {
      await api.markNotificationRead(id);
      await load();
    } catch (err) {
      onError(err);
    }
  }

  async function markAll() {
    try {
      await api.markNotificationsRead();
      await load();
    } catch (err) {
      onError(err);
    }
  }

  return (
    <div className="notify-wrap">
      <button
        type="button"
        className="btn notify-bell"
        aria-label="Notifications"
        onClick={() => setOpen((value) => !value)}
      >
        Bell
        {unread > 0 ? <span className="notify-count">{unread}</span> : null}
      </button>
      {open ? (
        <div className="notify-panel" role="dialog" aria-label="Notifications">
          <div className="notify-head">
            <strong>Notifications</strong>
            <button type="button" className="text-btn" onClick={() => void markAll()} disabled={unread === 0}>
              Mark all read
            </button>
          </div>
          {items.length === 0 ? (
            <p className="empty">No notices yet. Stub jobs and mentions land here. Webhook unset unless configured.</p>
          ) : (
            <ul className="notify-list">
              {items.map((row) => (
                <li key={row.id} className={row.read_at ? "" : "is-unread"}>
                  <button
                    type="button"
                    className="text-btn"
                    onClick={() => {
                      void mark(row.id);
                      if (row.href) onOpenHref(row.href);
                      setOpen(false);
                    }}
                  >
                    {row.title}
                  </button>
                  <span>
                    {row.kind} · {formatWhen(row.created_at)}
                  </span>
                  {row.body ? <em>{row.body}</em> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
