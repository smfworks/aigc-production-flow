import { useEffect, useMemo, useRef, useState } from "react";
import { CardsStep } from "../../app/src/components/CardsStep.tsx";
import { EditListStep } from "../../app/src/components/EditListStep.tsx";
import { MapStep } from "../../app/src/components/MapStep.tsx";
import { PackStep } from "../../app/src/components/PackStep.tsx";
import { SmokeStep } from "../../app/src/components/SmokeStep.tsx";
import { StepNav } from "../../app/src/components/StepNav.tsx";
import { TakesStep } from "../../app/src/components/TakesStep.tsx";
import { evaluateGates, type CardsTab, type GateId, GATE_DESTINATION } from "../../app/src/lib/gate.ts";
import { emptyPack } from "../../app/src/lib/pack.ts";
import { migratePack } from "../../app/src/lib/storage.ts";
import type { CapturePack, StepId } from "../../app/src/types.ts";
import { api, downloadAgentExport } from "./api.ts";
import { ConfirmDialog } from "./ConfirmDialog.tsx";
import "./pack-stage.css";

type Props = {
  episodeId: string;
  canEdit: boolean;
  onError: (err: unknown) => void;
  onNotice: (message: string) => void;
  onSaved?: () => void;
};

function readMeta(raw: unknown): { note: string; modelRan: boolean } {
  if (!raw || typeof raw !== "object") return { note: "", modelRan: false };
  const meta = (raw as { studioMeta?: { note?: string; model_ran?: boolean } }).studioMeta;
  return {
    note: typeof meta?.note === "string" ? meta.note : "",
    modelRan: Boolean(meta?.model_ran),
  };
}

