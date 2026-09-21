import { useEffect, useState } from "react";
import { api, fetchMediaBlob } from "./api.ts";
import type { PlaylistScrubShot } from "./types.ts";

export function PlaylistScrubber({
  episodeId,
  onError,
}: {
  episodeId: string;
  onError: (err: unknown) => void;
}) {
  const [shots, setShots] = useState<PlaylistScrubShot[]>([]);
  const [honesty, setHonesty] = useState("");
  const [index, setIndex] = useState(0);
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .playlistScrub(episodeId)
      .then((body) => {
        if (cancelled) return;
        setHonesty(body.honesty);
        setShots(body.shots);
        setIndex(0);
      })
      .catch(onError);
    return () => {
      cancelled = true;
    };
  }, [episodeId, onError]);

  const shot = shots[index] ?? null;
  const mediaId = shot?.media_id && (shot.playable || shot.image) ? shot.media_id : null;

  useEffect(() => {
    if (!mediaId) {
      setSrc(null);
      return;
    }
    let cancelled = false;
    let objectUrl = "";
    void fetchMediaBlob(mediaId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(onError);
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [mediaId, onError]);

  const last = Math.max(shots.length - 1, 0);

  return (
    <section className="panel" id="playlist-scrubber" data-testid="playlist-scrubber">
      <div className="panel-head">
        <h3>Playlist scrubber</h3>
        <p>{honesty || "Metadata and local preview playback only. Not an NLE."}</p>
      </div>
      {shots.length === 0 ? (
        <p className="empty" data-testid="playlist-empty">
          No shots on this playlist yet. Import a pack to see the edit-list order. This is not a
          timeline editor, and no preview file is invented.
        </p>
      ) : (
        <>
          <div className="scrub-transport">
            <button type="button" className="btn" disabled={index <= 0} onClick={() => setIndex((n) => Math.max(0, n - 1))}>
              Previous
            </button>
            <label className="scrub-range">
              Shot {index + 1} / {shots.length}
              <input
                type="range"
                min={0}
                max={last}
                value={index}
                aria-label="Scrub shot playlist"
                onChange={(event) => setIndex(Number(event.target.value))}
              />
            </label>
            <button
              type="button"
              className="btn"
              disabled={index >= last}
              onClick={() => setIndex((n) => Math.min(last, n + 1))}
            >
              Next
            </button>
          </div>
          {shot ? (
            <div className="scrub-stage" data-testid="playlist-stage">
              <p>
                <strong>
                  #{shot.sort_index + 1} · take {shot.take || "—"} · {shot.join || "no join"}
                </strong>
                {shot.song_t ? ` · ${shot.song_t}` : ""}
                {shot.duration_s != null ? ` · ${shot.duration_s}s` : ""}
                {shot.frames != null ? ` · ${shot.frames}f` : ""}
                {shot.preview_watched ? " · watched" : ""}
              </p>
              {shot.action ? <p className="hint">{shot.action}</p> : null}
              {shot.empty ? (
                <p className="empty" data-testid="playlist-shot-empty">
                  No local preview on this shot. Attach a hop-1 file (kind=preview) on the desk.
                  Stub JSON is metadata only — this view will not invent an MP4.
                </p>
              ) : null}
              {shot.stub ? (
                <p className="hint" data-testid="playlist-stub">
                  Stub preview{shot.original_name ? ` (${shot.original_name})` : ""}. {shot.note}{" "}
                  Playback is metadata only until a real local preview file is stored.
                </p>
              ) : null}
              {shot.playable && src ? (
                <video src={src} controls preload="metadata" data-testid="playlist-video" />
              ) : null}
              {shot.image && src ? <img src={src} alt={shot.original_name || "preview still"} /> : null}
              {shot.playable && !src ? <p className="hint">Loading local preview…</p> : null}
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
