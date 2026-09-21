import { useState } from "react";
import {
  CAMERA_VERBS,
  JOIN_TYPES,
  type CapturePack,
  type JoinType,
} from "../types";
import { defaultHold, formatCameraCell, isSingleOfficialCamera } from "../lib/camera";
import { missingIdentityHoldPlate, scheduleAppliesToRow } from "../lib/entitySchedule";
import { emptyEditRow } from "../lib/pack";
import { ensureEntityPlateStill, ensurePlateStill, missingIdentityPlate } from "../lib/stills";
import type { GateResult } from "../lib/gate";
import { BoardCanvas } from "./BoardCanvas";
import { SelectField, TextField } from "./Field";
import { EmptyHint, StepIssues } from "./StepIssues";

type Props = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
  gates: GateResult[];
  onOpenStills: () => void;
  selectedId?: string;
  onSelect?: (id: string) => void;
};

const JOIN_OPTIONS = JOIN_TYPES.map((value) => ({ value, label: value }));
const CAMERA_OPTIONS = CAMERA_VERBS.map((value) => ({ value, label: value }));

export function EditListStep({
  pack,
  onChange,
  gates,
  onOpenStills,
  selectedId,
  onSelect,
}: Props) {
  const [view, setView] = useState<"list" | "board">("list");
  const rowIndex = Number(selectedId);
  const resolvedSelected =
    pack.editList.find((row) => row.id === selectedId)?.id ??
    (Number.isInteger(rowIndex) && rowIndex >= 1 ? pack.editList[rowIndex - 1]?.id : undefined);
  return (
    <section>
      <div className="editor-head">
        <h2>Edit list</h2>
        <p>
          Every row: join ∈ {"{continue, cut, fadeblack}"}. Exactly one camera
          verb (type + amplitude + speed). <code>continue</code> = plate on hop-1
          only; hop 2+ is Motion-Context latent (no new Qwen still).{" "}
          <code>cut</code> / <code>fadeblack</code> = new plate → I2VA hop-1.
          List is precision. Canvas shows join chains.
        </p>
      </div>
      <StepIssues gates={gates} ids={["edit-list", "entity-schedule"]} />
      <div className="subnav">
        <button
          type="button"
          className={view === "list" ? "chip is-on" : "chip"}
          onClick={() => setView("list")}
        >
          List
        </button>
        <button
          type="button"
          className={view === "board" ? "chip is-on" : "chip"}
          onClick={() => setView("board")}
        >
          Canvas
        </button>
      </div>
      {view === "board" ? (
        <BoardCanvas pack={pack} selectedId={resolvedSelected} onSelect={onSelect} />
      ) : null}
      {pack.editList.length === 0 ? (
        <EmptyHint>No edit rows. Add continue / cut / fadeblack before generate.</EmptyHint>
      ) : null}
      {view === "list"
        ? pack.editList.map((row, index) => {
            const camera = formatCameraCell(
              row.cameraVerb,
              row.cameraAmplitude,
              row.cameraSpeed,
            );
            const mush =
              Boolean(row.cameraVerb) && camera && !isSingleOfficialCamera(camera);
            const plateGap = missingIdentityPlate(pack, index);
            const holdGaps = pack.entitySchedule
              .filter((item) => item.identityHold && scheduleAppliesToRow(pack, item, index))
              .map((item) => ({
                name: item.entityName,
                gap: missingIdentityHoldPlate(pack, item, index),
              }))
              .filter((item) => item.gap);
            const selected = resolvedSelected === row.id;
            return (
              <article
                key={row.id}
                id={`edit-row-${index + 1}`}
                className={mush || plateGap || holdGaps.length ? "row-card is-bad" : selected ? "row-card is-selected" : "row-card"}
                onClick={() => onSelect?.(row.id)}
              >
                <div className="row-top">
                  <span className="row-kicker">
                    Row {index + 1}
                    {row.join ? ` · ${row.join}` : ""}
                  </span>
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
                {holdGaps.map((item) => (
                  <p key={item.name} className="danger">
                    {item.gap}{" "}
                    <button
                      type="button"
                      className="btn btn-inline"
                      onClick={() => {
                        onChange(ensureEntityPlateStill(pack, item.name, index));
                        onOpenStills();
                      }}
                    >
                      Bind {item.name} plate
                    </button>
                  </p>
                ))}
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
                    label="Entities in this window"
                    value={row.entities}
                    placeholder="smith, francisca"
                    hint="Must include everyone on the entity schedule for this take/window."
                    onChange={(entities) =>
                      onChange({
                        ...pack,
                        editList: pack.editList.map((item) =>
                          item.id === row.id ? { ...item, entities } : item,
                        ),
                      })
                    }
                  />
                </div>
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
              </article>
            );
          })
        : null}
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
