import { useState } from "react";
import type { IdentityAsset } from "./types.ts";

export function IdentityStore({
  sheets,
  plates,
  shots,
  selectedId,
  canMutate,
  honesty,
  onApprove,
  onLink,
  onSelect,
}: {
  sheets: IdentityAsset[];
  plates: IdentityAsset[];
  shots: { id: string; sort_index: number; take: string; edit_row_id: string }[];
  selectedId?: string | null;
  canMutate: boolean;
  honesty: string;
  onApprove: (assetId: string, lockKeywords: string) => void;
  onLink: (assetId: string, shotId: string) => void;
  onSelect: (assetId: string) => void;
}) {
  const [keywords, setKeywords] = useState<Record<string, string>>({});

  function keywordsFor(asset: IdentityAsset): string {
    return keywords[asset.id] ?? asset.lock_keywords ?? "";
  }

  return (
    <section className="panel" id="identity-store">
      <div className="panel-head">
        <h3>Identity store</h3>
        <p>{honesty}</p>
      </div>
      <p className="hint">
        Approved sheets and per-window plates. Draft does not count for lock-diff or generate
        readiness. Not embeddings. Fixture/placeholder metadata only in this public tree — no
        likeness stills.
      </p>
      <h4>Sheets</h4>
      {sheets.length === 0 ? (
        <p className="empty">No character/prop sheets yet. Upload kind=sheet in Media, then approve here.</p>
      ) : (
        <ul className="identity-list">
          {sheets.map((asset) => (
            <li key={asset.id} className={selectedId === asset.id ? "is-selected" : ""}>
              <button type="button" className="card-btn" onClick={() => onSelect(asset.id)}>
                <strong>
                  {asset.entity_label || asset.original_name} · {asset.approval_status}
                </strong>
                <span>
                  {asset.entity_type || "entity"}
                  {asset.approved_by ? ` · approved by ${asset.approved_by}` : " · draft"}
                </span>
              </button>
              <label>
                Lock keywords
                <input
                  value={keywordsFor(asset)}
                  disabled={!canMutate || asset.approved}
                  onChange={(event) =>
                    setKeywords((current) => ({ ...current, [asset.id]: event.target.value }))
                  }
                />
              </label>
              {asset.approved ? null : (
                <button
                  type="button"
                  className="btn"
                  disabled={!canMutate}
                  onClick={() => onApprove(asset.id, keywordsFor(asset))}
                >
                  Approve sheet
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <h4>Plates</h4>
      {plates.length === 0 ? (
        <p className="empty">No per-window plates yet. Upload kind=plate, link to a shot, then approve.</p>
      ) : (
        <ul className="identity-list">
          {plates.map((asset) => (
            <li key={asset.id} className={selectedId === asset.id ? "is-selected" : ""}>
              <button type="button" className="card-btn" onClick={() => onSelect(asset.id)}>
                <strong>
                  {asset.entity_label || asset.original_name} · {asset.approval_status}
                </strong>
                <span>
                  {asset.shot_id ? `linked shot ${asset.shot_id.slice(0, 8)}` : "unlinked"}
                  {asset.edit_row_id ? ` · window ${asset.edit_row_id}` : ""}
                </span>
              </button>
              <label>
                Link to shot
                <select
                  value={asset.shot_id || ""}
                  disabled={!canMutate}
                  onChange={(event) => {
                    const shotId = event.target.value;
                    if (shotId) onLink(asset.id, shotId);
                  }}
                >
                  <option value="">select shot / window</option>
                  {shots.map((shot) => (
                    <option key={shot.id} value={shot.id}>
                      #{shot.sort_index + 1} · take {shot.take || "—"}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Lock keywords
                <input
                  value={keywordsFor(asset)}
                  disabled={!canMutate || asset.approved}
                  onChange={(event) =>
                    setKeywords((current) => ({ ...current, [asset.id]: event.target.value }))
                  }
                />
              </label>
              {asset.approved ? null : (
                <button
                  type="button"
                  className="btn"
                  disabled={!canMutate}
                  onClick={() => onApprove(asset.id, keywordsFor(asset))}
                >
                  Approve plate
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
