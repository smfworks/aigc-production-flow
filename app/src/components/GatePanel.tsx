import { GATE_DESTINATION, type GateId, type GateResult } from "../lib/gate";
import { useEffect, useRef } from "react";

type Props = {
  gates: GateResult[];
  complete: boolean;
  busy: boolean;
  helpOpen: boolean;
  onExport: () => void;
  onExportDraft: () => void;
  onCopyChecklist: () => void;
  onPrint: () => void;
  onJump: (id: GateId) => void;
  onOpenStudio: () => void;
  studioBusy?: boolean;
};

export function GatePanel({
  gates,
  complete,
  busy,
  helpOpen,
  onExport,
  onExportDraft,
  onCopyChecklist,
  onPrint,
  onJump,
  onOpenStudio,
  studioBusy,
}: Props) {
  const green = gates.filter((gate) => gate.ok).length;
  const total = gates.length || 1;
  const helpRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if (helpRef.current) helpRef.current.open = helpOpen;
  }, [helpOpen]);
  return (
    <aside className="gate" aria-label="Pack gates">
      <div>
        <p className="eyebrow">Do not queue Comfy</p>
        <h2>Gate</h2>
        <p className="gate-lede">
          Refuse generate until every gate is green, including entity schedule
          and lock-diff. Hop-1 is I2VA if a plate exists, else T2V. Export is
          the pack zip, not a render.
        </p>
      </div>
      <p className="gate-score">
        {green} / {total} green
      </p>
      <div
        className={complete ? "gate-meter is-ready" : "gate-meter"}
        role="meter"
        aria-label={`${green} of ${total} gates green`}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={green}
      >
        <span style={{ width: `${Math.round((green / total) * 100)}%` }} />
      </div>
      {complete ? (
        <p className="ok-note">
          Ready to queue Comfy? Yes. {total} lights honest. Export is the pack zip, not a render.
        </p>
      ) : (
        <p className="danger">
          Ready to queue Comfy? No. {green}/{total}. Export pack zip stays off until
          every light is honest.
        </p>
      )}
      <ol className="gate-list">
        {gates.map((gate) => (
          <li key={gate.id}>
            <button
              type="button"
              className={gate.ok ? "gate-item is-ok" : "gate-item is-bad"}
              onClick={() => onJump(gate.id)}
              aria-label={`Go to ${GATE_DESTINATION[gate.id].step}: ${gate.label}. ${gate.detail}`}
            >
              <span className="dot" aria-hidden="true" />
              <div>
                <strong>
                  {gate.n}. {gate.label}
                </strong>
                <span>{gate.detail}</span>
              </div>
            </button>
          </li>
        ))}
      </ol>
      <details ref={helpRef} className="still-help">
        <summary>Still factory → clip factory</summary>
        <p>
          Sheets and plates are generated on the image Spark (Qwen-Image-2.1) at
          native <strong>1344×768</strong>. Do not stretch 1024². Wikipedia is
          not a still. A sheet is the character/prop bible. A plate is hop-1 /{" "}
          <code>cut</code> / <code>fadeblack</code>{" "}
          <code>MiniMaxH3ImageToVideo.first_frame</code>. Hop 2+ is
          Motion-Context latent — no new Qwen still.{" "}
          <a href="https://github.com/smfworks/h3-longform-capture/blob/main/docs/IMAGE-STILLS.md">
            docs/IMAGE-STILLS.md
          </a>
        </p>
      </details>
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
        <button type="button" className="btn" onClick={onCopyChecklist}>
          Copy pack summary
        </button>
        <button type="button" className="btn" onClick={onPrint}>
          Print pack summary
        </button>
        <button type="button" className="btn" onClick={onOpenStudio} disabled={studioBusy}>
          {studioBusy ? "Handing off…" : "Open in Studio"}
        </button>
      </div>
      <p className="kbd-hint">
        1–6 steps · E export · D draft · C summary · ? stills help
      </p>
    </aside>
  );
}
