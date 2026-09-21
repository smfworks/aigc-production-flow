import { CardsStep } from "./components/CardsStep";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { EditListStep } from "./components/EditListStep";
import { GatePanel } from "./components/GatePanel";
import { Header } from "./components/Header";
import { MapStep } from "./components/MapStep";
import { PackStep } from "./components/PackStep";
import { SmokeStep } from "./components/SmokeStep";
import { StepNav } from "./components/StepNav";
import { TakesStep } from "./components/TakesStep";
import { Toast } from "./components/Toast";
import {
  GATE_DESTINATION,
  allGatesGreen,
  evaluateGates,
  packSummaryMarkdown,
  type CardsTab,
  type GateId,
} from "./lib/gate";
import { downloadBlob, packToZipBlob, zipFilename } from "./lib/exportZip";
import { packFromZipBlob } from "./lib/importZip";
import { WIPE_PROMPTS, packAfterConfirmedWipe, type WipeKind } from "./lib/confirmWipe";
import { sigilsSample } from "./lib/sample";
import { consumeLoadNote, initialPack, saveStoredPack } from "./lib/storage";
import { openInStudio } from "./lib/studio";
import { STEPS, type CapturePack, type StepId } from "./types";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

function typingInField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

const CARD_TABS: CardsTab[] = ["characters", "props", "look", "stills", "schedule"];

function stepFromSearch(): StepId {
  if (typeof window === "undefined") return "pack";
  const step = new URLSearchParams(window.location.search).get("step");
  return STEPS.some((item) => item.id === step) ? (step as StepId) : "pack";
}

function tabFromSearch(): CardsTab {
  if (typeof window === "undefined") return "characters";
  const tab = new URLSearchParams(window.location.search).get("tab");
  return CARD_TABS.includes(tab as CardsTab) ? (tab as CardsTab) : "characters";
}

function rowFromSearch(): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("row") ?? "";
}

