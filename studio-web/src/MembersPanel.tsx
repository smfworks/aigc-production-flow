import { useEffect, useState, type FormEvent } from "react";
import { api } from "./api.ts";
import type { OrgMember, OrgRole, RoleMatrixRow, StudioUser } from "./types.ts";

const ROLES: OrgRole[] = ["producer", "editor", "writer", "art", "reviewer", "viewer"];

const MATRIX_COLUMNS = [
  { id: "read", label: "Read" },
  { id: "script", label: "Script" },
  { id: "identity", label: "Identity" },
  { id: "edit", label: "Edit list" },
  { id: "jobs", label: "Jobs" },
  { id: "pack", label: "Pack" },
  { id: "signoff", label: "Sign-off" },
  { id: "budget", label: "Budget" },
  { id: "members", label: "Members" },
] as const;

export function MembersPanel({
  me,
  onError,
  onNotice,
}: {
  me: StudioUser | null;
  onError: (err: unknown) => void;
  onNotice: (msg: string) => void;
}) {
  const orgId = me?.org_id;
  const canManage = Boolean(me?.permissions.includes("members"));
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [matrix, setMatrix] = useState<RoleMatrixRow[]>([]);
  const [name, setName] = useState("");
  const [role, setRole] = useState<OrgRole>("viewer");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!orgId) return;
    void api.members(orgId).then(setMembers).catch(onError);
    void api
      .meta()
      .then((meta) => setMatrix(meta.role_matrix || []))
      .catch(onError);
  }, [orgId, onError]);

  if (!orgId) return null;

  async function add(event: FormEvent) {
    event.preventDefault();
    if (!orgId || !name.trim()) return;
    setBusy(true);
    try {
      await api.addMember(orgId, { user_name: name.trim(), role });
      setName("");
      setMembers(await api.members(orgId));
      onNotice(`Added ${name.trim()} as ${role}`);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  }

  async function change(member: OrgMember, next: OrgRole) {
    if (!orgId) return;
    try {
      await api.changeMemberRole(orgId, member.id, next);
      setMembers(await api.members(orgId));
      onNotice(`${member.user_name} → ${next}`);
    } catch (err) {
      onError(err);
    }
  }

  return (
    <section className="panel" data-testid="members-panel">
      <div className="panel-head">
        <h2>Org members</h2>
        <p>
          App-level roles on the <strong>active org</strong>. <code>writer</code> and <code>art</code>{" "}
          are the pack-convention roles. Legacy <code>editor</code> stays the craft bundle (script +
          identity + edit list + jobs + pack). Reviewers still sign off. Viewers stay read-only.
          This is not IdP groups unless the optional OIDC claim map is enabled. docs/AUTH.md.
        </p>
      </div>
      <table className="matrix" data-testid="role-matrix">
        <thead>
          <tr>
            <th>Role</th>
            {MATRIX_COLUMNS.map((column) => (
              <th key={column.id}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(matrix.length ? matrix : ROLES.map((item) => ({ role: item, label: item, legacy: true, permissions: [] as string[], note: "" }))).map(
            (row) => (
              <tr key={row.role}>
                <th>
                  <em className={`role-chip is-${row.role}`}>{row.label || row.role}</em>
                  {row.legacy ? <span className="hint"> legacy</span> : null}
                </th>
                {MATRIX_COLUMNS.map((column) => (
                  <td key={column.id}>{row.permissions.includes(column.id) ? "yes" : ""}</td>
                ))}
              </tr>
            ),
          )}
        </tbody>
      </table>
      <ul className="matrix-notes">
        {matrix.map((row) => (
          <li key={row.role}>
            <strong>{row.role}</strong> — {row.note}
          </li>
        ))}
      </ul>
      <ul className="member-list">
        {members.map((member) => (
          <li key={member.id}>
            <strong>{member.user_name}</strong>
            <em className={`role-chip is-${member.role}`}>{member.role}</em>
            {canManage ? (
              <select
                value={member.role}
                onChange={(event) => void change(member, event.target.value as OrgRole)}
                aria-label={`Role for ${member.user_name}`}
              >
                {ROLES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            ) : null}
          </li>
        ))}
      </ul>
      {canManage ? (
        <form className="create-row" onSubmit={add}>
          <input
            placeholder="Local user name (X-User-Name)"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <select value={role} onChange={(event) => setRole(event.target.value as OrgRole)} aria-label="Role for new member">
            {ROLES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn-go" disabled={busy}>
            Add member
          </button>
        </form>
      ) : (
        <p className="hint">Only producers can add members or change roles.</p>
      )}
    </section>
  );
}
