import { useMemo, useState } from "react";
import type { CandidateKind, MediaAsset, Shot, ShotReadiness } from "./types.ts";
import { CANDIDATE_KINDS, SHOT_READINESS } from "./types.ts";
import { CommentsDrawer } from "./CommentsDrawer.tsx";

type Props = {
  shots: Shot[];
  media: MediaAsset[];
  packBuilderUrl: string;
  selectedShotId?: string | null;
  onSelectShot?: (shotId: string) => void;
  onExtract: () => void;
  onReadiness: (shotId: string, readiness: ShotReadiness) => void;
  onCandidate: (
    shotId: string,
    candidateId: string,
    body: { status?: string; linked_asset_id?: string; linked_ref?: string },
  ) => void;
  onAddCandidate: (shotId: string, body: { kind: CandidateKind; label: string }) => void;
  onBreakScene?: (body: {
    action: string;
    dialogue: string;
    scene_s: number;
    continue_chain: boolean;
  }) => void;
  episodeId?: string;
  canComment?: boolean;
  canMutate?: boolean;
  onError?: (err: unknown) => void;
  onNotice?: (msg: string) => void;
};

function continueChain(shots: Shot[], shotId: string): Set<string> {
  const index = shots.findIndex((shot) => shot.id === shotId);
  if (index < 0) return new Set();
  let start = index;
  while (start > 0 && shots[start].join === "continue") start -= 1;
  let end = index;
  while (end < shots.length - 1 && shots[end + 1].join === "continue") end += 1;
  return new Set(shots.slice(start, end + 1).map((shot) => shot.id));
}

