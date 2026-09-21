import {
  DEFAULT_LOOK_STYLE,
  DEFAULT_STILL_CANVAS,
  CHARACTER_LOCK_FIELDS,
  ENTITY_KINDS,
  PROP_FIELDS,
  STILL_ROLES,
  STILL_SOURCES,
  type CapturePack,
  type EntityKind,
  type EntityScheduleRow,
  type PropFieldKey,
  type StillCard,
  type StillRole,
  type StillSource,
} from "../types";
import {
  emptyCharacter,
  emptyEntitySchedule,
  emptyProp,
  emptyStill,
  stillOk,
} from "../lib/pack";
import { propGenerateFlags, type CardsTab, type GateResult } from "../lib/gate";
import { missingIdentityHoldPlate, scheduleAppliesToRow } from "../lib/entitySchedule";
import { lockDiffProblems } from "../lib/lockDiff";
import {
  canvasLooksStretched,
  canvasMatchesHop1,
  ensureSheetStill,
  isBlankStill,
  sheetStillForEntity,
  stillCardProblems,
  stillSourceAgrees,
} from "../lib/stills";
import { Field, SelectField, TextArea, TextField } from "./Field";
import { EmptyHint, StepIssues } from "./StepIssues";

type Props = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
  gates: GateResult[];
  tab: CardsTab;
  onTab: (tab: CardsTab) => void;
};

const SOURCE_OPTIONS = STILL_SOURCES.map((value) => ({ value, label: value }));
const ROLE_OPTIONS = STILL_ROLES.map((value) => ({ value, label: value }));

