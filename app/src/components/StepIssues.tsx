import type { ReactNode } from "react";
import type { GateId, GateResult } from "../lib/gate";

type Props = {
  gates: GateResult[];
  ids: GateId[];
};

export function StepIssues({ gates, ids }: Props) {
  const bad = gates.filter((gate) => ids.includes(gate.id) && !gate.ok);
  if (!bad.length) return null;
  return (
    <ul className="step-issues">
      {bad.map((gate) => (
        <li key={gate.id}>
          <strong>
            Gate {gate.n}. {gate.label}
          </strong>
          <span>{gate.detail}</span>
        </li>
      ))}
    </ul>
  );
}

export function EmptyHint({ children }: { children: ReactNode }) {
  return <p className="empty-hint">{children}</p>;
}
