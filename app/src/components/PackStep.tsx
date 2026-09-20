import type { AudioPath, CapturePack, SpeechMode } from "../types";
import { STACK_LINE } from "../types";
import { TextArea, TextField } from "./Field";

type Props = {
  pack: CapturePack;
  onChange: (pack: CapturePack) => void;
};

const AUDIO: { value: AudioPath; label: string }[] = [
  { value: "na-mute", label: "N/A + mute in NLE" },
  { value: "prompt-score", label: "prompt score" },
  { value: "silence", label: "silence" },
];

const SPEECH: { value: SpeechMode; label: string }[] = [
  { value: "none", label: "none" },
  { value: "finish-by-8s", label: "lines finish by 8.0 s" },
];

export function PackStep({ pack, onChange }: Props) {
  return (
    <section>
      <div className="editor-head">
        <h2>New pack</h2>
        <p>
          Title, log line, duration, and exactly one audio path. Speech and
          chorus hits finish by 8.0 s in a 10.125 s window. Stills are a second
          Spark (Qwen-Image-2.1 at 1344×768); clips are MiniMax H3 +
          Motion-Context.
        </p>
      </div>
      <div className="stack">
        <TextField
          label="Title"
          value={pack.title}
          onChange={(title) => onChange({ ...pack, title })}
          placeholder="Working title"
        />
        <TextArea
          label="Log line (one sentence)"
          value={pack.logLine}
          onChange={(logLine) => onChange({ ...pack, logLine })}
          placeholder="One sentence. Prop numbers pinned before generate."
        />
        <div className="grid-2">
          <TextField
            label="Duration target"
            value={pack.durationTarget}
            onChange={(durationTarget) => onChange({ ...pack, durationTarget })}
            placeholder="4:00"
            mono
          />
          <TextField
            label="Song / narrative clock"
            value={pack.songNarrativeClock}
            onChange={(songNarrativeClock) =>
              onChange({ ...pack, songNarrativeClock })
            }
            placeholder="0:00 · 0:18 · 0:46"
            mono
          />
        </div>
        <div>
          <p className="editor-label">Audio path (exactly one)</p>
          <div className="seg-row">
            {AUDIO.map((option) => (
              <button
                key={option.value}
                type="button"
                className={pack.audioPath === option.value ? "seg is-on" : "seg"}
                onClick={() => onChange({ ...pack, audioPath: option.value })}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="field-hint">
            N/A + mute the AAC in the editor, or a prompt score, or silence. Not
            both a mastered track and a prompt score.
          </p>
        </div>
        <div>
          <p className="editor-label">Speech</p>
          <div className="seg-row">
            {SPEECH.map((option) => (
              <button
                key={option.value}
                type="button"
                className={pack.speech === option.value ? "seg is-on" : "seg"}
                onClick={() => onChange({ ...pack, speech: option.value })}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <TextArea
          label="Forbidden (global)"
          value={pack.forbiddenGlobal}
          onChange={(forbiddenGlobal) => onChange({ ...pack, forbiddenGlobal })}
        />
        <p className="field-hint">
          Stack (exported, not a serving pin): {STACK_LINE}
        </p>
      </div>
    </section>
  );
}