export function CardsStep({ pack, onChange, gates, tab, onTab }: Props) {
  return (
    <section>
      <div className="editor-head">
        <h2>Characters / Props / Look / Stills / Schedule</h2>
        <p>
          Verbatim lock + forbidden + <strong>sheet</strong> path or explicit{" "}
          <code>none</code> and why. Plates (hop-1 / cut / fadeblack first frames)
          live on still cards — do not collapse them into the character/prop
          sheet. Entity schedule says who persists on which windows. Lyric
          numbers belong on a prop card before any browser call.
        </p>
      </div>
      <StepIssues
        gates={gates}
        ids={
          tab === "stills"
            ? ["smoke", "lock-diff"]
            : tab === "schedule"
              ? ["entity-schedule"]
              : ["characters", "props", "look", "lock-diff"]
        }
      />
      <div className="subnav">
        {(
          [
            ["characters", "Characters"],
            ["props", "Props"],
            ["look", "Look"],
            ["stills", "Stills"],
            ["schedule", "Schedule"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "chip is-on" : "chip"}
            aria-current={tab === id ? "true" : undefined}
            onClick={() => onTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "characters" ? (
        <Characters pack={pack} onChange={onChange} onOpenStills={() => onTab("stills")} />
      ) : null}
      {tab === "props" ? (
        <PropsEditor pack={pack} onChange={onChange} onOpenStills={() => onTab("stills")} />
      ) : null}
      {tab === "look" ? <LookEditor pack={pack} onChange={onChange} /> : null}
      {tab === "stills" ? <StillsEditor pack={pack} onChange={onChange} /> : null}
      {tab === "schedule" ? <ScheduleEditor pack={pack} onChange={onChange} /> : null}
    </section>
  );
}

type EditorProps = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
  onOpenStills?: () => void;
};

function Characters({ pack, onChange, onOpenStills }: EditorProps) {
  if (pack.characters.length === 0) {
    return (
      <>
        <EmptyHint>No character cards. Add one with lock, forbidden, and a sheet or none + why.</EmptyHint>
        <button
          type="button"
          className="btn btn-inline"
          onClick={() =>
            onChange({ ...pack, characters: [...pack.characters, emptyCharacter()] })
          }
        >
          Add character
        </button>
      </>
    );
  }
  return (
    <>
      {pack.characters.map((card) => (
        <article
          key={card.id}
            className={
            stillOk(card.stillFile) &&
            stillSourceAgrees(card.stillFile, card.stillSource) &&
            card.lockParagraph.trim()
              ? "row-card"
              : "row-card is-bad"
          }
        >
          <div className="row-top">
            <span className="row-kicker">
              character-{card.name || "unnamed"}
            </span>
            <button
              type="button"
              className="icon-btn"
              onClick={() =>
                onChange({
                  ...pack,
                  characters: pack.characters.filter((item) => item.id !== card.id),
                })
              }
            >
              Remove
            </button>
          </div>
          <div className="grid-2">
            <TextField
              label="Name"
              value={card.name}
              onChange={(name) =>
                onChange({
                  ...pack,
                  characters: pack.characters.map((item) =>
                    item.id === card.id ? { ...item, name } : item,
                  ),
                })
              }
            />
            <TextField
              label="Speaker ID"
              value={card.speakerId}
              hint="(S1) / none"
              onChange={(speakerId) =>
                onChange({
                  ...pack,
                  characters: pack.characters.map((item) =>
                    item.id === card.id ? { ...item, speakerId } : item,
                  ),
                })
              }
            />
          </div>
          <TextField
            label="Sheet file (or none + why)"
            value={card.stillFile}
            placeholder="stills/smith-sheet.png or none — no likeness still"
            hint="Still role is sheet (bible). Plates live on still cards."
            onChange={(stillFile) =>
              onChange({
                ...pack,
                characters: pack.characters.map((item) =>
                  item.id === card.id ? { ...item, stillFile } : item,
                ),
              })
            }
          />
          <div className="grid-2">
            <SelectField
              label="Sheet source"
              value={card.stillSource}
              allowEmpty
              emptyLabel="photo / qwen-t2i / qwen-edit / none"
              options={SOURCE_OPTIONS}
              onChange={(stillSource) =>
                onChange({
                  ...pack,
                  characters: pack.characters.map((item) =>
                    item.id === card.id
                      ? { ...item, stillSource: stillSource as StillSource | "" }
                      : item,
                  ),
                })
              }
            />
            <TextField
              label="Sheet canvas"
              value={card.stillCanvas}
              placeholder={DEFAULT_STILL_CANVAS}
              hint="Must match H3 hop-1. Do not stretch 1024²."
              onChange={(stillCanvas) =>
                onChange({
                  ...pack,
                  characters: pack.characters.map((item) =>
                    item.id === card.id ? { ...item, stillCanvas } : item,
                  ),
                })
              }
            />
          </div>
          <SheetLockButton pack={pack} entity={card.name} onCopy={(lockFromStill) =>
            onChange({
              ...pack,
              characters: pack.characters.map((item) =>
                item.id === card.id ? { ...item, lockParagraph: lockFromStill } : item,
              ),
            })
          } />
          {!sheetStillForEntity(pack, card.name) && card.name.trim() ? (
            <button
              type="button"
              className="btn btn-inline"
              onClick={() => {
                onChange(
                  ensureSheetStill(
                    pack,
                    card.name,
                    card.stillFile,
                    card.stillSource,
                    card.stillCanvas,
                  ),
                );
                onOpenStills?.();
              }}
            >
              Add matching sheet still
            </button>
          ) : null}
          <div className="grid-2">
            {CHARACTER_LOCK_FIELDS.map((field) => (
              <TextField
                key={field.key}
                label={field.label}
                value={card[field.key]}
                onChange={(value) =>
                  onChange({
                    ...pack,
                    characters: pack.characters.map((item) =>
                      item.id === card.id
                        ? { ...item, [field.key]: value }
                        : item,
                    ),
                  })
                }
              />
            ))}
          </div>
          <TextArea
            label="Lock paragraph"
            value={card.lockParagraph}
            onChange={(lockParagraph) =>
              onChange({
                ...pack,
                characters: pack.characters.map((item) =>
                  item.id === card.id ? { ...item, lockParagraph } : item,
                ),
              })
            }
          />
          {lockDiffProblems(pack)
            .filter((item) => item.entityName.toLowerCase() === card.name.trim().toLowerCase())
            .slice(0, 2)
            .map((item) => (
              <p key={item.detail} className="danger">
                {item.detail}
              </p>
            ))}
          <TextArea
            label="Forbidden"
            value={card.forbidden}
            onChange={(forbidden) =>
              onChange({
                ...pack,
                characters: pack.characters.map((item) =>
                  item.id === card.id ? { ...item, forbidden } : item,
                ),
              })
            }
          />
          <TextArea
            label="Motion notes (optional)"
            value={card.motionNotes}
            onChange={(motionNotes) =>
              onChange({
                ...pack,
                characters: pack.characters.map((item) =>
                  item.id === card.id ? { ...item, motionNotes } : item,
                ),
              })
            }
          />
        </article>
      ))}
      <button
        type="button"
        className="btn btn-inline"
        onClick={() =>
          onChange({ ...pack, characters: [...pack.characters, emptyCharacter()] })
        }
      >
        Add character
      </button>
    </>
  );
}

function PropsEditor({ pack, onChange, onOpenStills }: EditorProps) {
  if (pack.props.length === 0) {
    return (
      <>
        <EmptyHint>No prop cards. Pin numbers and units before any browser call.</EmptyHint>
        <button
          type="button"
          className="btn btn-inline"
          onClick={() => onChange({ ...pack, props: [...pack.props, emptyProp()] })}
        >
          Add prop
        </button>
      </>
    );
  }
  return (
    <>
      {pack.props.map((card) => {
        const flags = propGenerateFlags(card);
        return (
          <article
            key={card.id}
            className={
              flags.overallHaftUnresolved || flags.noStillAndNoReason
                ? "row-card is-bad"
                : "row-card"
            }
          >
            <div className="row-top">
              <span className="row-kicker">prop-{card.name || "unnamed"}</span>
              <button
                type="button"
                className="icon-btn"
                onClick={() =>
                  onChange({
                    ...pack,
                    props: pack.props.filter((item) => item.id !== card.id),
                  })
                }
              >
                Remove
              </button>
            </div>
            <TextField
              label="Name"
              value={card.name}
              onChange={(name) =>
                onChange({
                  ...pack,
                  props: pack.props.map((item) =>
                    item.id === card.id ? { ...item, name } : item,
                  ),
                })
              }
            />
            <TextField
              label="Sheet file (or none + why)"
              value={card.stillFile}
              placeholder="stills/francisca-sheet.png or none — lyric numbers only"
              hint="Still role is sheet (bible). Plates live on still cards."
              onChange={(stillFile) =>
                onChange({
                  ...pack,
                  props: pack.props.map((item) =>
                    item.id === card.id ? { ...item, stillFile } : item,
                  ),
                })
              }
            />
            <div className="grid-2">
              <SelectField
                label="Sheet source"
                value={card.stillSource}
                allowEmpty
                emptyLabel="photo / qwen-t2i / qwen-edit / none"
                options={SOURCE_OPTIONS}
                onChange={(stillSource) =>
                  onChange({
                    ...pack,
                    props: pack.props.map((item) =>
                      item.id === card.id
                        ? { ...item, stillSource: stillSource as StillSource | "" }
                        : item,
                    ),
                  })
                }
              />
              <TextField
                label="Sheet canvas"
                value={card.stillCanvas}
                placeholder={DEFAULT_STILL_CANVAS}
                hint="Must match H3 hop-1. Do not stretch 1024²."
                onChange={(stillCanvas) =>
                  onChange({
                    ...pack,
                    props: pack.props.map((item) =>
                      item.id === card.id ? { ...item, stillCanvas } : item,
                    ),
                  })
                }
              />
            </div>
            <SheetLockButton pack={pack} entity={card.name} onCopy={(lockFromStill) =>
              onChange({
                ...pack,
                props: pack.props.map((item) =>
                  item.id === card.id ? { ...item, lockParagraph: lockFromStill } : item,
                ),
              })
            } />
            {!sheetStillForEntity(pack, card.name) && card.name.trim() ? (
              <button
                type="button"
                className="btn btn-inline"
                onClick={() => {
                  onChange(
                    ensureSheetStill(
                      pack,
                      card.name,
                      card.stillFile,
                      card.stillSource,
                      card.stillCanvas,
                    ),
                  );
                  onOpenStills?.();
                }}
              >
                Add matching sheet still
              </button>
            ) : null}
            <p className={flags.overallHaftUnresolved ? "danger" : "ok-note"}>
              {flags.overallHaftUnresolved
                ? "Overall vs haft length unresolved"
                : "Overall vs haft length pinned"}
            </p>
            <p className={flags.noStillAndNoReason ? "danger" : "ok-note"}>
              {flags.noStillAndNoReason
                ? "No still and no reason"
                : "Still path or none + why"}
            </p>
            {PROP_FIELDS.map((field) => (
              <div key={field.key} className="grid-3">
                <Field label={field.label}>
                  <input
                    value={card.fields[field.key].value}
                    onChange={(event) =>
                      patchMeasurement(pack, onChange, card.id, field.key, {
                        value: event.target.value,
                      })
                    }
                  />
                </Field>
                <Field label="Unit">
                  <input
                    className="mono"
                    value={card.fields[field.key].unit}
                    onChange={(event) =>
                      patchMeasurement(pack, onChange, card.id, field.key, {
                        unit: event.target.value,
                      })
                    }
                  />
                </Field>
                <Field label="Source (lyric / photo / measured)">
                  <input
                    value={card.fields[field.key].source}
                    onChange={(event) =>
                      patchMeasurement(pack, onChange, card.id, field.key, {
                        source: event.target.value,
                      })
                    }
                  />
                </Field>
              </div>
            ))}
            <TextArea
              label="Lock paragraph"
              value={card.lockParagraph}
              onChange={(lockParagraph) =>
                onChange({
                  ...pack,
                  props: pack.props.map((item) =>
                    item.id === card.id ? { ...item, lockParagraph } : item,
                  ),
                })
              }
            />
            <TextArea
              label="Forbidden (do not invent)"
              value={card.forbidden}
              onChange={(forbidden) =>
                onChange({
                  ...pack,
                  props: pack.props.map((item) =>
                    item.id === card.id ? { ...item, forbidden } : item,
                  ),
                })
              }
            />
          </article>
        );
      })}
      <button
        type="button"
        className="btn btn-inline"
        onClick={() => onChange({ ...pack, props: [...pack.props, emptyProp()] })}
      >
        Add prop
      </button>
    </>
  );
}

function patchMeasurement(
  pack: CapturePack,
  onChange: (pack: CapturePack) => void,
  id: string,
  key: PropFieldKey,
  patch: Partial<{ value: string; unit: string; source: string }>,
): void {
  onChange({
    ...pack,
    props: pack.props.map((item) =>
      item.id === id
        ? {
            ...item,
            fields: {
              ...item.fields,
              [key]: { ...item.fields[key], ...patch },
            },
          }
        : item,
    ),
  });
}

function LookEditor({ pack, onChange }: EditorProps) {
  return (
    <div className="stack">
      <TextArea
        label="One style line (paste into every [Shot 1])"
        value={pack.look.styleLine}
        placeholder={DEFAULT_LOOK_STYLE}
        onChange={(styleLine) =>
          onChange({ ...pack, look: { ...pack.look, styleLine } })
        }
      />
      <TextArea
        label="Palette / grade"
        value={pack.look.paletteGrade}
        onChange={(paletteGrade) =>
          onChange({ ...pack, look: { ...pack.look, paletteGrade } })
        }
      />
      <TextArea
        label="Era"
        value={pack.look.era}
        onChange={(era) => onChange({ ...pack, look: { ...pack.look, era } })}
      />
      <TextArea
        label="Lens / grain (optional)"
        value={pack.look.lensGrain}
        onChange={(lensGrain) =>
          onChange({ ...pack, look: { ...pack.look, lensGrain } })
        }
      />
      <TextArea
        label="Extras forbidden"
        value={pack.look.extrasForbidden}
        onChange={(extrasForbidden) =>
          onChange({ ...pack, look: { ...pack.look, extrasForbidden } })
        }
      />
    </div>
  );
}

function StillsEditor({ pack, onChange }: EditorProps) {
  const cards = pack.stills;
  if (cards.length === 0) {
    return (
      <>
        <p className="field-hint">
          A <strong>sheet</strong> is the bible. A <strong>plate</strong> is hop-1
          first_frame. Native 1344×768. Do not stretch 1024².
        </p>
        <EmptyHint>No still cards. Add a sheet, then plates for hop-1 / cut / fadeblack.</EmptyHint>
        <button
          type="button"
          className="btn btn-inline"
          onClick={() => onChange({ ...pack, stills: [emptyStill()] })}
        >
          Add still card
        </button>
      </>
    );
  }
  function patch(id: string, next: Partial<StillCard>) {
    onChange({
      ...pack,
      stills: pack.stills.map((item) => (item.id === id ? { ...item, ...next } : item)),
    });
  }

  return (
    <>
      <p className="field-hint">
        A <strong>sheet</strong> is the character/prop bible. A <strong>plate</strong>{" "}
        is the hop-1 / cut / fadeblack first frame for{" "}
        <code>MiniMaxH3ImageToVideo.first_frame</code>. Native canvas 1344×768.
        Do not stretch 1024². Wikipedia is not a still. Export writes one{" "}
        <code>still-*.md</code> per card, shaped like{" "}
        <code>templates/still-card.md</code>.
      </p>
      {pack.stills.map((row) => {
        const problems = isBlankStill(row) ? [] : stillCardProblems(row, pack.look.styleLine);
        return (
          <article key={row.id} className={problems.length ? "row-card is-bad" : "row-card"}>
            <div className="row-top">
              <span className="row-kicker">
                still-{row.entity || "unnamed"}
                {row.role ? ` · ${row.role}` : ""}
              </span>
              <button
                type="button"
                className="icon-btn"
                onClick={() =>
                  onChange({
                    ...pack,
                    stills: pack.stills.filter((item) => item.id !== row.id),
                  })
                }
              >
                Remove
              </button>
            </div>
            <div className="grid-2">
              <TextField
                label="Entity"
                value={row.entity}
                placeholder="smith / francisca / take A hop-1"
                onChange={(entity) => patch(row.id, { entity })}
              />
              <SelectField
                label="Role"
                value={row.role}
                allowEmpty
                emptyLabel="sheet | hop-1 plate | cut plate | last-frame"
                options={ROLE_OPTIONS}
                hint="Sheet = bible. Plate = first frame of a window."
                onChange={(role) =>
                  patch(row.id, {
                    role: role as StillRole | "",
                    conditions:
                      role === "sheet" && !row.conditions.trim() ? "none" : row.conditions,
                  })
                }
              />
            </div>
            <div className="grid-3">
              <SelectField
                label="Source"
                value={row.source}
                allowEmpty
                emptyLabel="photo | qwen-t2i | qwen-edit | none"
                options={SOURCE_OPTIONS}
                onChange={(source) => patch(row.id, { source: source as StillSource | "" })}
              />
              <TextField
                label="Canvas"
                value={row.canvas}
                placeholder={DEFAULT_STILL_CANVAS}
                hint={
                  canvasLooksStretched(row.canvas) || !canvasMatchesHop1(row.canvas)
                    ? `Must be ${DEFAULT_STILL_CANVAS}`
                    : "H3 native 16:9"
                }
                onChange={(canvas) => patch(row.id, { canvas })}
              />
              <TextField
                label="File (or none + why)"
                value={row.file}
                placeholder="stills/…png or none — why"
                onChange={(file) => patch(row.id, { file })}
              />
            </div>
            <TextField
              label="Conditions (hop-1 of take _ / cut row _ / none)"
              value={row.conditions}
              placeholder={
                row.role === "cut plate"
                  ? "cut row 3"
                  : row.role === "hop-1 plate"
                    ? "hop-1 of take A"
                    : "none"
              }
              hint="continue = plate on hop-1 only. Hop 2+ is the latent."
              onChange={(conditions) => patch(row.id, { conditions })}
            />
            <TextArea
              label="Look lock (must match look.md, verbatim)"
              value={row.lookLock}
              placeholder={pack.look.styleLine || DEFAULT_LOOK_STYLE}
              onChange={(lookLock) => patch(row.id, { lookLock })}
            />
            <button
              type="button"
              className="btn btn-inline"
              onClick={() => patch(row.id, { lookLock: pack.look.styleLine })}
            >
              Copy look.md
            </button>
            <TextArea
              label="Lock copied from this still (do not invent after)"
              value={row.lockFromStill}
              onChange={(lockFromStill) => patch(row.id, { lockFromStill })}
            />
            <TextArea
              label="Forbidden (what this still must not grow)"
              value={row.forbidden}
              onChange={(forbidden) => patch(row.id, { forbidden })}
            />
            <TextArea
              label="Notes"
              value={row.notes}
              onChange={(notes) => patch(row.id, { notes })}
            />
            {problems.length ? (
              <p className="danger">{problems.slice(0, 2).join("; ")}</p>
            ) : null}
            {row.role && row.role !== "sheet" ? (
              <p className="field-hint">
                cut / fadeblack identity holds need this plate's <strong>entity</strong> to match
                the scheduled name (not just "take A hop-1") and conditions to bind the window.
              </p>
            ) : null}
          </article>
        );
      })}
      <button
        type="button"
        className="btn btn-inline"
        onClick={() => onChange({ ...pack, stills: [...pack.stills, emptyStill()] })}
      >
        Add still card
      </button>
    </>
  );
}

function SheetLockButton({
  pack,
  entity,
  onCopy,
}: {
  pack: CapturePack;
  entity: string;
  onCopy: (lock: string) => void;
}) {
  const sheet = sheetStillForEntity(pack, entity);
  if (!sheet?.lockFromStill.trim()) {
    return (
      <p className="field-hint">
        Copy the lock paragraph from the matching sheet still. Do not generate the
        still from a lock you wrote after.
      </p>
    );
  }
  return (
    <button type="button" className="btn btn-inline" onClick={() => onCopy(sheet.lockFromStill)}>
      Copy lock from sheet still
    </button>
  );
}

function ScheduleEditor({ pack, onChange }: EditorProps) {
  const KIND_OPTIONS = ENTITY_KINDS.map((value) => ({ value, label: value }));
  function patch(id: string, next: Partial<EntityScheduleRow>) {
    onChange({
      ...pack,
      entitySchedule: pack.entitySchedule.map((item) =>
        item.id === id ? { ...item, ...next } : item,
      ),
    });
  }
  return (
    <>
      <p className="field-hint">
        Who/what must persist on which takes/windows. Identity hold at{" "}
        <code>cut</code> / <code>fadeblack</code> requires a plate still whose
        entity is this name. <code>continue</code> hop 2+ is the latent.
      </p>
      {pack.entitySchedule.map((row) => {
        const matching = pack.editList
          .map((_, index) => index)
          .filter((index) => scheduleAppliesToRow(pack, row, index));
        const gaps = matching
          .map((index) => missingIdentityHoldPlate(pack, row, index))
          .filter(Boolean);
        return (
          <article key={row.id} className={gaps.length ? "row-card is-bad" : "row-card"}>
            <div className="row-top">
              <span className="row-kicker">
                {row.entityName || "unnamed"} · take {row.take || "?"}
              </span>
              <button
                type="button"
                className="icon-btn"
                onClick={() =>
                  onChange({
                    ...pack,
                    entitySchedule: pack.entitySchedule.filter((item) => item.id !== row.id),
                  })
                }
              >
                Remove
              </button>
            </div>
            <div className="grid-3">
              <SelectField
                label="Kind"
                value={row.entityKind}
                allowEmpty
                options={KIND_OPTIONS}
                onChange={(entityKind) =>
                  patch(row.id, { entityKind: entityKind as EntityKind | "" })
                }
              />
              <TextField
                label="Entity"
                value={row.entityName}
                placeholder="smith / francisca"
                onChange={(entityName) => patch(row.id, { entityName })}
              />
              <TextField
                label="Take (* = all)"
                value={row.take}
                placeholder="A or *"
                onChange={(take) => patch(row.id, { take })}
              />
            </div>
            <div className="grid-2">
              <TextField
                label="Windows"
                value={row.windows}
                placeholder="all · hop-1 · 0:18 · #3 · 1-2"
                hint="all, hop-1, song clocks, or 1-based row numbers."
                onChange={(windows) => patch(row.id, { windows })}
              />
              <label className="check">
                <input
                  type="checkbox"
                  checked={row.identityHold}
                  onChange={(event) => patch(row.id, { identityHold: event.target.checked })}
                />
                Identity must hold at cut / fadeblack (needs a bound plate)
              </label>
            </div>
            {matching.length ? (
              <p className="field-hint">
                Matches edit row{matching.length === 1 ? "" : "s"}{" "}
                {matching.map((index) => `#${index + 1}`).join(", ")}.
              </p>
            ) : (
              <p className="danger">No edit-list window matches this take/windows pin.</p>
            )}
            {gaps.map((gap) => (
              <p key={gap} className="danger">
                {gap}
              </p>
            ))}
          </article>
        );
      })}
      <button
        type="button"
        className="btn btn-inline"
        onClick={() =>
          onChange({
            ...pack,
            entitySchedule: [...pack.entitySchedule, emptyEntitySchedule()],
          })
        }
      >
        Add schedule row
      </button>
    </>
  );
}
