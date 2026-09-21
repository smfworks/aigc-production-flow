# Auth (studio spine)

This is **not** SSO and **not** an IdP integration.

Identity modes (`STUDIO_AUTH_MODE`) pick **who the process believes you are**. App-level **roles** (`producer` / `editor` / `reviewer` / `viewer`) sit on the default org after that. The IdP is still outside this repo.

Phase 4 added a reverse-proxy hook so a later ops deploy can put Caddy/nginx/oauth2-proxy in front of the API. Phase 5 did **not** implement OIDC, SAML, or a login page. Roles are stored on `org_members`, not on a JWT.

## Identity modes (`STUDIO_AUTH_MODE`)

Use the named values `local` (default) or `forward-header`. Aliases for local: `local-dev`, `token`, `bearer`.

| Value | Identity | API gate |
|---|---|---|
| `local` | `X-User-Name` or `STUDIO_DEFAULT_USER` (`local-dev`) | Bearer `STUDIO_API_TOKEN` |
| `forward-header` | **Required** `X-Forwarded-User` (set by the reverse proxy after it authenticates the human) | Bearer token still required so scripts and the Vite shell keep working |

Local-dev token default: `local-dev-token`. Do not treat this as multi-tenant SaaS security. There is a single default organization.

## App-level roles (Phase 5)

Seed on first boot: default org + current `STUDIO_DEFAULT_USER` as **producer**.

| Role | Reads | Writes |
|---|---|---|
| `producer` | yes | members, budget hard-stop / cap, retention apply, plus editor writes |
| `editor` | yes | review set, job enqueue/cancel, pack import, media upload, shots, comments |
| `reviewer` | yes | comments (create/resolve), review set |
| `viewer` | yes | none (presence heartbeat only) |

Producers manage members at `GET/POST /api/orgs/{id}/members`. `/api/me` reports `role` and `permissions`. Unknown `X-User-Name` values are authenticated (same token) but **not** members until a producer adds them.

Roles do **not** come from OIDC groups. Forward-header still only supplies a name.

## Reverse-proxy SSO later (not this PR)

When you are ready:

1. Terminate TLS and authenticate at the proxy (oauth2-proxy, Authentik, Cloud IAP, …).
2. Set `STUDIO_AUTH_MODE` to `forward-header`.
3. Have the proxy **overwrite** `X-Forwarded-User` (never pass it through from the public internet).
4. Keep the studio API off the public network except through that proxy.
5. Optionally rotate `STUDIO_API_TOKEN` and inject it only on the trusted path.
6. Map proxy names onto org members (producers still add roles in the studio).

Until that exists, use `local`. The studio shell still shows a token field and a local user field. `/api/me` reports `auth_mode` and `sso: "not implemented — see docs/AUTH.md"`.

## What this file is not

- Not OIDC discovery, JWKS, or callback routes
- Not a promise that `X-Forwarded-User` is spoof-proof without a correctly locked-down proxy
- Not multi-tenant isolation
