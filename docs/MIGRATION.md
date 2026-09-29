# Migration

Studio no longer ships a default API token, no longer listens on every interface, and no longer hands the token to whoever can open a local URL.

## Old `.env` with `local-dev-token`

If `STUDIO_API_TOKEN=local-dev-token` is still in `.env`, the shell, or `data/studio.api-token`, the API refuses to start.

- Remove that line to generate a new token on the next loopback start, or set a new secret.
- Delete `data/studio.api-token` when startup says that file holds the retired value.
- Do not copy the old value into `VITE_API_TOKEN` or `VITE_STUDIO_TOKEN`.

## Docker Compose

`STUDIO_API_TOKEN` is required. Compose will not start without it. The image and the compose file do not contain a token.

```bash
export STUDIO_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose -f docker-compose.studio.yml up --build
```

Host ports are `127.0.0.1:8000` and `127.0.0.1:5174`. The web container does not write `studio-token.js`. Nginx adds `Authorization` on `/api` only when `Host` is `127.0.0.1`, `localhost`, or `[::1]`. Any other Host hits a default server that returns `444`. Nginx clears `X-User-Name` and `X-Forwarded-User`, so the compose shell acts as `STUDIO_DEFAULT_USER`.

The token must not contain `$`, quotes, spaces, `#`, `;`, braces, or backticks. `secrets.token_urlsafe` is safe to embed.

## Vite shells and the pack builder

`./scripts/dev-studio.sh` passes the token to Vite as `VITE_API_TOKEN` and `VITE_STUDIO_TOKEN`. It prints the token file path, not the token.

A manual `npm run dev` does not. Paste the token from `data/studio.api-token` into the studio shell token field, and set `VITE_STUDIO_TOKEN` to that same value for the pack builder. The builder does not call `GET /api/local-token` (that route is gone). `URL.hostname` for IPv6 loopback is `[::1]`.

## Scripts and automations

Replace `Authorization: Bearer local-dev-token` with the generated or configured token. Call `127.0.0.1`, not a LAN address, unless you set `STUDIO_ALLOW_NON_LOOPBACK=1` and `STUDIO_API_TOKEN`. A `Host` other than `127.0.0.1`, `localhost`, `[::1]`, or a name in `STUDIO_TRUSTED_HOSTS` is rejected.
