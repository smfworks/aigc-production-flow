import type { CapturePack } from "../types";
import { emptyContinuity } from "../lib/pack";
import { applyStillsToTakes } from "../lib/stills";
import type { GateResult } from "../lib/gate";
import { Hop1Fields } from "./Hop1Fields";
import { TextArea, TextField } from "./Field";
import { EmptyHint, StepIssues } from "./StepIssues";

type Props = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
  gates: GateResult[];
};

export function SmokeStep({ pack, onChange, gates }: Props) {
  return (
    <section>
      <div className="editor-head">
        <h2>Smoke + continuity</h2>
        <p>
          One hop-1 per take — <strong>I2VA if a plate exists, else T2V</strong> —
          with SaveLatent and a unique prefix. Watch identity at cuts. Only then
          hop. Gate 9 refuses a missing plate (or missing <code>none</code> +
          why). Continuity log and polaroid path are what landed, not intent.
        </p>
      </div>
      <StepIssues gates={gates} ids={["smoke"]} />
      <TextArea
        label="Smoke plan"
        value={pack.smokeNotes}
        onChange={(smokeNotes) => onChange({ ...pack, smokeNotes })}
      />
      <button
        type="button"
        className="btn btn-inline"
        onClick={() => onChange(applyStillsToTakes(pack))}
      >
        Fill hop-1 from still cards
      </button>
      {pack.takes.map((row) => (
        <article key={row.id} className="row-card">
          <div className="row-top">
            <span className="row-kicker">
              Take {row.take} · {row.prefix || "no prefix"} ·{" "}
              {row.hop1Mode === "i2va" ? "I2VA" : row.hop1Mode === "t2v" ? "T2V" : "no hop-1 mode"}
            </span>
          </div>
          <Hop1Fields pack={pack} take={row} onChange={onChange} showAttestation />
        </article>
      ))}

      <div className="editor-head">
        <h2>Continuity log stub</h2>
        <p>Fill during generate from history: seed, peak °C, ffprobe, NG reason.</p>
      </div>
      {pack.continuityRows.length === 0 ? (
        <EmptyHint>No continuity rows yet. Fill during generate — this is what landed, not intent.</EmptyHint>
      ) : null}
      {pack.continuityRows.map((row) => (
        <article key={row.id} className="row-card">
          <div className="row-top">
            <span className="row-kicker">Hop row</span>
            <button
              type="button"
              className="icon-btn"
              onClick={() =>
                onChange({
                  ...pack,
                  continuityRows: pack.continuityRows.filter((item) => item.id !== row.id),
                })
              }
            >
              Remove
            </button>
          </div>
          <div className="grid-3">
            <TextField
              label="Take"
              value={row.take}
              mono
              onChange={(take) => patchRow(pack, onChange, row.id, { take })}
            />
            <TextField
              label="Hop"
              value={row.hop}
              mono
              onChange={(hop) => patchRow(pack, onChange, row.id, { hop })}
            />
            <TextField
              label="Seed"
              value={row.seed}
              mono
              onChange={(seed) => patchRow(pack, onChange, row.id, { seed })}
            />
          </div>
          <div className="grid-3">
            <TextField
              label="Wall s"
              value={row.wallS}
              onChange={(wallS) => patchRow(pack, onChange, row.id, { wallS })}
            />
            <TextField
              label="Peak °C"
              value={row.peakC}
              onChange={(peakC) => patchRow(pack, onChange, row.id, { peakC })}
            />
            <TextField
              label="ffprobe (dur / frames)"
              value={row.ffprobe}
              onChange={(ffprobe) => patchRow(pack, onChange, row.id, { ffprobe })}
            />
          </div>
          <div className="grid-3">
            <TextField
              label="Still vs lock"
              value={row.stillVsLock}
              onChange={(stillVsLock) =>
                patchRow(pack, onChange, row.id, { stillVsLock })
              }
            />
            <TextField
              label="Circle / NG"
              value={row.circleNg}
              onChange={(circleNg) =>
                patchRow(pack, onChange, row.id, { circleNg })
              }
            />
            <TextField
              label="Why"
              value={row.why}
              onChange={(why) => patchRow(pack, onChange, row.id, { why })}
            />
          </div>
        </article>
      ))}
      <button
        type="button"
        className="btn btn-inline"
        onClick={() =>
          onChange({
            ...pack,
            continuityRows: [...pack.continuityRows, emptyContinuity()],
          })
        }
      >
        Add log row
      </button>
      <TextField
        label="Polaroid / still grab after hop-1 (path)"
        value={pack.polaroidPath}
        onChange={(polaroidPath) => onChange({ ...pack, polaroidPath })}
      />
    </section>
  );
}

function patchRow(
  pack: CapturePack,
  onChange: (pack: CapturePack) => void,
  id: string,
  patch: Partial<CapturePack["continuityRows"][number]>,
): void {
  onChange({
    ...pack,
    continuityRows: pack.continuityRows.map((item) =>
      item.id === id ? { ...item, ...patch } : item,
    ),
  });
}
