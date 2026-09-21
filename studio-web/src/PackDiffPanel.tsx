import type { PackDiff } from "./types.ts";

function Side({ ok, detail }: { ok: boolean | null; detail: string }) {
  if (ok === null) return <em className="muted">—</em>;
  return (
    <span className={ok ? "gate-ok" : "gate-bad"}>
      {ok ? "green" : "red"}
      {detail ? ` · ${detail}` : ""}
    </span>
  );
}

export function PackDiffPanel({
  diff,
  onApply,
  onCancel,
  applying,
  canApply,
}: {
  diff: PackDiff;
  onApply: () => void;
  onCancel: () => void;
  applying?: boolean;
  canApply: boolean;
}) {
  const gates = diff.gates || [];
  const changedGates = gates.filter((gate) => gate.changed);
  const schedule = diff.entity_schedule || { added: [], removed: [], changed: [] };
  const edit = diff.edit_list || { added: [], removed: [], changed: [] };
  const keywords = diff.identity_keywords || { added: [], removed: [], changed: [] };

  return (
    <section className="panel pack-diff">
      <div className="panel-head">
        <h3>Pack revision diff</h3>
        <p>{diff.honesty}</p>
      </div>
      <p className="hint">
        Left: {diff.left?.filename || "none (empty episode)"}. Right:{" "}
        {diff.right?.filename || "candidate"}. Confirm to apply overwrite. Never auto-generate.
      </p>
      <div className="diff-grid">
        <div>
          <h4>Gates {changedGates.length ? `(${changedGates.length} changed)` : ""}</h4>
          {gates.length === 0 ? (
            <p className="empty">No gates.</p>
          ) : (
            <ul className="diff-list">
              {gates.map((gate) => (
                <li key={gate.id} className={gate.changed ? "is-changed" : ""}>
                  <strong>
                    {gate.n}. {gate.label}
                  </strong>
                  <div className="diff-sides">
                    <span>
                      left: <Side ok={gate.left_ok} detail={gate.left_detail} />
                    </span>
                    <span>
                      right: <Side ok={gate.right_ok} detail={gate.right_detail} />
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4>Entity schedule</h4>
          <p className="hint">
            +{schedule.added?.length || 0} / −{schedule.removed?.length || 0} / ~{schedule.changed?.length || 0}
          </p>
          <h4>Edit list</h4>
          <p className="hint">
            +{edit.added?.length || 0} / −{edit.removed?.length || 0} / ~{edit.changed?.length || 0}
          </p>
          <h4>Identity keywords</h4>
          <p className="hint">
            +{keywords.added?.length || 0} / −{keywords.removed?.length || 0} / ~{keywords.changed?.length || 0}.
            Same synonym groups as lock-diff — not embeddings.
          </p>
        </div>
      </div>
      <div className="toolbar">
        <button type="button" className="btn btn-go" disabled={!canApply || applying} onClick={onApply}>
          {applying ? "Importing…" : "Confirm import"}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </section>
  );
}
