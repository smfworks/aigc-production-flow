import { useEffect, useState } from "react";
import { api } from "./api.ts";
import type { ContinuitySummary } from "./types.ts";

export function ContinuityPanel({
  episodeId,
  refreshKey,
  onOpenHref,
  onError,
}: {
  episodeId: string;
  refreshKey?: string;
  onOpenHref: (href: string) => void;
  onError: (err: unknown) => void;
}) {
  const [summary, setSummary] = useState<ContinuitySummary | null>(null);

  useEffect(() => {
    void api.continuity(episodeId).then(setSummary).catch(onError);
  }, [episodeId, refreshKey, onError]);

  if (!summary) {
    return (
      <section className="panel">
        <h3>Continuity</h3>
        <p className="hint">Read/visualize only. Not a full NLE.</p>
      </section>
    );
  }

  const mismatches = summary.mismatches || [];
  const red = summary.red_gates || [];

  return (
    <section className="panel">
      <div className="panel-head">
        <h3>Continuity</h3>
        <p>{summary.honesty}</p>
      </div>
      <p className="hint">
        Entity schedule + lock-diff from the imported pack. Identity store is approved
        sheets/plates — not embeddings. Red gates are highlighted. Click a shot to open the board,
        or an identity link for the sheet/plate. This is not an NLE.
      </p>
      {red.length ? (
        <ol className="gates">
          {red.map((gate) => (
            <li key={gate.id} className="gate-bad">
              <span className="gate-n">{gate.n}</span>
              <span>
                <strong>{gate.label}</strong>
                <em>{gate.detail}</em>
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="hint">{summary.all_green ? "Continuity gates green on the latest pack." : "No pack snapshot yet."}</p>
      )}
      {mismatches.length ? (
        <ul className="mismatch-list">
          {mismatches.slice(0, 12).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="hint">No entity-schedule / lock-diff mismatches on this pack.</p>
      )}
      {summary.shots.length ? (
        <ul className="card-list">
          {summary.shots.map((shot) => (
            <li key={shot.shot_id}>
              <button
                type="button"
                className={shot.issues.length ? "card-btn gate-bad" : "card-btn"}
                onClick={() => onOpenHref(shot.href)}
              >
                <strong>
                  #{shot.sort_index + 1} · take {shot.take || "—"} · {shot.join || "no join"}
                </strong>
                <span>{shot.entities || "no entities"}</span>
                {shot.issues.length ? <em>{shot.issues[0]}</em> : null}
              </button>
              {shot.identity_href ? (
                <button type="button" className="text-btn" onClick={() => onOpenHref(shot.identity_href || "")}>
                  identity
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty">Import a pack to see shots on the continuity panel.</p>
      )}
    </section>
  );
}
