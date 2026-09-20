type Props = {
  onLoadSample: () => void;
  onNewPack: () => void;
};

export function Header({ onLoadSample, onNewPack }: Props) {
  return (
    <header className="mast">
      <div className="mast-brand">
        <div className="mark" aria-hidden="true" />
        <div>
          <p className="eyebrow">SMF Works · Human-AI lab</p>
          <h1>H3 Capture Pack</h1>
        </div>
      </div>
      <p className="lede">
        Two Sparks, two jobs. Still factory is Qwen-Image-2.1 at native{" "}
        <strong>1344×768</strong> (do not stretch 1024²). Clip factory is MiniMax
        H3 + Motion-Context. A <strong>sheet</strong> is the character/prop bible;
        a <strong>plate</strong> is hop-1 / cut / fadeblack{" "}
        <code>first_frame</code>. This builder encodes the nine-gate bible — it
        does not run either engine, and it does not export MP4s.
      </p>
      <p className="lede lede-sub">
        Procedure:{" "}
        <a href="https://github.com/smfworks/h3-longform-capture/blob/main/docs/IMAGE-STILLS.md">
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
      </div>
    </header>
  );
}