export default function App() {
  const [pack, setPack] = useState<CapturePack>(() => initialPack(sigilsSample()));
  const [step, setStep] = useState<StepId>(stepFromSearch);
  const [cardsTab, setCardsTab] = useState<CardsTab>(tabFromSearch);
  const [boardRow, setBoardRow] = useState(rowFromSearch);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [pendingWipe, setPendingWipe] = useState<
    { kind: WipeKind; file?: File } | null
  >(null);
  const importRef = useRef<HTMLInputElement>(null);

  const showToast = useCallback((message: string) => {
    setToast(message);
  }, []);

  useEffect(() => {
    const note = consumeLoadNote();
    if (note) showToast(note);
  }, [showToast]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 2800);
    return () => window.clearTimeout(id);
  }, [toast]);

  useEffect(() => {
    const id = window.setTimeout(() => saveStoredPack(pack), 280);
    return () => window.clearTimeout(id);
  }, [pack]);

  const gates = useMemo(() => evaluateGates(pack), [pack]);
  const complete = useMemo(() => allGatesGreen(pack), [pack]);

  const jumpGate = useCallback((id: GateId) => {
    const dest = GATE_DESTINATION[id];
    setStep(dest.step);
    setCardsTab(dest.cardsTab ?? "characters");
  }, []);

  const loadSample = useCallback(() => {
    setPendingWipe({ kind: "load-sample" });
  }, []);

  const newPack = useCallback(() => {
    setPendingWipe({ kind: "new-pack" });
  }, []);

  const cancelWipe = useCallback(() => {
    setPendingWipe(null);
  }, []);

  const exportZip = useCallback(
    async (asDraft: boolean) => {
      if (asDraft === false && !complete) {
        showToast("Nine+ consistency gates not green. Use D for an incomplete draft.");
        return;
      }
      setBusy(true);
      try {
        const blob = await packToZipBlob(pack);
        downloadBlob(blob, zipFilename(pack, !asDraft && complete));
        showToast(
          asDraft
            ? "Draft zip downloaded. Open in Studio stages the zip when the API is reachable."
            : "Pack zip downloaded. Open in Studio stages the zip when the API is reachable.",
        );
      } catch (error) {
        showToast(error instanceof Error ? error.message : "Export failed.");
      } finally {
        setBusy(false);
      }
    },
    [complete, pack, showToast],
  );

  const openStudio = useCallback(async () => {
    setBusy(true);
    try {
      const blob = await packToZipBlob(pack);
      const result = await openInStudio(blob, zipFilename(pack, complete));
      showToast(result.message);
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Studio handoff failed.");
    } finally {
      setBusy(false);
    }
  }, [complete, pack, showToast]);

  const copyChecklist = useCallback(async () => {
    const text = packSummaryMarkdown(pack);
    try {
      await navigator.clipboard.writeText(text);
      showToast("Pack summary copied.");
    } catch {
      showToast("Could not copy summary.");
    }
  }, [pack, showToast]);

  const importZip = useCallback(
    async (file: File) => {
      try {
        const next = await packFromZipBlob(file);
        setPack(next);
        setStep("pack");
        setCardsTab("characters");
        showToast("Imported pack zip.");
      } catch (error) {
        showToast(error instanceof Error ? error.message : "Import failed.");
      }
    },
    [showToast],
  );

  const confirmWipe = useCallback(() => {
    if (!pendingWipe) return;
    if (pendingWipe.kind === "import-zip") {
      const file = pendingWipe.file;
      setPendingWipe(null);
      if (file) void importZip(file);
      return;
    }
    const next = packAfterConfirmedWipe(pendingWipe.kind);
    setPack(next);
    setStep("pack");
    setCardsTab("characters");
    setPendingWipe(null);
    showToast(
      pendingWipe.kind === "new-pack"
        ? "New pack."
        : "Loaded Sigils lessons sample — not generate-ready until the axe is pinned.",
    );
  }, [importZip, pendingWipe, showToast]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (pendingWipe) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (typingInField(event.target)) return;
      if (event.key === "1" || event.key === "2" || event.key === "3" || event.key === "4" || event.key === "5" || event.key === "6") {
        const dest = STEPS[Number(event.key) - 1];
        if (dest) {
          event.preventDefault();
          setStep(dest.id);
        }
        return;
      }
      const key = event.key.toLowerCase();
      if (key === "e") {
        event.preventDefault();
        void exportZip(false);
        return;
      }
      if (key === "d") {
        event.preventDefault();
        void exportZip(true);
        return;
      }
      if (key === "c") {
        event.preventDefault();
        void copyChecklist();
        return;
      }
      if (key === "?") {
        event.preventDefault();
        setHelpOpen((open) => !open);
        return;
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [complete, copyChecklist, exportZip, pendingWipe]);

  return (
    <div className="page">
      <div className="ambient" aria-hidden="true" />
      <Header
        onLoadSample={loadSample}
        onNewPack={newPack}
        onImport={() => importRef.current?.click()}
        onOpenStudio={() => void openStudio()}
        studioBusy={busy}
      />
      <input
        ref={importRef}
        className="sr-only"
        type="file"
        accept=".zip,application/zip"
        aria-label="Import pack zip"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (!file) return;
          setPendingWipe({ kind: "import-zip", file });
        }}
      />
      <div className="workspace">
        <main className="editor">
          <StepNav step={step} onStep={setStep} />
          {step === "pack" ? (
            <PackStep pack={pack} onChange={setPack} gates={gates} />
          ) : null}
          {step === "map" ? (
            <MapStep pack={pack} onChange={setPack} gates={gates} />
          ) : null}
          {step === "takes" ? (
            <TakesStep pack={pack} onChange={setPack} gates={gates} />
          ) : null}
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
            <CardsStep
              pack={pack}
              onChange={setPack}
              gates={gates}
              tab={cardsTab}
              onTab={setCardsTab}
            />
          ) : null}
          {step === "smoke" ? (
            <SmokeStep pack={pack} onChange={setPack} gates={gates} />
          ) : null}
        </main>
        <GatePanel
          gates={gates}
          complete={complete}
          busy={busy}
          helpOpen={helpOpen}
          onExport={() => void exportZip(false)}
          onExportDraft={() => void exportZip(true)}
          onCopyChecklist={() => void copyChecklist()}
          onPrint={() => window.print()}
          onJump={jumpGate}
          onOpenStudio={() => void openStudio()}
          studioBusy={busy}
        />
      </div>
      <footer className="site-foot">
        <p>
          AIGC Production Flow · SMF Works ·{" "}
          <a href="https://github.com/smfworks/aigc-production-flow">GitHub</a>
          {" · "}
          <a href="https://github.com/smfworks/aigc-production-flow/blob/main/docs/PRODUCTION-FLOW.md">
            Four stages
          </a>
          {" · "}
          <a href="https://github.com/smfworks/aigc-production-flow/blob/main/docs/IMAGE-STILLS.md">
            Still factory → clip factory
          </a>
          {" · "}
          <a href="https://www.smfclearinghouse.com/blog/2026-09-17-h3-longform-capture-bible">
            Lock the bible before the GPU
          </a>
        </p>
        <p className="fineprint">
          MIT templates remain the source of truth under <code>templates/</code>{" "}
          and <code>docs/</code> (especially <code>docs/PRODUCTION-FLOW.md</code>,{" "}
          <code>docs/IMAGE-STILLS.md</code>, and{" "}
          <code>templates/still-card.md</code>). This app is a client-side form
          over that gate. No engine weights, no generated media, no uploads.
          Intelligence is abundant. Judgment is the product.
        </p>
      </footer>
      <pre className="print-summary">{packSummaryMarkdown(pack)}</pre>
      <Toast message={toast} />
      {pendingWipe ? (
        <ConfirmDialog
          title={WIPE_PROMPTS[pendingWipe.kind].title}
          message={WIPE_PROMPTS[pendingWipe.kind].message}
          confirmLabel={WIPE_PROMPTS[pendingWipe.kind].confirmLabel}
          onConfirm={confirmWipe}
          onCancel={cancelWipe}
        />
      ) : null}
    </div>
  );
}
