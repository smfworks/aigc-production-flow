from typing import Annotated

from fastapi import Header, HTTPException, status

from .config import get_settings
from .schemas import UserOut


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header()] = None,
) -> UserOut:
    """Local-dev token gate. This is not SSO and not multi-tenant isolation."""
    settings = get_settings()
    token = _extract_bearer(authorization)
    if token != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Invalid or missing API token. Local-dev auth: "
                "Authorization: Bearer $STUDIO_API_TOKEN (default local-dev-token). "
                "SSO is not in this phase."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )
    name = (x_user_name or settings.default_user).strip() or settings.default_user
    return UserOut(name=name)
