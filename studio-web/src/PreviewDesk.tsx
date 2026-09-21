import { useRef, useState, type FormEvent } from "react";
import { api } from "./api.ts";
import type { ContinuityReceipt, MediaAsset, PreviewDesk, Shot } from "./types.ts";

type Props = {
  episodeId: string;
  desk: PreviewDesk | null;
  shots: Shot[];
  media: MediaAsset[];
  selectedShotId?: string | null;
  onSelectShot?: (shotId: string) => void;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
  onChanged: () => void;
};

export function PreviewDesk({
  episodeId,
  desk,
  shots,
  media,
  selectedShotId,
  onSelectShot,
  onError,
  onNotice,
  onChanged,
}: Props) {
  const required =
    desk?.shots.filter((row) => row.required) ??
    shots
      .filter((item) => item.hop1_required)
      .map((item) => ({
        shot: item,
        required: true,
        complete: Boolean(item.preview?.complete),
        extend_ok: Boolean(item.preview?.extend_ok),
        blockers: item.preview?.blockers ?? [],
      }));
  const selected = required.find((row) => row.shot.id === selectedShotId) ?? required[0];
  const shot = selected?.shot;
  const [duration, setDuration] = useState("");
  const [frames, setFrames] = useState("");
  const [lock, setLock] = useState("");
  const [ng, setNg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const receipt: ContinuityReceipt | null | undefined = shot?.preview;

  async function submit(event: FormEvent, watched: boolean) {
    event.preventDefault();
    if (!shot) return;
    try {
      const file = fileRef.current?.files?.[0];
      if (file) {
        await api.attachPreview(episodeId, shot.id, {
          file,
          duration_s: duration,
          frames,
          still_vs_lock: lock || receipt?.still_vs_lock,
          ng_reason: ng,
          watched,
        });
      } else {
        await api.setReceipt(episodeId, shot.id, {
          media_id: receipt?.media_id || media.find((asset) => asset.kind === "preview")?.id,
          duration_s: duration ? Number(duration) : receipt?.duration_s,
          frames: frames ? Number(frames) : receipt?.frames,
          still_vs_lock: lock || receipt?.still_vs_lock,
          ng_reason: ng,
          watched,
        });
      }
      if (fileRef.current) fileRef.current.value = "";
      setDuration("");
      setFrames("");
      onNotice(watched ? "Hop-1 preview watched" : "Continuity receipt saved");
      onChanged();
    } catch (err) {
      onError(err);
    }
  }

  return (
    <section className="panel" id="preview-desk">
      <div className="panel-head">
        <h3>Hop-1 preview desk</h3>
        <p>
          One hop-1 per planned take. Attach the stub receipt or a local preview file, fill
          duration/frames + still-vs-lock, then mark preview-watched. generate-ok and clip-extend stay
          blocked until every required hop-1 has that stamp. An NG reason still blocks spend.
        </p>
      </div>
      {desk ? (
        <p className="hint">
          {desk.complete_count}/{desk.required_count} required hop-1s complete.
          {desk.generate_ok_ready ? " Ready for generate-ok." : " generate-ok blocked."}
        </p>
      ) : null}
      {required.length === 0 ? (
        <p className="empty">Import a pack with hop-1 planned takes to open the desk.</p>
      ) : (
        <ul className="shot-list">
          {required.map((row) => {
            const item = row.shot;
            const complete = row.complete;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={shot?.id === item.id ? "card-btn is-on" : "card-btn"}
                  onClick={() => onSelectShot?.(item.id)}
                >
                  <strong>
                    #{item.sort_index + 1} · take {item.take || "—"} · hop-1
                  </strong>
                  <span>
                    <em className={`chip-status ${complete ? "is-ready" : "is-candidates"}`}>
                      {complete ? "watched" : item.preview?.preview_watched ? "receipt" : "needed"}
                    </em>
                    {item.preview?.ng_reason ? " · NG" : ""}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {shot ? (
        <form className="stack" onSubmit={(event) => void submit(event, false)}>
          <p className="hint">
            Shot #{shot.sort_index + 1}.{" "}
            {shot.preview?.blockers?.length
              ? shot.preview.blockers.join(" ")
              : "Receipt complete — clip-extend and generate-ok can proceed if gates are green."}
          </p>
          <div className="create-row">
            <input
              placeholder="Duration seconds (e.g. 10.125)"
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
            />
            <input
              placeholder="Frames (e.g. 243)"
              value={frames}
              onChange={(event) => setFrames(event.target.value)}
            />
          </div>
          <textarea
            placeholder="Still-vs-lock note (required)"
            rows={2}
            value={lock}
            onChange={(event) => setLock(event.target.value)}
          />
          <input
            placeholder="NG reason (optional — blocks generate-ok / extend)"
            value={ng}
            onChange={(event) => setNg(event.target.value)}
          />
          <div className="toolbar">
            <button type="button" className="btn" onClick={() => fileRef.current?.click()}>
              Attach preview / receipt
            </button>
            <input
              ref={fileRef}
              type="file"
              hidden
              accept=".json,.txt,.md,.png,.jpg,.jpeg,.webp,.mp4,.webm,.mov,application/json,video/mp4"
            />
            <button type="submit" className="btn">
              Save receipt
            </button>
            <button type="button" className="btn btn-go" onClick={(event) => void submit(event, true)}>
              Mark preview-watched
            </button>
          </div>
          {receipt ? (
            <p className="hint">
              {receipt.duration_s ?? "—"}s / {receipt.frames ?? "—"}f · {receipt.source}
              {receipt.preview_watched ? ` · watched by ${receipt.watched_by}` : " · not watched"}
              {receipt.media_id ? " · media attached" : ""}
            </p>
          ) : null}
        </form>
      ) : null}
    </section>
  );
}
