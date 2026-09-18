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
        Lock the pack before you spend GPU. A song map and a Wikipedia tab are not
        a generate list. This builder encodes the nine-gate bible — it does not
        run MiniMax, and it does not export MP4s.
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
