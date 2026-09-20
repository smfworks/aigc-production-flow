import { STEPS, type StepId } from "../types";

type Props = {
  step: StepId;
  onStep: (id: StepId) => void;
};

export function StepNav({ step, onStep }: Props) {
  return (
    <nav className="steps" aria-label="Pack workflow">
      {STEPS.map((item) => (
        <button
          key={item.id}
          type="button"
          className={item.id === step ? "step is-on" : "step"}
          aria-current={item.id === step ? "step" : undefined}
          onClick={() => onStep(item.id)}
        >
          <span className="step-n">{item.n}</span>
          {item.label}
        </button>
      ))}
    </nav>
  );
}