export function ShotBoard({
  shots,
  media,
  packBuilderUrl,
  selectedShotId,
  onSelectShot,
  onExtract,
  onReadiness,
  onCandidate,
  onAddCandidate,
  onBreakScene,
  episodeId,
  canComment = false,
  canMutate = true,
  onError,
  onNotice,
}: Props) {
  const [view, setView] = useState<"list" | "canvas">("list");
  const [kind, setKind] = useState<CandidateKind>("character");
  const [label, setLabel] = useState("");
  const [breakAction, setBreakAction] = useState("");
  const [breakDialogue, setBreakDialogue] = useState("");
  const [breakSeconds, setBreakSeconds] = useState("16");
  const [breakContinue, setBreakContinue] = useState(false);
  const selected =
    shots.find((shot) => shot.id === selectedShotId) ??
    shots.find((shot) => shot.hop1_required) ??
    shots[0] ??
    null;
  const inChain = useMemo(
    () => (selected ? continueChain(shots, selected.id) : new Set<string>()),
    [shots, selected],
  );

  function select(shotId: string) {
    onSelectShot?.(shotId);
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h3>Shots</h3>
        <p>
          Edit-list rows mapped to shots. Readiness is prepared, not generating. Confirm
          candidates by hand — never auto generate-ok.
        </p>
      </div>
      <div className="toolbar">
        <button type="button" className={view === "list" ? "btn btn-go" : "btn"} onClick={() => setView("list")}>
          List
        </button>
        <button
          type="button"
          className={view === "canvas" ? "btn btn-go" : "btn"}
          onClick={() => setView("canvas")}
        >
          Canvas
        </button>
        <button type="button" className="btn" onClick={onExtract} disabled={!canMutate}>
          Extract candidates (stub)
        </button>
      </div>
      {onBreakScene ? (
        <form
          className="coverage-form"
          data-testid="shot-break"
          onSubmit={(event) => {
            event.preventDefault();
            const scene_s = Number(breakSeconds);
            if (!Number.isFinite(scene_s) || scene_s <= 0) return;
            onBreakScene({
              action: breakAction,
              dialogue: breakDialogue,
              scene_s,
              continue_chain: breakContinue,
            });
          }}
        >
          <p className="editor-label">Break scene into clips</p>
          <p className="hint">
            Timed coverage, about 5–10 seconds each. This writes plan rows on the board. It does not render.
          </p>
          <label className="field">
            <span className="editor-label">Action</span>
            <textarea
              rows={2}
              value={breakAction}
              onChange={(event) => setBreakAction(event.target.value)}
              aria-label="Coverage action"
            />
          </label>
          <label className="field">
            <span className="editor-label">Dialogue</span>
            <textarea
              rows={2}
              value={breakDialogue}
              onChange={(event) => setBreakDialogue(event.target.value)}
              aria-label="Coverage dialogue"
              placeholder={"One line per beat"}
            />
          </label>
          <label className="field inline">
            <span className="editor-label">Scene seconds</span>
            <input
              type="number"
              min={1}
              step="0.1"
              value={breakSeconds}
              onChange={(event) => setBreakSeconds(event.target.value)}
              aria-label="Scene seconds"
            />
          </label>
          <label className="field inline">
            <input
              type="checkbox"
              checked={breakContinue}
              onChange={(event) => setBreakContinue(event.target.checked)}
            />
            Chain clips with continue
          </label>
          <button type="submit" className="btn" disabled={!canMutate}>
            Break into clips
          </button>
        </form>
      ) : null}
      {shots.length === 0 ? (
        <p className="empty">No edit-list shots yet. Fill the storyboard stage, or import a zip.</p>
      ) : view === "canvas" ? (
        <div className="board-canvas" role="list">
          {shots.map((shot, index) => (
            <div key={shot.id} className="board-slot">
              {index > 0 ? (
                <div className={`board-join join-${shot.join || "unset"}`}>
                  <span>{shot.join || "?"}</span>
                </div>
              ) : null}
              <button
                type="button"
                className={[
                  "board-card",
                  `join-${shot.join || "unset"}`,
                  selected?.id === shot.id ? "is-selected" : "",
                  inChain.has(shot.id) && shot.join === "continue" ? "in-chain" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => select(shot.id)}
              >
                <span className="board-kicker">
                  #{shot.sort_index + 1} · {shot.readiness}
                </span>
                <strong>
                  Take {shot.take || "—"} · {shot.song_t || "no clock"}
                </strong>
                <em>{shot.action || "no action"}</em>
                <span>{shot.entities || "no entities"}</span>
              </button>
            </div>
          ))}
        </div>
      ) : (
        <ul className="shot-list">
          {shots.map((shot) => (
            <li key={shot.id}>
              <button
                type="button"
                className={selected?.id === shot.id ? "card-btn is-on" : "card-btn"}
                onClick={() => select(shot.id)}
              >
                <strong>
                  #{shot.sort_index + 1} · {shot.join || "no join"} · take {shot.take || "—"}
                </strong>
                <span>
                  <em className={`chip-status is-${shot.readiness}`}>{shot.readiness}</em>
                  {shot.hop1_required ? " · hop-1" : ""}
                  {shot.preview?.preview_watched ? " · watched" : ""}
                  {shot.coverage?.plan_only ? ` · plan ${shot.coverage.duration_s ?? "?"}s · not rendered` : ""}
                  {" · "}
                  {shot.action || "no action"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected ? (
        <div className="join-inspector">
          <h3>
            Shot #{selected.sort_index + 1} · {selected.join || "unset"}
          </h3>
          <p className="hint">
            {selected.join === "continue"
              ? "Continue chain — same room, action continues. Plate on hop-1 only."
              : selected.join === "cut"
                ? "Cut boundary — new angle/plate, no hold."
                : selected.join === "fadeblack"
                  ? "Fadeblack boundary — new location, grade, or time of day."
                  : "Join must be continue, cut, or fadeblack."}{" "}
            ready means prepared, not a generate job.
          </p>
          <div className="states">
            {SHOT_READINESS.map((state) => (
              <button
                key={state}
                type="button"
                className={selected.readiness === state ? "btn btn-go" : "btn"}
                disabled={!canMutate}
                onClick={() => onReadiness(selected.id, state)}
              >
                {state}
              </button>
            ))}
            <a
              className="btn"
              href={`${packBuilderUrl}?step=edit&row=${selected.sort_index + 1}`}
              target="_blank"
              rel="noreferrer"
            >
              Open in pack builder
            </a>
          </div>
          <h4>Candidates</h4>
          {selected.candidates.length === 0 ? (
            <p className="empty">No candidates. Extract stub or add one by hand.</p>
          ) : (
            <ul className="candidate-list">
              {selected.candidates.map((candidate) => (
                <li key={candidate.id}>
                  <strong>
                    {candidate.kind} · {candidate.label}
                  </strong>
                  <span>
                    {candidate.status} · {candidate.source}
                  </span>
                  <em>{candidate.evidence}</em>
                  <div className="toolbar">
                    <button
                      type="button"
                      className="btn"
                      onClick={() => onCandidate(selected.id, candidate.id, { status: "accepted" })}
                    >
                      Accept
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => onCandidate(selected.id, candidate.id, { status: "ignored" })}
                    >
                      Ignore
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={() =>
                        onCandidate(selected.id, candidate.id, {
                          status: "linked",
                          linked_ref: `${candidate.kind}:${candidate.label}`,
                        })
                      }
                    >
                      Link pack entity
                    </button>
                    {media[0] ? (
                      <button
                        type="button"
                        className="btn"
                        onClick={() =>
                          onCandidate(selected.id, candidate.id, {
                            status: "linked",
                            linked_asset_id: media[0].id,
                          })
                        }
                      >
                        Link latest media
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="create-row">
            <select value={kind} onChange={(event) => setKind(event.target.value as CandidateKind)}>
              {CANDIDATE_KINDS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
            <input
              placeholder="Label (smith / francisca / wardrobe)"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
            />
            <button
              type="button"
              className="btn btn-go"
              onClick={() => {
                if (!label.trim()) return;
                onAddCandidate(selected.id, { kind, label: label.trim() });
                setLabel("");
              }}
            >
            Add candidate
          </button>
          </div>
          {episodeId && selected && onError ? (
            <CommentsDrawer
              episodeId={episodeId}
              shotId={selected.id}
              canComment={canComment}
              onError={onError}
              onNotice={onNotice}
            />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
