# Auth (studio spine)

This is **not** SSO and **not** an IdP integration.

Phase 4 adds a reverse-proxy hook so a later ops deploy can put Caddy/nginx/oauth2-proxy in front of the API. It does **not** implement OIDC, SAML, or a login page.

## Modes (`STUDIO_AUTH_MODE`)

| Value | Identity | API gate |
|---|---|---|
| `local` (default) | `X-User-Name` or `STUDIO_DEFAULT_USER` (`local-dev`) | Bearer `STUDIO_API_TOKEN` |
| `forward-header` | **Required** `X-Forwarded-User` (set by the reverse proxy after it authenticates the human) | Bearer token still required so scripts and the Vite shell keep working |

Local-dev token default: `local-dev-token`. Do not treat this as multi-tenant SaaS security. There is a single default organization.

## Reverse-proxy SSO later (not this PR)

When you are ready:

1. Terminate TLS and authenticate at the proxy (oauth2-proxy, Authentik, Cloud IAP, …).
2. Set `STUDIO_AUTH_MODE=forward-header`.
3. Have the proxy **overwrite** `X-Forwarded-User` (never pass it through from the public internet).
4. Keep the studio API off the public network except through that proxy.
5. Optionally rotate `STUDIO_API_TOKEN` and inject it only on the trusted path.

Until that exists, use `local`. The studio shell still shows a token field. `/api/me` reports `auth_mode` and `sso: "not implemented — see docs/AUTH.md"`.

## What this file is not

- Not OIDC discovery, JWKS, or callback routes
- Not role-based access control
- Not a promise that `X-Forwarded-User` is spoof-proof without a correctly locked-down proxy
