import type { CapturePack } from "../types";
import { emptyTake, nextTakeLetter } from "../lib/pack";
import { TextField } from "./Field";

type Props = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
};

export function TakesStep({ pack, onChange }: Props) {
  return (
    <section>
      <div className="editor-head">
        <h2>Takes</h2>
        <p>
          One location and one grade per take. Unique prefix for{" "}
          <code>MiniMaxH3MotionContextSaveLatent</code>. Gold / dusk / amber are
          three takes, not one prompt.
        </p>
      </div>
      {pack.takes.map((row) => (
        <article key={row.id} className="row-card">
          <div className="row-top">
            <span className="row-kicker">Take {row.take || "—"}</span>
            <button
              type="button"
              className="icon-btn"
              onClick={() =>
                onChange({
                  ...pack,
                  takes:
                    pack.takes.length === 1
                      ? pack.takes
                      : pack.takes.filter((item) => item.id !== row.id),
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
              onChange={(take) =>
                onChange({
                  ...pack,
                  takes: pack.takes.map((item) =>
                    item.id === row.id ? { ...item, take } : item,
                  ),
                })
              }
            />
            <TextField
              label="Location"
              value={row.location}
              onChange={(location) =>
                onChange({
                  ...pack,
                  takes: pack.takes.map((item) =>
                    item.id === row.id ? { ...item, location } : item,
                  ),
                })
              }
            />
            <TextField
              label="Grade"
              value={row.grade}
              onChange={(grade) =>
                onChange({
                  ...pack,
                  takes: pack.takes.map((item) =>
                    item.id === row.id ? { ...item, grade } : item,
                  ),
                })
              }
            />
          </div>
          <div className="grid-3">
            <TextField
              label="Windows"
              value={row.windows}
              onChange={(windows) =>
                onChange({
                  ...pack,
                  takes: pack.takes.map((item) =>
                    item.id === row.id ? { ...item, windows } : item,
                  ),
                })
              }
            />
            <TextField
              label="Prefix"
              value={row.prefix}
              mono
              onChange={(prefix) =>
                onChange({
                  ...pack,
                  takes: pack.takes.map((item) =>
                    item.id === row.id ? { ...item, prefix } : item,
                  ),
                })
              }
            />
            <TextField
              label="Hop-1 seed"
              value={row.hop1Seed}
              mono
              onChange={(hop1Seed) =>
                onChange({
                  ...pack,
                  takes: pack.takes.map((item) =>
                    item.id === row.id ? { ...item, hop1Seed } : item,
                  ),
                })
              }
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
            takes: [...pack.takes, emptyTake(nextTakeLetter(pack.takes))],
          })
        }
      >
        Add take
      </button>
    </section>
  );
}
