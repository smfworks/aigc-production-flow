import { useState } from "react";
import {
  DEFAULT_LOOK_STYLE,
  CHARACTER_LOCK_FIELDS,
  PROP_FIELDS,
  type CapturePack,
  type PropFieldKey,
} from "../types";
import { propGenerateFlags } from "../lib/gate";
import {
  emptyCharacter,
  emptyProp,
  emptyStill,
  stillOk,
} from "../lib/pack";
import { Field, TextArea, TextField } from "./Field";

type Props = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
};

type Tab = "characters" | "props" | "look" | "stills";

export function CardsStep({ pack, onChange }: Props) {
  const [tab, setTab] = useState<Tab>("characters");
  return (
    <section>
      <div className="editor-head">
        <h2>Characters / Props / Look</h2>
        <p>
          Verbatim lock + forbidden + still path or explicit <code>none</code>{" "}
          and why. Lyric numbers belong on a prop card before any browser call.
        </p>
      </div>
      <div className="subnav">
        {(
          [
            ["characters", "Characters"],
            ["props", "Props"],
            ["look", "Look"],
            ["stills", "Stills"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "chip is-on" : "chip"}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "characters" ? (
        <Characters pack={pack} onChange={onChange} />
      ) : null}
      {tab === "props" ? <PropsEditor pack={pack} onChange={onChange} /> : null}
      {tab === "look" ? <LookEditor pack={pack} onChange={onChange} /> : null}
      {tab === "stills" ? <StillsEditor pack={pack} onChange={onChange} /> : null}
    </section>
  );
}

function Characters({ pack, onChange }: Props) {
  return (
    <>
      {pack.characters.map((card) => (
        <article
          key={card.id}
          className={
            stillOk(card.stillFile) && card.lockParagraph.trim()
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
            label="Still file (or none + why)"
            value={card.stillFile}
            placeholder="stills/smith.png or none — no likeness still"
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

function PropsEditor({ pack, onChange }: Props) {
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
              label="Still file (or none + why)"
              value={card.stillFile}
              placeholder="stills/francisca.png or none — lyric numbers only"
              onChange={(stillFile) =>
                onChange({
                  ...pack,
                  props: pack.props.map((item) =>
                    item.id === card.id ? { ...item, stillFile } : item,
                  ),
                })
              }
            />
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

function LookEditor({ pack, onChange }: Props) {
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

function StillsEditor({ pack, onChange }: Props) {
  return (
    <>
      <p className="field-hint">Wikipedia is not a still.</p>
      {pack.stills.map((row) => (
        <article key={row.id} className="row-card">
          <div className="grid-3">
            <TextField
              label="Entity"
              value={row.entity}
              onChange={(entity) =>
                onChange({
                  ...pack,
                  stills: pack.stills.map((item) =>
                    item.id === row.id ? { ...item, entity } : item,
                  ),
                })
              }
            />
            <TextField
              label="File"
              value={row.file}
              placeholder="stills/… or none"
              onChange={(file) =>
                onChange({
                  ...pack,
                  stills: pack.stills.map((item) =>
                    item.id === row.id ? { ...item, file } : item,
                  ),
                })
              }
            />
            <TextField
              label="Conditions hop"
              value={row.conditionsHop}
              placeholder="hop-1 of take A"
              onChange={(conditionsHop) =>
                onChange({
                  ...pack,
                  stills: pack.stills.map((item) =>
                    item.id === row.id ? { ...item, conditionsHop } : item,
                  ),
                })
              }
            />
          </div>
          <button
            type="button"
            className="icon-btn"
            onClick={() =>
              onChange({
                ...pack,
                stills:
                  pack.stills.length === 1
                    ? pack.stills
                    : pack.stills.filter((item) => item.id !== row.id),
              })
            }
          >
            Remove
          </button>
        </article>
      ))}
      <button
        type="button"
        className="btn btn-inline"
        onClick={() => onChange({ ...pack, stills: [...pack.stills, emptyStill()] })}
      >
        Add still row
      </button>
    </>
  );
}