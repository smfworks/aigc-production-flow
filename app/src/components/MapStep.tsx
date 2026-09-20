import { ENERGY_VALUES, type CapturePack } from "../types";
import { emptyMapRow } from "../lib/pack";
import type { GateResult } from "../lib/gate";
import { StepIssues, EmptyHint } from "./StepIssues";

type Props = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
  gates: GateResult[];
};

export function MapStep({ pack, onChange, gates }: Props) {
  return (
    <section>
      <div className="editor-head">
        <h2>Map</h2>
        <p>
          Clock → beat → energy. This is not a shot list. Chorus clocks do not
          choose <code>cut</code> vs <code>continue</code> — that is the edit
          list.
        </p>
      </div>
      <StepIssues gates={gates} ids={["map"]} />
      {pack.map.length === 0 ? (
        <EmptyHint>No beats. Map clocks to verse/chorus/bridge — not shots.</EmptyHint>
      ) : null}
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Clock</th>
              <th>Beat</th>
              <th>Energy (title/verse/chorus/bridge/outro)</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pack.map.map((row) => (
              <tr key={row.id}>
                <td>
                  <input
                    className="mono"
                    value={row.clock}
                    placeholder="0:18"
                    aria-label="Clock"
                    onChange={(event) =>
                      onChange({
                        ...pack,
                        map: pack.map.map((item) =>
                          item.id === row.id
                            ? { ...item, clock: event.target.value }
                            : item,
                        ),
                      })
                    }
                  />
                </td>
                <td>
                  <input
                    value={row.beat}
                    placeholder="verse"
                    aria-label="Beat"
                    onChange={(event) =>
                      onChange({
                        ...pack,
                        map: pack.map.map((item) =>
                          item.id === row.id
                            ? { ...item, beat: event.target.value }
                            : item,
                        ),
                      })
                    }
                  />
                </td>
                <td>
                  <select
                    value={row.energy}
                    aria-label="Energy"
                    onChange={(event) =>
                      onChange({
                        ...pack,
                        map: pack.map.map((item) =>
                          item.id === row.id
                            ? { ...item, energy: event.target.value }
                            : item,
                        ),
                      })
                    }
                  >
                    <option value="">—</option>
                    {ENERGY_VALUES.map((energy) => (
                      <option key={energy} value={energy}>
                        {energy}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() =>
                      onChange({
                        ...pack,
                        map: pack.map.filter((item) => item.id !== row.id),
                      })
                    }
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        className="btn btn-inline"
        onClick={() => onChange({ ...pack, map: [...pack.map, emptyMapRow()] })}
      >
        Add beat
      </button>
    </section>
  );
}
