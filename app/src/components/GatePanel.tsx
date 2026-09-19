import type { GateResult } from "../lib/gate";

type Props = {
  gates: GateResult[];
  complete: boolean;
  busy: boolean;
  onExport: () => void;
  onExportDraft: () => void;
};

export function GatePanel({
  gates,
  complete,
  busy,
  onExport,
  onExportDraft,
}: Props) {
  const green = gates.filter((gate) => gate.ok).length;
  return (
    <aside className="gate" aria-label="Nine gates">
      <div>
        <p className="eyebrow">Do not queue Comfy</p>
        <h2>Gate</h2>
        <p className="gate-lede">
          Refuse generate until all nine exist. Export is the pack zip, not a
          render.
        </p>
      </div>
      <p className="gate-score">
        {green} / 9 green
      </p>
      {complete ? (
        <p className="ok-note">Nine lights honest. Export is the pack zip, not a render.</p>
      ) : (
        <p className="danger">
          Incomplete. Export pack zip stays off until every light is honest.
        </p>
      )}
      <ol className="gate-list">
        {gates.map((gate) => (
          <li
            key={gate.id}
            className={gate.ok ? "gate-item is-ok" : "gate-item is-bad"}
          >
            <span className="dot" aria-hidden="true" />
            <div>
              <strong>
                {gate.n}. {gate.label}
              </strong>
              <span>{gate.detail}</span>
            </div>
          </li>
        ))}
      </ol>
      <div className="actions">
        <button
          type="button"
          className="btn btn-go"
          disabled={!complete || busy}
          onClick={onExport}
        >
          {busy ? "Zipping…" : "Export pack zip"}
        </button>
        <button
          type="button"
          className="btn btn-warn"
          disabled={complete || busy}
          onClick={onExportDraft}
        >
          Export incomplete draft
        </button>
      </div>
    </aside>
  );
}
