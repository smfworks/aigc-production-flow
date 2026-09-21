from typing import Annotated

from fastapi import Header, HTTPException, status

from .config import get_settings
from .schemas import UserOut

LOCAL_IDENTITY = "local"
FORWARD_HEADER_IDENTITY = "forward-header"
SUPPORTED_IDENTITY_MODES = frozenset({LOCAL_IDENTITY, FORWARD_HEADER_IDENTITY})


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _mode(raw: str | None) -> str:
    value = (raw or LOCAL_IDENTITY).strip().lower()
    if value in {"local-dev", "token", "bearer"}:
        return LOCAL_IDENTITY
    return value if value in SUPPORTED_IDENTITY_MODES else LOCAL_IDENTITY


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header()] = None,
    x_forwarded_user: Annotated[str | None, Header()] = None,
) -> UserOut:
    """Bearer token gate plus optional reverse-proxy identity.

    ``STUDIO_AUTH_MODE=local`` (default): token required; display name from
    ``X-User-Name`` or ``STUDIO_DEFAULT_USER``.

    ``STUDIO_AUTH_MODE=forward-header``: token still required as an API gate;
    identity is ``X-Forwarded-User`` (reverse-proxy SSO later). No OIDC in this
    phase — see docs/AUTH.md.
    """
    settings = get_settings()
    mode = _mode(settings.auth_mode)
    token = _extract_bearer(authorization)
    if token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Invalid or missing API token. Local-dev auth: "
                "Authorization: Bearer $STUDIO_API_TOKEN (default local-dev-token). "
                "SSO is not implemented — see docs/AUTH.md."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )
    if mode == "forward-header":
        forwarded = (x_forwarded_user or "").strip()
        if not forwarded:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "STUDIO_AUTH_MODE=forward-header requires X-Forwarded-User. "
                    "The reverse proxy must set that header after authenticating. "
                    "OIDC is not implemented — see docs/AUTH.md."
                ),
            )
        name = forwarded
    else:
        name = (x_user_name or settings.default_user).strip() or settings.default_user
    return UserOut(name=name, auth_mode=mode, sso="not implemented — see docs/AUTH.md")
