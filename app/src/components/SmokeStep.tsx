import type { CapturePack } from "../types";
import { emptyContinuity } from "../lib/pack";
import { TextArea, TextField } from "./Field";

type Props = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
};

export function SmokeStep({ pack, onChange }: Props) {
  return (
    <section>
      <div className="editor-head">
        <h2>Smoke + continuity</h2>
        <p>
          One T2V per take with SaveLatent and a unique prefix. Join the planned
          fades. Watch. Only then hop. The continuity log is a stub until
          generate — intent is the edit list; this file is what landed.
        </p>
      </div>
      <TextArea
        label="Smoke plan"
        value={pack.smokeNotes}
        onChange={(smokeNotes) => onChange({ ...pack, smokeNotes })}
      />
      {pack.takes.map((row) => (
        <article key={row.id} className="row-card">
          <div className="row-top">
            <span className="row-kicker">
              Take {row.take} · {row.prefix || "no prefix"}
            </span>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={row.t2vPlanned}
              onChange={(event) =>
                onChange({
                  ...pack,
                  takes: pack.takes.map((item) =>
                    item.id === row.id
                      ? { ...item, t2vPlanned: event.target.checked }
                      : item,
                  ),
                })
              }
            />
            Hop-1 T2V planned
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={row.watched}
              onChange={(event) =>
                onChange({
                  ...pack,
                  takes: pack.takes.map((item) =>
                    item.id === row.id
                      ? { ...item, watched: event.target.checked }
                      : item,
                  ),
                })
              }
            />
            Watched (identity at cuts, join watchable)
          </label>
        </article>
      ))}

      <div className="editor-head">
        <h2>Continuity log stub</h2>
        <p>Fill during generate from history: seed, peak °C, ffprobe, NG reason.</p>
      </div>
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
                  continuityRows:
                    pack.continuityRows.length === 1
                      ? pack.continuityRows
                      : pack.continuityRows.filter((item) => item.id !== row.id),
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
