import { CardsStep } from "./components/CardsStep";
import { EditListStep } from "./components/EditListStep";
import { GatePanel } from "./components/GatePanel";
import { Header } from "./components/Header";
import { MapStep } from "./components/MapStep";
import { PackStep } from "./components/PackStep";
import { SmokeStep } from "./components/SmokeStep";
import { StepNav } from "./components/StepNav";
import { TakesStep } from "./components/TakesStep";
import { Toast } from "./components/Toast";
import { allGatesGreen, evaluateGates } from "./lib/gate";
import { downloadBlob, packToZipBlob, zipFilename } from "./lib/exportZip";
import { clonePack, emptyPack } from "./lib/pack";
import { sigilsSample } from "./lib/sample";
import { initialPack, saveStoredPack } from "./lib/storage";
import type { CapturePack, StepId } from "./types";
import { useCallback, useEffect, useMemo, useState } from "react";

export default function App() {
  const [pack, setPack] = useState<CapturePack>(() => initialPack(sigilsSample()));
  const [step, setStep] = useState<StepId>("pack");
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const showToast = useCallback((message: string) => {
    setToast(message);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 2400);
    return () => window.clearTimeout(id);
  }, [toast]);

  useEffect(() => {
    const id = window.setTimeout(() => saveStoredPack(pack), 280);
    return () => window.clearTimeout(id);
  }, [pack]);

  const gates = useMemo(() => evaluateGates(pack), [pack]);
  const complete = useMemo(() => allGatesGreen(pack), [pack]);

  const loadSample = useCallback(() => {
    setPack(clonePack(sigilsSample()));
    setStep("pack");
    showToast("Loaded Sigils lessons sample.");
  }, [showToast]);

  const newPack = useCallback(() => {
    setPack(emptyPack());
    setStep("pack");
    showToast("New pack.");
  }, [showToast]);

  const exportZip = useCallback(
    async (asDraft: boolean) => {
      if (asDraft === false && !complete) return;
      setBusy(true);
      try {
        const blob = await packToZipBlob(pack);
        downloadBlob(blob, zipFilename(pack, !asDraft && complete));
        showToast(asDraft ? "Draft zip downloaded." : "Pack zip downloaded.");
      } catch (error) {
        showToast(error instanceof Error ? error.message : "Export failed.");
      } finally {
        setBusy(false);
      }
    },
    [complete, pack, showToast],
  );

  return (
    <div className="page">
      <div className="ambient" aria-hidden="true" />
      <Header onLoadSample={loadSample} onNewPack={newPack} />
      <div className="workspace">
        <main className="editor">
          <StepNav step={step} onStep={setStep} />
          {step === "pack" ? (
            <PackStep pack={pack} onChange={setPack} />
          ) : null}
          {step === "map" ? <MapStep pack={pack} onChange={setPack} /> : null}
          {step === "takes" ? (
            <TakesStep pack={pack} onChange={setPack} />
          ) : null}
          {step === "edit" ? (
            <EditListStep pack={pack} onChange={setPack} />
          ) : null}
          {step === "cards" ? (
            <CardsStep pack={pack} onChange={setPack} />
          ) : null}
          {step === "smoke" ? (
            <SmokeStep pack={pack} onChange={setPack} />
          ) : null}
        </main>
        <GatePanel
          gates={gates}
          complete={complete}
          busy={busy}
          onExport={() => void exportZip(false)}
          onExportDraft={() => void exportZip(true)}
        />
      </div>
      <footer className="site-foot">
        <p>
          H3 Capture Pack · SMF Works ·{" "}
          <a href="https://github.com/smfworks/h3-longform-capture">GitHub</a>
          {" · "}
          <a href="https://www.smfclearinghouse.com/blog/2026-09-17-h3-longform-capture-bible">
            Lock the bible before the GPU
          </a>
        </p>
        <p className="fineprint">
          MIT templates remain the source of truth under <code>templates/</code>{" "}
          and <code>docs/</code>. This app is a client-side form over that gate.
          No MiniMax weights, no generated media, no uploads. Intelligence is
          abundant. Judgment is the product.
        </p>
      </footer>
      <Toast message={toast} />
    </div>
  );
}
