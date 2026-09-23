import { useEffect, useState } from "react";
import { api } from "./api.ts";
import type { AgentRun, AgentStep } from "./types.ts";

type Props = {
  runId: string;
  onError: (err: unknown) => void;
};

function stepTitle(step: AgentStep): string {
  if (step.kind === "stitch") return "Stitch";
  if (step.kind === "still-sheet") return `Sheet · ${step.subject || "untitled"}`;
  if (step.kind === "still-plate") return `Plate · ${step.subject || "window"}`;
  if (step.kind === "clip-hop1") return `Hop-1 · take ${step.take || "—"}`;
  return step.kind;
}

function stepState(step: AgentStep): string {
  if (step.kind === "stitch") {
    if (step.produced_mp4) return "Concat file · not completed";
    if (step.status === "planned" || step.status === "queued" || step.status === "running") return step.status;
    return "Awaiting stitch";
  }
  if (step.status === "refused_live") return "Live generate refused";
  if (step.status === "succeeded" && !step.called_comfy) return "Fixture receipt";
  return step.status;
}

export function AgentRunStatus({ runId, onError }: Props) {
  const [run, setRun] = useState<AgentRun | null>(null);

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const next = await api.agentRun(runId);
        if (!stop) setRun(next);
      } catch (err) {
        if (!stop) onError(err);
      }
    }
    void tick();
    const id = window.setInterval(() => {
      void tick();
    }, 2000);
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [onError, runId]);

  if (!run) {
    return (
      <p className="hint" data-testid="agent-run-pending">
        Reading the agent run…
      </p>
    );
  }

  const live = run.called_comfy;
  const hermes = run.hermes_ran;

  return (
    <section className="agent-run" data-testid="agent-run" data-state={run.status}>
      <div className="panel-head">
        <h3>Agent run</h3>
        <p data-testid="agent-run-honesty">{run.honesty_note}</p>
      </div>
      <p className="wizard-flags">
        <span data-testid="flag-comfy">{live ? "Comfy was called" : "Comfy was not called"}</span>
        <span data-testid="flag-hermes">{hermes ? "Hermes reported a run" : "Hermes was not invoked"}</span>
        <span data-testid="flag-stitch">
          {run.stitch_state === "stitched"
            ? "Stitch wrote a file. Not a completed episode."
            : run.stitch_state === "awaiting_stitch"
              ? "Awaiting stitch"
              : "Stitch pending"}
        </span>
      </p>
      <ol className="agent-steps">
        {run.steps.map((step) => (
          <li key={`${step.order}-${step.kind}`} data-kind={step.kind} data-status={step.status}>
            <span className="agent-order">{step.order}</span>
            <span>
              <strong>{stepTitle(step)}</strong>
              <span className="hint"> {stepState(step)}</span>
              {step.kind === "stitch" && !step.produced_mp4 ? (
                <span className="hint" data-testid="stitch-awaiting">
                  {" "}
                  No MP4 was produced. The concat plan is the contract until real clip files exist.
                </span>
              ) : null}
              {step.error ? <span className="hint"> {step.error}</span> : null}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
