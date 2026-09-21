import { useState } from "react";
import type { IdentityAsset } from "./types.ts";

function KeywordRow({
  asset,
  canIdentity,
  keywords,
  onChange,
  onApprove,
  onSaveDraft,
  onUnapprove,
  approveLabel,
}: {
  asset: IdentityAsset;
  canIdentity: boolean;
  keywords: string;
  onChange: (value: string) => void;
  onApprove: () => void;
  onSaveDraft: () => void;
  onUnapprove: () => void;
  approveLabel: string;
}) {
  return (
    <>
      <label>
        Lock keywords
        <input
          value={keywords}
          disabled={!canIdentity}
          aria-label={`Lock keywords for ${asset.entity_label || asset.original_name}`}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      <p className="hint">
        Draft keywords do not count for lock-diff or generate-ok. Saving keywords on an approved
        asset returns it to draft until you re-approve.
      </p>
      <div className="toolbar">
        {asset.approved ? (
          <button type="button" className="btn" disabled={!canIdentity} onClick={onUnapprove}>
            Unapprove
          </button>
        ) : null}
        <button type="button" className="btn" disabled={!canIdentity} onClick={onSaveDraft}>
          Save draft keywords
        </button>
        <button type="button" className="btn btn-go" disabled={!canIdentity} onClick={onApprove}>
          {asset.approved ? `Re-approve ${approveLabel}` : `Approve ${approveLabel}`}
        </button>
      </div>
    </>
  );
}

export function IdentityStore({
  sheets,
  plates,
  shots,
  selectedId,
  canIdentity,
  honesty,
  onApprove,
  onSaveKeywords,
  onUnapprove,
  onLink,
  onSelect,
}: {
  sheets: IdentityAsset[];
  plates: IdentityAsset[];
  shots: { id: string; sort_index: number; take: string; edit_row_id: string }[];
  selectedId?: string | null;
  canIdentity: boolean;
  honesty: string;
  onApprove: (assetId: string, lockKeywords: string) => void;
  onSaveKeywords: (assetId: string, lockKeywords: string) => void;
  onUnapprove: (assetId: string) => void;
  onLink: (assetId: string, shotId: string) => void;
  onSelect: (assetId: string) => void;
}) {
  const [keywords, setKeywords] = useState<Record<string, string>>({});

  function keywordsFor(asset: IdentityAsset): string {
    return keywords[asset.id] ?? asset.lock_keywords ?? "";
  }

  function setKeyword(assetId: string, value: string) {
    setKeywords((current) => ({ ...current, [assetId]: value }));
  }

  return (
    <section className="panel" id="identity-store" data-testid="identity-store">
      <div className="panel-head">
        <h3>Identity store</h3>
        <p>{honesty}</p>
      </div>
      <p className="hint">
        Approved sheets and per-window plates. Draft does not count for lock-diff or generate
        readiness. Unapprove is audited. Not embeddings. Fixture/placeholder metadata only in this
        public tree — no likeness stills.
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
                <span data-testid="identity-status" data-state={asset.approved ? "green" : "red"}>
                  {asset.entity_type || "entity"}
                  {asset.approved_by ? ` · approved by ${asset.approved_by}` : " · draft"}
                </span>
              </button>
              <KeywordRow
                asset={asset}
                canIdentity={canIdentity}
                keywords={keywordsFor(asset)}
                onChange={(value) => setKeyword(asset.id, value)}
                onApprove={() => onApprove(asset.id, keywordsFor(asset))}
                onSaveDraft={() => onSaveKeywords(asset.id, keywordsFor(asset))}
                onUnapprove={() => onUnapprove(asset.id)}
                approveLabel="sheet"
              />
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
                <span data-testid="identity-status" data-state={asset.approved ? "green" : "red"}>
                  {asset.shot_id ? `linked shot ${asset.shot_id.slice(0, 8)}` : "unlinked"}
                  {asset.edit_row_id ? ` · window ${asset.edit_row_id}` : ""}
                  {asset.approved ? "" : " · draft"}
                </span>
              </button>
              <label>
                Link to shot
                <select
                  value={asset.shot_id || ""}
                  disabled={!canIdentity}
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
              <KeywordRow
                asset={asset}
                canIdentity={canIdentity}
                keywords={keywordsFor(asset)}
                onChange={(value) => setKeyword(asset.id, value)}
                onApprove={() => onApprove(asset.id, keywordsFor(asset))}
                onSaveDraft={() => onSaveKeywords(asset.id, keywordsFor(asset))}
                onUnapprove={() => onUnapprove(asset.id)}
                approveLabel="plate"
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
