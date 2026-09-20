import {
  HOP1_MODES,
  type CapturePack,
  type Hop1Mode,
  type TakeCard,
} from "../types";
import { hop1ModeForPlate, hop1PlateStills, isRealStillFile } from "../lib/stills";
import { SelectField, TextField } from "./Field";

const HOP1_OPTIONS = [
  { value: "i2va", label: "I2VA — plate → MiniMaxH3ImageToVideo.first_frame" },
  { value: "t2v", label: "T2V — no plate (new face)" },
];

type Props = {
  pack: CapturePack;
  take: TakeCard;
  onChange: (pack: CapturePack) => void;
  showAttestation?: boolean;
};

export function Hop1Fields({ pack, take, onChange, showAttestation }: Props) {
  const derived = hop1ModeForPlate(take.hop1Plate);
  const plates = hop1PlateStills(pack, take.take);
  const hint =
    take.hop1Mode === "i2va"
      ? "Relative PNG path the clip Spark LoadImage can see."
      : take.hop1Mode === "t2v"
        ? "T2V requires none + why. A real plate file forces I2VA."
        : "I2VA if a plate exists, else T2V.";

  function patch(next: Partial<TakeCard>) {
    onChange({
      ...pack,
      takes: pack.takes.map((item) => {
        if (item.id !== take.id) return item;
        const merged = { ...item, ...next };
        if (next.hop1Plate !== undefined) {
          const mode = hop1ModeForPlate(merged.hop1Plate);
          if (mode) merged.hop1Mode = mode;
        }
        return merged;
      }),
    });
  }

  return (
    <div className="stack">
      <div className="grid-2">
        <SelectField
          label="Hop-1 mode"
          value={take.hop1Mode}
          allowEmpty
          emptyLabel="I2VA or T2V"
          options={HOP1_OPTIONS.filter((option) =>
            (HOP1_MODES as readonly string[]).includes(option.value),
          )}
          onChange={(hop1Mode) => patch({ hop1Mode: hop1Mode as Hop1Mode | "" })}
          hint={
            derived && take.hop1Mode && derived !== take.hop1Mode
              ? `Plate file implies ${derived.toUpperCase()}.`
              : "One hop-1 per take. Watch before hopping."
          }
        />
        <TextField
          label="Hop-1 plate (or none + why)"
          value={take.hop1Plate}
          mono
          title={take.hop1Plate}
          placeholder={
            take.hop1Mode === "i2va"
              ? "stills/a-hop1-plate.png"
              : "none — T2V until a plate exists"
          }
          hint={hint}
          onChange={(hop1Plate) => patch({ hop1Plate })}
        />
      </div>
      {plates.length > 0 ? (
        <p className="field-hint">
          From still cards:{" "}
          {plates.map((card) => card.file || card.entity).join(" · ")}
        </p>
      ) : null}
      {take.hop1Mode === "i2va" && !isRealStillFile(take.hop1Plate) ? (
        <p className="danger">I2VA needs a plate file, not none.</p>
      ) : null}
      {take.hop1Mode === "t2v" && isRealStillFile(take.hop1Plate) ? (
        <p className="danger">A plate exists — hop-1 must be I2VA.</p>
      ) : null}
      {showAttestation ? (
        <>
          <label className="check">
            <input
              type="checkbox"
              checked={take.hop1Planned}
              onChange={(event) => patch({ hop1Planned: event.target.checked })}
            />
            Hop-1 planned ({take.hop1Mode === "i2va" ? "I2VA" : take.hop1Mode === "t2v" ? "T2V" : "I2VA or T2V"})
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={take.watched}
              onChange={(event) => patch({ watched: event.target.checked })}
            />
            Watched (identity at cuts, join watchable) before hopping
          </label>
        </>
      ) : null}
    </div>
  );
}
