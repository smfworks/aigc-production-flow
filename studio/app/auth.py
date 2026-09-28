import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from .config import get_settings
from .oidc import OIDC_IDENTITY, validate_bearer
from .schemas import UserOut

LOCAL_IDENTITY = "local"
FORWARD_HEADER_IDENTITY = "forward-header"
SUPPORTED_IDENTITY_MODES = frozenset(
    {LOCAL_IDENTITY, FORWARD_HEADER_IDENTITY, OIDC_IDENTITY}
)

SSO_NOTE = "see docs/AUTH.md"


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


def _sso_note(mode: str) -> str:
    if mode == OIDC_IDENTITY:
        return (
            "oidc opt-in (JWKS). Off by default. App roles stay authoritative "
            f"unless STUDIO_OIDC_APPLY_ROLE_CLAIM is set — {SSO_NOTE}"
        )
    if mode == FORWARD_HEADER_IDENTITY:
        return f"forward-header identity. OIDC remains opt-in — {SSO_NOTE}"
    return f"local-dev token. OIDC remains opt-in and off by default — {SSO_NOTE}"


def bearer_matches(presented: str | None, expected: str) -> bool:
    """Constant-time compare. Empty tokens never match."""
    if not presented or not expected:
        return False
    try:
        return hmac.compare_digest(presented, expected)
    except (TypeError, ValueError):
        return False


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header()] = None,
    x_forwarded_user: Annotated[str | None, Header()] = None,
) -> UserOut:
    """Identity gate. Default is a Bearer token. OIDC is opt-in.

    ``STUDIO_AUTH_MODE=local`` (default): token required; display name from
    ``X-User-Name`` or ``STUDIO_DEFAULT_USER``.

    ``STUDIO_AUTH_MODE=forward-header``: token still required as an API gate;
    identity is ``X-Forwarded-User`` (reverse-proxy SSO later).

    ``STUDIO_AUTH_MODE=oidc``: Bearer JWT validated against issuer JWKS.
    Not a production IdP; not configured unless issuer + audience are set.
    """
    settings = get_settings()
    mode = _mode(settings.auth_mode)
    token = _extract_bearer(authorization)

    if mode == OIDC_IDENTITY:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "STUDIO_AUTH_MODE=oidc requires Authorization: Bearer <jwt>. "
                    f"OIDC is opt-in. {SSO_NOTE}."
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )
        name, oidc_role = validate_bearer(token, settings)
        return UserOut(
            name=name,
            auth_mode=mode,
            sso=_sso_note(mode),
            oidc_role=oidc_role,
        )

    if not bearer_matches(token, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Invalid or missing API token. "
                "Authorization: Bearer $STUDIO_API_TOKEN. "
                f"OIDC is opt-in and off by default — {SSO_NOTE}."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )
    if mode == FORWARD_HEADER_IDENTITY:
        forwarded = (x_forwarded_user or "").strip()
        if not forwarded:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "STUDIO_AUTH_MODE=forward-header requires X-Forwarded-User. "
                    "The reverse proxy must set that header after authenticating. "
                    f"OIDC is opt-in — {SSO_NOTE}."
                ),
            )
        name = forwarded
    else:
        name = (x_user_name or settings.default_user).strip() or settings.default_user
    return UserOut(name=name, auth_mode=mode, sso=_sso_note(mode))
