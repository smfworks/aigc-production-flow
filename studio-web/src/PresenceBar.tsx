import { useEffect, useState } from "react";
import { api } from "./api.ts";
import type { PresenceUser } from "./types.ts";

export function PresenceBar({
  episodeId,
  shotId,
  onError,
}: {
  episodeId: string;
  shotId?: string | null;
  onError: (err: unknown) => void;
}) {
  const [people, setPeople] = useState<PresenceUser[]>([]);

  useEffect(() => {
    let cancelled = false;
    async function beat() {
      try {
        const next = await api.heartbeat(episodeId, shotId);
        if (!cancelled) setPeople(next);
      } catch (err) {
        if (!cancelled) onError(err);
      }
    }
    void beat();
    const id = window.setInterval(() => void beat(), 15000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [episodeId, shotId, onError]);

  if (people.length === 0) {
    return <p className="hint presence-bar">No one else on this episode (TTL ~60s).</p>;
  }

  return (
    <div className="presence-bar" aria-label="Who is on this episode">
      {people.map((row) => (
        <span key={row.user_name} className={`presence-chip is-${row.role || "viewer"}`}>
          {row.user_name}
          {row.role ? ` · ${row.role}` : ""}
          {row.shot_id && row.shot_id === shotId ? " · this shot" : ""}
        </span>
      ))}
    </div>
  );
}
