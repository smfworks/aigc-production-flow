# Auth (studio spine)

Identity modes pick **who the process believes you are**. App-level **roles** (`producer` / `editor` / `writer` / `art` / `reviewer` / `viewer`) sit on each organization the user belongs to. They are not IdP groups unless the optional OIDC claim map is enabled.

**OIDC is opt-in and off by default.** This repo does not ship a production IdP. Local-dev remains the default. Do not treat a local token or a lab JWKS as multi-tenant SaaS security.

**Multi-org lite (Phase 7):** a producer can create additional organizations. `GET /api/orgs` lists orgs the caller belongs to. Send `X-Org-Id` to switch the active org (studio-web chrome does this). Members and projects are scoped to that org; other orgs 404. Existing single-org databases keep the seeded default org (`SMF Works (local)`). This is **not** billing, **not** SSO org mapping, and **not** a SaaS tenancy model. Optional OIDC role claims still only upsert membership on the **default** org when `STUDIO_OIDC_APPLY_ROLE_CLAIM` is true.

## Identity modes (`STUDIO_AUTH_MODE`)

Use the named values `local` (default), `forward-header`, or `oidc`. Aliases for local: `local-dev`, `token`, `bearer`.

| Value | Identity | API gate |
|---|---|---|
| `local` | `X-User-Name` or `STUDIO_DEFAULT_USER` (`local-dev`) | Bearer `STUDIO_API_TOKEN` |
| `forward-header` | **Required** `X-Forwarded-User` (set by the reverse proxy after it authenticates the human) | Bearer token still required so scripts and the Vite shell keep working |
| `oidc` | JWT claims (`preferred_username`, then `email`, then `name`, then `sub`) | Bearer JWT validated against the issuer JWKS. **Not configured** unless `STUDIO_OIDC_ISSUER` and `STUDIO_OIDC_AUDIENCE` are set |

Local-dev token default: `local-dev-token`. Multi-org lite isolates memberships; it is not SaaS security.

`/api/me` reports `auth_mode`, `sso`, `role`, and `oidc_configured` on `/api/meta`. Meta `oidc_configured` is true only when issuer **and** audience are set. An empty issuer is not a live IdP.

## App-level roles (Phase 5 bundle, Phase 9 matrix)

Seed on first boot: default org + current `STUDIO_DEFAULT_USER` as **producer**. Extra orgs created later get the creating producer as their first member.

Phase 9 maps the pack-convention roles onto these permissions. The original four roles keep their Phase 5 powers. `writer` and `art` are narrower roles you can assign when those jobs should not share the legacy editor bundle.

| Role | Legacy | Reads | Writes |
|---|---|---|---|
| `producer` | yes | yes | members, budget hard-stop / cap, retention apply, **sign-off**, generate-ok override, plus the editor bundle |
| `editor` | yes | yes | **craft bundle**: script/map/dialogue, sheets/plates/identity, joins/board/edit-list, review set, job enqueue/cancel, pack import, media, shots, comments. Not budget, retention, members, or sign-off |
| `writer` | no | yes | script, map, dialogue, episode season/sequence order, comments |
| `art` | no | yes | sheets, plates, costumes, identity approve / unapprove / keyword edit, comments |
| `reviewer` | yes | yes | comments, review set, **sign-off** |
| `viewer` | yes | yes | none (presence heartbeat only) |

`editor` is not narrowed. An existing editor can still enqueue and import packs. Assign `writer` or `art` when those permissions must differ. GPU **budget** hard-stop stays producer-only; job enqueue stays on the legacy editor bundle and on producer.

Producers manage members at `GET/POST /api/orgs/{id}/members`. Unknown names are authenticated but **not** members until a producer adds them. `GET /api/meta` includes `role_matrix`.

**App roles stay authoritative** unless the optional OIDC claim map is enabled (below). Forward-header still only supplies a name. OIDC still only supplies a name unless `STUDIO_OIDC_APPLY_ROLE_CLAIM` is true. The claim map may name `writer` or `art`; that is still an app role, not an IdP group.

