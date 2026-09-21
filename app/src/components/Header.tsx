import { studioImportUrl } from "../lib/studio";

type Props = {
  onLoadSample: () => void;
  onNewPack: () => void;
  onImport: () => void;
};

export function Header({ onLoadSample, onNewPack, onImport }: Props) {
  return (
    <header className="mast">
      <div className="mast-brand">
        <div className="mark" aria-hidden="true" />
        <div>
          <p className="eyebrow">SMF Works · Human-AI lab</p>
          <h1>AIGC Production Flow</h1>
        </div>
      </div>
      <p className="lede">
        Script analysis → asset setup → storyboard → video preview. A{" "}
        <strong>sheet</strong> is the character/prop bible; a{" "}
        <strong>plate</strong> is the first frame of this window. Native still
        canvas <strong>1344×768</strong> (do not stretch 1024²). This builder
        encodes the production pack (nine gates plus entity schedule and
        lock-diff) — it does not run a video engine, and it does not export
        MP4s.
      </p>
      <p className="lede lede-sub">
        Flow:{" "}
        <a href="https://github.com/smfworks/aigc-production-flow/blob/main/docs/PRODUCTION-FLOW.md">
          docs/PRODUCTION-FLOW.md
        </a>
        {" · "}
        <a href="https://github.com/smfworks/aigc-production-flow/blob/main/docs/IMAGE-STILLS.md">
          docs/IMAGE-STILLS.md
        </a>
        {" · "}
        <a href="https://www.smfclearinghouse.com/blog/2026-09-20-qwen-image-21-one-spark">
          Qwen-Image-2.1 on one Spark
        </a>
        . Wikipedia is not a still.
      </p>
      <div className="sample-row">
        <button type="button" className="btn btn-go" onClick={onLoadSample}>
          Load Sigils sample
        </button>
        <button type="button" className="btn" onClick={onNewPack}>
          New pack
        </button>
        <button type="button" className="btn" onClick={onImport}>
          Import zip
        </button>
        <a className="btn" href={studioImportUrl()} target="_blank" rel="noreferrer">
          Open in Studio
        </a>
      </div>
    </header>
  );
}
