import { useEffect, useState, type FormEvent } from "react";
import { api } from "./api.ts";
import type { OrgMember, OrgRole, StudioUser } from "./types.ts";

const ROLES: OrgRole[] = ["producer", "editor", "reviewer", "viewer"];

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
  const [name, setName] = useState("");
  const [role, setRole] = useState<OrgRole>("viewer");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!orgId) return;
    void api.members(orgId).then(setMembers).catch(onError);
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
    <section className="panel">
      <div className="panel-head">
        <h2>Org members</h2>
        <p>
          App-level roles on the default org. Identity is still the local-dev token / X-User-Name
          (or X-Forwarded-User). OIDC is not implemented — docs/AUTH.md.
        </p>
      </div>
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
          <select value={role} onChange={(event) => setRole(event.target.value as OrgRole)}>
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
