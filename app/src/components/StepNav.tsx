import { STEPS, type StepId } from "../types";

type Props = {
  step: StepId;
  onStep: (id: StepId) => void;
};

const STAGES = [...new Set(STEPS.map((item) => item.stage))];

export function StepNav({ step, onStep }: Props) {
  return (
    <nav className="flow" aria-label="Production flow">
      {STAGES.map((stage) => (
        <div key={stage} className="flow-stage">
          <p className="flow-stage-label">{stage}</p>
          <div className="steps">
            {STEPS.filter((item) => item.stage === stage).map((item) => (
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
          </div>
        </div>
      ))}
    </nav>
  );
}