export function PackStage({ episodeId, canEdit, onError, onNotice, onSaved }: Props) {
  const [pack, setPack] = useState<CapturePack | null>(null);
  const [step, setStep] = useState<StepId>("pack");
  const [cardsTab, setCardsTab] = useState<CardsTab>("characters");
  const [boardRow, setBoardRow] = useState("");
  const [saveState, setSaveState] = useState("Loading the pack…");
  const [modelNote, setModelNote] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [brainOpen, setBrainOpen] = useState(false);
  const [brain, setBrain] = useState("");
  const [confirmBrain, setConfirmBrain] = useState(false);
  const metaRef = useRef<Record<string, unknown>>({});
  const savedJson = useRef("");
  const skipSave = useRef(true);

  useEffect(() => {
    let cancelled = false;
    skipSave.current = true;
    setSaveState("Loading the pack…");
    void api
      .revisions(episodeId)
      .then(async (rows) => {
        if (cancelled) return;
        if (!rows.length) {
          const blank = emptyPack();
          setPack(blank);
          metaRef.current = {};
          savedJson.current = JSON.stringify(blank);
          setModelNote("No revision yet. Start a blank pack below, or paste a brain dump. Zip import is optional.");
          setSaveState("Not saved yet.");
          return;
        }
        const full = await api.revision(episodeId, rows[0].id);
        if (cancelled) return;
        const migrated = migratePack(full.pack);
        if (!migrated) throw new Error("Stored pack.json is not a capture pack.");
        const honesty = readMeta(full.pack);
        metaRef.current =
          full.pack && typeof full.pack === "object" && "studioMeta" in full.pack
            ? { ...(full.pack.studioMeta as Record<string, unknown>) }
            : {};
        setModelNote(honesty.note);
        setPack(migrated);
        savedJson.current = JSON.stringify(migrated);
        setSaveState(
          full.all_gates_green
            ? `Stored ${full.filename}. Gates green. generate-ok is still a separate stamp.`
            : `Stored ${full.filename}. Draft — gates red until filled. Not generate-ready.`,
        );
      })
      .catch((err) => {
        if (!cancelled) onError(err);
      });
    return () => {
      cancelled = true;
    };
  }, [episodeId, onError]);

  useEffect(() => {
    if (!pack || !canEdit) return;
    if (skipSave.current) {
      skipSave.current = false;
      return;
    }
    const serialized = JSON.stringify(pack);
    if (serialized === savedJson.current) return;
    const handle = window.setTimeout(() => {
      setSaveState("Saving revision…");
      const body = {
        ...pack,
        studioMeta: {
          ...metaRef.current,
          source: "studio-editor",
          generate_ready: false,
          note: "Saved from the in-studio pack editor. Not a generate.",
        },
      };
      void api
        .savePack(episodeId, body)
        .then((saved) => {
          savedJson.current = serialized;
          setSaveState(
            saved.gates_green
              ? `Saved ${saved.filename}. Gates green on this revision. Not generate-ok.`
              : `Saved ${saved.filename}. Draft revision. Gates stay red until filled.`,
          );
          onSaved?.();
        })
        .catch((err) => {
          setSaveState("Save failed.");
          onError(err);
        });
    }, 900);
    return () => window.clearTimeout(handle);
  }, [canEdit, episodeId, onError, onSaved, pack]);

  const gates = useMemo(() => (pack ? evaluateGates(pack) : []), [pack]);

  function jump(id: GateId) {
    const dest = GATE_DESTINATION[id];
    setStep(dest.step);
    setCardsTab(dest.cardsTab ?? "characters");
  }

  async function applyBlank() {
    setConfirmReset(false);
    try {
      const saved = await api.resetBlank(episodeId);
      skipSave.current = true;
      const blank = emptyPack();
      if (pack?.title) blank.title = pack.title;
      setPack(blank);
      metaRef.current = {
        status: "draft",
        source: "blank",
        model_ran: false,
        generate_ready: false,
      };
      savedJson.current = JSON.stringify(blank);
      setModelNote("Blank pack. Look is blank. No model ran.");
      setSaveState(`Saved ${saved.filename}. Earlier revisions kept. Not generate-ready.`);
      onNotice("Working pack reset to blank. Earlier revisions kept.");
      onSaved?.();
    } catch (err) {
      onError(err);
    }
  }

  async function applyBrain() {
    setConfirmBrain(false);
    try {
      const created = await api.brainDump(episodeId, brain.trim());
      setBrain("");
      setBrainOpen(false);
      skipSave.current = true;
      const full = await api.revision(episodeId, created.revision_id);
      const migrated = migratePack(full.pack);
      if (!migrated) throw new Error("Draft pack could not be read.");
      setPack(migrated);
      savedJson.current = JSON.stringify(migrated);
      setModelNote(created.model_note);
      setSaveState(
        created.model_ran
          ? "Draft from the configured endpoint. Gates are not a generate."
          : "Draft from the dump text. No model ran.",
      );
      onNotice(created.model_note);
      onSaved?.();
    } catch (err) {
      onError(err);
    }
  }

  return (
    <section className="panel pack-stage" data-testid="pack-stage">
      <div className="panel-head">
        <h3>Pack stages</h3>
        <p>
          Script → Assets → Storyboard → Preview, in this episode. Autosave writes a pack revision.
          Look starts blank on a new pack. This does not generate video.
        </p>
      </div>
      <p className="hint" data-testid="pack-save-state">
        {saveState}
        {modelNote ? ` ${modelNote}` : ""}
      </p>
      <div className="toolbar">
        <button
          type="button"
          className="btn btn-go"
          data-testid="export-agent"
          onClick={() =>
            void downloadAgentExport(episodeId)
              .then(() =>
                onNotice(
                  "Exported agent zip. Still jobs are listed before hop-1 clips. Studio did not call Comfy.",
                ),
              )
              .catch(onError)
          }
        >
          Export for agent
        </button>
        <button type="button" className="btn" disabled={!canEdit} onClick={() => setBrainOpen((open) => !open)}>
          {brainOpen ? "Hide brain dump" : "Brain dump"}
        </button>
        <button type="button" className="btn" disabled={!canEdit || !pack} onClick={() => setConfirmReset(true)}>
          Reset to blank pack
        </button>
      </div>
      {brainOpen ? (
        <label className="field">
          <span className="editor-label">Brain dump</span>
          <textarea
            value={brain}
            onChange={(event) => setBrain(event.target.value)}
            rows={4}
            placeholder="Freeform brief. Becomes a draft skeleton. Gates stay red."
            aria-label="Episode brain dump"
          />
          <button
            type="button"
            className="btn btn-go"
            disabled={!brain.trim() || !canEdit}
            onClick={() => setConfirmBrain(true)}
          >
            Make draft pack
          </button>
        </label>
      ) : null}
      {pack ? (
        <div className="pack-stage-workspace">
          <div className="editor">
            <StepNav step={step} onStep={setStep} />
            <fieldset disabled={!canEdit} className="pack-fields">
              {step === "pack" ? <PackStep pack={pack} onChange={setPack} gates={gates} /> : null}
              {step === "map" ? <MapStep pack={pack} onChange={setPack} gates={gates} /> : null}
              {step === "takes" ? <TakesStep pack={pack} onChange={setPack} gates={gates} /> : null}
              {step === "edit" ? (
                <EditListStep
                  pack={pack}
                  onChange={setPack}
                  gates={gates}
                  selectedId={boardRow}
                  onSelect={setBoardRow}
                  onOpenStills={() => {
                    setCardsTab("stills");
                    setStep("cards");
                  }}
                />
              ) : null}
              {step === "cards" ? (
                <CardsStep pack={pack} onChange={setPack} gates={gates} tab={cardsTab} onTab={setCardsTab} />
              ) : null}
              {step === "smoke" ? <SmokeStep pack={pack} onChange={setPack} gates={gates} /> : null}
            </fieldset>
          </div>
          <aside className="gate" aria-label="Live gates">
            <p className="eyebrow">Do not queue Comfy</p>
            <p className="gate-lede">Live checklist while you edit. The stored revision is what review reads after autosave.</p>
            <ol className="gate-list">
              {gates.map((gate) => (
                <li key={gate.id}>
                  <button
                    type="button"
                    className={gate.ok ? "gate-item is-ok" : "gate-item is-bad"}
                    onClick={() => jump(gate.id)}
                  >
                    <span className="dot" aria-hidden="true" />
                    <span>
                      {gate.n}. {gate.label}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </aside>
        </div>
      ) : (
        <p className="empty">Loading stages…</p>
      )}
      <ConfirmDialog
        open={confirmReset}
        title="Reset to a blank pack?"
        message="The working pack becomes blank. Look stays blank and gates stay red. Earlier revisions are kept. This does not generate."
        confirmLabel="Reset pack"
        onCancel={() => setConfirmReset(false)}
        onConfirm={() => void applyBlank()}
      />
      <ConfirmDialog
        open={confirmBrain}
        title="Replace the working pack with this dump?"
        message="A new draft revision is added from the brief. Gates stay red until you fill them. Earlier revisions are kept. If no model is configured, Studio says so."
        confirmLabel="Create draft"
        onCancel={() => setConfirmBrain(false)}
        onConfirm={() => void applyBrain()}
      />
    </section>
  );
}
