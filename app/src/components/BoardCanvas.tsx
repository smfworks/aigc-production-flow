import { JOIN_TYPES, type CapturePack, type JoinType } from "../types";
import { formatCameraCell } from "../lib/camera";
import { missingIdentityHoldPlate, parseEntityList, scheduleAppliesToRow } from "../lib/entitySchedule";
import { isHop1EditRow, missingIdentityPlate } from "../lib/stills";

type Props = {
  pack: CapturePack;
  selectedId?: string;
  onSelect?: (id: string) => void;
};

function joinClass(join: JoinType | ""): string {
  if (join === "continue") return "join-continue";
  if (join === "cut") return "join-cut";
  if (join === "fadeblack") return "join-fade";
  return "join-unset";
}

export function continueChainAt(pack: CapturePack, index: number): { start: number; end: number } {
  let start = index;
  while (start > 0 && pack.editList[start].join === "continue") start -= 1;
  let end = index;
  while (end < pack.editList.length - 1 && pack.editList[end + 1].join === "continue") end += 1;
  return { start, end };
}

export function BoardCanvas({ pack, selectedId, onSelect }: Props) {
  const selectedIndex = pack.editList.findIndex((row) => row.id === selectedId);
  const chain =
    selectedIndex >= 0 ? continueChainAt(pack, selectedIndex) : null;
  const selected = selectedIndex >= 0 ? pack.editList[selectedIndex] : null;

  return (
    <div className="board-wrap">
      <div className="board-canvas" role="list">
        {pack.editList.map((row, index) => {
          const selectedHere = row.id === selectedId;
          const inChain = chain ? index >= chain.start && index <= chain.end : false;
          const plateGap = missingIdentityPlate(pack, index);
          const holds = pack.entitySchedule.filter(
            (item) => item.identityHold && scheduleAppliesToRow(pack, item, index),
          );
          const holdGaps = holds
            .map((item) => missingIdentityHoldPlate(pack, item, index))
            .filter(Boolean);
          return (
            <div key={row.id} className="board-slot" role="listitem">
              {index > 0 ? (
                <div
                  className={`board-join ${joinClass(row.join)}`}
                  title={row.join || "no join"}
                >
                  <span>{row.join || "?"}</span>
                </div>
              ) : null}
              <button
                type="button"
                className={[
                  "board-card",
                  joinClass(row.join),
                  selectedHere ? "is-selected" : "",
                  inChain && row.join === "continue" ? "in-chain" : "",
                  plateGap || holdGaps.length ? "is-bad" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => onSelect?.(row.id)}
              >
                <span className="board-kicker">
                  #{index + 1}
                  {isHop1EditRow(pack, index) ? " · hop-1" : ""}
                </span>
                <strong>
                  Take {row.take || "—"} · {row.songT || "no clock"}
                </strong>
                <em>{row.action || "no action"}</em>
                <span className="board-meta">
                  {formatCameraCell(row.cameraVerb, row.cameraAmplitude, row.cameraSpeed) || "no verb"}
                </span>
                {parseEntityList(row.entities).length ? (
                  <span className="board-cast">{row.entities}</span>
                ) : (
                  <span className="board-cast is-muted">no entities</span>
                )}
              </button>
            </div>
          );
        })}
      </div>
      <aside className="join-inspector">
        <h3>Join inspector</h3>
        {!selected ? (
          <p className="field-hint">Select a board card. Continue chains stay connected; cut and fadeblack are boundaries.</p>
        ) : (
          <>
            <p>
              <strong>#{selectedIndex + 1}</strong> is{" "}
              <code>{selected.join || "unset"}</code> into take {selected.take || "—"}.
            </p>
            {selected.join === "continue" && chain ? (
              <p>
                Continue chain: rows {chain.start + 1}–{chain.end + 1}. Same room, action continues.
                Plate on hop-1 only; hop 2+ is the latent.
              </p>
            ) : null}
            {selected.join === "cut" ? (
              <p>
                Cut boundary. New angle/plate, no hold. Identity hold needs a cut plate bound to the
                entity, not a wardrobe paragraph.
              </p>
            ) : null}
            {selected.join === "fadeblack" ? (
              <p>
                Fadeblack boundary. New location, grade, or time of day. New hop-1 plate in the new
                room.
              </p>
            ) : null}
            {JOIN_TYPES.includes(selected.join as JoinType) ? null : (
              <p className="danger">Join must be continue, cut, or fadeblack.</p>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
