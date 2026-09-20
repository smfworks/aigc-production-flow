import {
  CAMERA_VERBS,
  JOIN_TYPES,
  type CapturePack,
  type JoinType,
} from "../types";
import { defaultHold, formatCameraCell, isSingleOfficialCamera } from "../lib/camera";
import { emptyEditRow } from "../lib/pack";
import { ensurePlateStill, missingIdentityPlate } from "../lib/stills";
import type { GateResult } from "../lib/gate";
import { SelectField, TextField } from "./Field";
import { EmptyHint, StepIssues } from "./StepIssues";

type Props = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
  gates: GateResult[];
  onOpenStills: () => void;
};

const JOIN_OPTIONS = JOIN_TYPES.map((value) => ({ value, label: value }));
const CAMERA_OPTIONS = CAMERA_VERBS.map((value) => ({ value, label: value }));

export function EditListStep({ pack, onChange, gates, onOpenStills }: Props) {
  return (
    <section>
      <div className="editor-head">
        <h2>Edit list</h2>
        <p>
          Every row: join ∈ {"{continue, cut, fadeblack}"}. Exactly one camera
          verb (type + amplitude + speed). <code>continue</code> = plate on hop-1
          only; hop 2+ is Motion-Context latent (no new Qwen still).{" "}
          <code>cut</code> / <code>fadeblack</code> = new plate → I2VA hop-1.
          Chorus independent takes = independent plates. Pan and zoom and circle
          is three rows or it is refused.
        </p>
      </div>
      <StepIssues gates={gates} ids={["edit-list"]} />
      {pack.editList.length === 0 ? (
        <EmptyHint>No edit rows. Add continue / cut / fadeblack before generate.</EmptyHint>
      ) : null}
      {pack.editList.map((row, index) => {
        const camera = formatCameraCell(
          row.cameraVerb,
          row.cameraAmplitude,
          row.cameraSpeed,
        );
        const mush =
          Boolean(row.cameraVerb) && camera && !isSingleOfficialCamera(camera);
        const plateGap = missingIdentityPlate(pack, index);
        return (
          <article
            key={row.id}
            className={mush || plateGap ? "row-card is-bad" : "row-card"}
          >
            <div className="row-top">
              <span className="row-kicker">Row {index + 1}</span>
              <button
                type="button"
                className="icon-btn"
                onClick={() =>
                  onChange({
                    ...pack,
                    editList: pack.editList.filter((item) => item.id !== row.id),
                  })
                }
              >
                Remove
              </button>
            </div>
            <div className="grid-3">
              <TextField
                label="Song t"
                value={row.songT}
                mono
                placeholder="0:18"
                onChange={(songT) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id ? { ...item, songT } : item,
                    ),
                  })
                }
              />
              <TextField
                label="Dur s"
                value={row.durS}
                mono
                hint="Hop-1 10.125 · hop 2+ 9.209 · cut often 5"
                onChange={(durS) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id ? { ...item, durS } : item,
                    ),
                  })
                }
              />
              <SelectField
                label="Join"
                value={row.join}
                allowEmpty
                options={JOIN_OPTIONS}
                onChange={(join) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id
                        ? {
                            ...item,
                            join: join as JoinType | "",
                            hold: defaultHold(join),
                          }
                        : item,
                    ),
                  })
                }
              />
            </div>
            <div className="grid-3">
              <TextField
                label="Take"
                value={row.take}
                mono
                placeholder="A or —"
                onChange={(take) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id ? { ...item, take } : item,
                    ),
                  })
                }
              />
              <TextField
                label="Location / grade"
                value={row.locationGrade}
                onChange={(locationGrade) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id ? { ...item, locationGrade } : item,
                    ),
                  })
                }
              />
              <TextField
                label="Hold?"
                value={row.hold}
                hint="cut = no. Hold only before fadeblack."
                onChange={(hold) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id ? { ...item, hold } : item,
                    ),
                  })
                }
              />
            </div>
            <div className="grid-3">
              <SelectField
                label="Camera verb (one)"
                value={row.cameraVerb}
                allowEmpty
                options={CAMERA_OPTIONS}
                onChange={(cameraVerb) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id
                        ? {
                            ...item,
                            cameraVerb: cameraVerb as typeof row.cameraVerb,
                          }
                        : item,
                    ),
                  })
                }
              />
              <TextField
                label="Amplitude"
                value={row.cameraAmplitude}
                placeholder="small / 15°"
                onChange={(cameraAmplitude) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id ? { ...item, cameraAmplitude } : item,
                    ),
                  })
                }
              />
              <TextField
                label="Speed"
                value={row.cameraSpeed}
                placeholder="slow"
                onChange={(cameraSpeed) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id ? { ...item, cameraSpeed } : item,
                    ),
                  })
                }
              />
            </div>
            {mush ? (
              <p className="danger">
                Multi-verb mush: {camera}. Official H3 wants one verb.
              </p>
            ) : null}
            {plateGap ? (
              <p className="danger">
                {plateGap}{" "}
                <button
                  type="button"
                  className="btn btn-inline"
                  onClick={() => {
                    onChange(ensurePlateStill(pack, index));
                    onOpenStills();
                  }}
                >
                  Add plate still
                </button>
              </p>
            ) : null}
            <div className="grid-2">
              <TextField
                label="Action"
                value={row.action}
                onChange={(action) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id ? { ...item, action } : item,
                    ),
                  })
                }
              />
              <TextField
                label="Notes"
                value={row.notes}
                onChange={(notes) =>
                  onChange({
                    ...pack,
                    editList: pack.editList.map((item) =>
                      item.id === row.id ? { ...item, notes } : item,
                    ),
                  })
                }
              />
            </div>
          </article>
        );
      })}
      <button
        type="button"
        className="btn btn-inline"
        onClick={() =>
          onChange({ ...pack, editList: [...pack.editList, emptyEditRow()] })
        }
      >
        Add row
      </button>
    </section>
  );
}
