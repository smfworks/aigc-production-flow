import { useState, type FormEvent } from "react";
import { api, setOrgId } from "./api.ts";
import type { StudioOrg, StudioUser } from "./types.ts";

export function OrgSwitcher({
  me,
  orgs,
  onSwitch,
  onCreated,
  onError,
}: {
  me: StudioUser | null;
  orgs: StudioOrg[];
  onSwitch: (orgId: string) => void;
  onCreated: (org: StudioOrg) => void;
  onError: (err: unknown) => void;
}) {
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const canCreate = Boolean(me?.permissions?.includes("members"));

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !canCreate) return;
    setBusy(true);
    try {
      const org = await api.createOrg(name.trim());
      setName("");
      onCreated(org);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="org-switch">
      <label>
        Active org
        <select
          value={me?.org_id || ""}
          onChange={(event) => {
            const next = event.target.value;
            setOrgId(next);
            onSwitch(next);
          }}
          aria-label="Active organization"
        >
          {orgs.map((org) => (
            <option key={org.id} value={org.id}>
              {org.name}
              {org.is_default ? " (default)" : ""}
              {org.role ? ` · ${org.role}` : ""}
            </option>
          ))}
        </select>
      </label>
      {canCreate ? (
        <form className="org-create" onSubmit={create}>
          <input
            placeholder="New org name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button type="submit" className="btn" disabled={busy || !name.trim()}>
            Create org
          </button>
        </form>
      ) : null}
      <span className="hint">Multi-org lite — not SaaS billing.</span>
    </div>
  );
}