## Optional OIDC (`STUDIO_AUTH_MODE=oidc`)

This process is a **resource server**. It verifies Bearer JWTs. It does not implement authorization-code login, a callback route, or a confidential client. Do not put client secrets in git. `studio/.env.example` uses empty placeholders only.

Required:

| Env | Meaning |
|---|---|
| `STUDIO_OIDC_ISSUER` | Issuer URL (must match the JWT `iss`) |
| `STUDIO_OIDC_AUDIENCE` | API audience (must match JWT `aud`) |

Optional:

| Env | Meaning |
|---|---|
| `STUDIO_OIDC_CLIENT_ID` | If set, JWT `azp` or `aud` must include this value |
| `STUDIO_OIDC_JWKS_URL` | Override JWKS URI (otherwise `{issuer}/.well-known/openid-configuration` → `jwks_uri`) |
| `STUDIO_OIDC_NAME_CLAIM` | Default `preferred_username` |
| `STUDIO_OIDC_ROLE_CLAIM` | Claim name to read (unused unless apply is on) |
| `STUDIO_OIDC_ROLE_MAP` | `claim_value:app_role` pairs, comma-separated. Example: `admin:producer,review:reviewer,script:writer,stills:art`. Unknown app roles are ignored |
| `STUDIO_OIDC_APPLY_ROLE_CLAIM` | Default `false`. When `true`, mapped claim upserts the org member role |

Install the extra: `pip install -e "./studio[oidc]"`.

Allowed JWT algs: RS256 / RS384 / RS512 / ES256 / ES384 / ES512. `none` and HMAC algs are refused.

### Wire Authentik / Keycloak / Auth0

Same shape for each. Create an API / resource in the IdP, copy the **issuer** and the **audience** (API identifier), then:

```bash
export STUDIO_AUTH_MODE=oidc
export STUDIO_OIDC_ISSUER="https://idp.example.invalid/realms/studio"
export STUDIO_OIDC_AUDIENCE="aigc-studio-api"
export STUDIO_OIDC_CLIENT_ID=""   # optional; not a secret
# Do not set a client secret here. This API does not redeem codes.
```

| Provider | Issuer | Audience |
|---|---|---|
| **Authentik** | Application provider issuer URL (often `https://<host>/application/o/<slug>/`) | The provider's audience / client id you assigned to this API |
| **Keycloak** | `https://<host>/realms/<realm>` | Client id or dedicated audience mapper for this API |
| **Auth0** | `https://<tenant>.auth0.com/` | API Identifier on the Auth0 APIs page |

Then map IdP users onto org members in the studio (producer adds `preferred_username`). Roles still live on `org_members` unless you explicitly set `STUDIO_OIDC_APPLY_ROLE_CLAIM=true` **and** a role claim map.

This file does **not** claim any of those IdPs are configured in this repo.

## Reverse-proxy SSO (forward-header)

When you want the proxy to authenticate humans and the API to trust a header:

1. Terminate TLS and authenticate at the proxy (oauth2-proxy, Authentik forward-auth, Cloud IAP, …).
2. Set `STUDIO_AUTH_MODE` to `forward-header`.
3. Have the proxy **overwrite** `X-Forwarded-User` (never pass it through from the public internet).
4. Keep the studio API off the public network except through that proxy.
5. Optionally rotate `STUDIO_API_TOKEN` and inject it only on the trusted path.
6. Map proxy names onto org members (producers still add roles in the studio).

Until that exists, use `local`. The studio shell still shows a token field and a local user field.

## What this file is not

- Not a promise that a production IdP is running
- Not a confidential-client OAuth app (no client secret, no login page)
- Not a promise that `X-Forwarded-User` is spoof-proof without a locked-down proxy
- Not multi-tenant isolation beyond membership 404s
- Not SaaS billing or SSO org mapping
