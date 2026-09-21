"""Optional OIDC resource-server validation. Off by default.

This process verifies Bearer JWTs against the issuer JWKS. It is not a login
page, not a confidential client, and it does not ship a production IdP.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException, status

from .config import Settings
from .models import ORG_ROLES

log = logging.getLogger("aigc.studio.oidc")

OIDC_IDENTITY = "oidc"
JWKS_TTL_SECONDS = 300
NAME_CLAIM_FALLBACKS = ("preferred_username", "email", "name", "sub")
ALLOWED_ALGS = frozenset({"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"})

_jwks_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def oidc_configured(settings: Settings) -> bool:
    return bool((settings.oidc_issuer or "").strip() and (settings.oidc_audience or "").strip())


def parse_role_map(raw: str | None) -> dict[str, str]:
    """Parse STUDIO_OIDC_ROLE_MAP as claim_value:app_role pairs.

    App roles stay authoritative unless STUDIO_OIDC_APPLY_ROLE_CLAIM is set.
    """
    mapping: dict[str, str] = {}
    for chunk in (raw or "").split(","):
        piece = chunk.strip()
        if not piece or ":" not in piece:
            continue
        claim_value, _, role = piece.partition(":")
        key = claim_value.strip().lower()
        value = role.strip().lower()
        if key and value in ORG_ROLES:
            mapping[key] = value
    return mapping


def _http_json(url: str, timeout: float = 8.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "aigc-studio-oidc/0.6"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"OIDC discovery/JWKS fetch failed for {url}: {exc}. "
                "OIDC is opt-in. Local-dev remains STUDIO_AUTH_MODE=local. "
                "See docs/AUTH.md."
            ),
        ) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OIDC endpoint {url} did not return JSON. See docs/AUTH.md.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OIDC endpoint {url} returned a non-object. See docs/AUTH.md.",
        )
    return payload


def discovery_url(issuer: str) -> str:
    base = issuer.rstrip("/")
    return f"{base}/.well-known/openid-configuration"


def fetch_jwks(settings: Settings) -> dict[str, Any]:
    explicit = (settings.oidc_jwks_url or "").strip()
    issuer = (settings.oidc_issuer or "").strip()
    cache_key = explicit or issuer
    now = time.time()
    cached = _jwks_cache.get(cache_key)
    if cached and cached[0] > now:
        return cached[1]
    if explicit:
        jwks = _http_json(explicit)
    else:
        discovered = _http_json(discovery_url(issuer))
        jwks_uri = str(discovered.get("jwks_uri") or "").strip()
        if not jwks_uri:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "OIDC discovery document has no jwks_uri. "
                    "Set STUDIO_OIDC_JWKS_URL or fix the issuer. See docs/AUTH.md."
                ),
            )
        jwks = _http_json(jwks_uri)
    _jwks_cache[cache_key] = (now + JWKS_TTL_SECONDS, jwks)
    return jwks


def clear_jwks_cache() -> None:
    _jwks_cache.clear()


def _jwt():
    try:
        import jwt
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OIDC extra is not installed. pip install -e './studio[oidc]'. "
                "Default auth remains local. See docs/AUTH.md."
            ),
        ) from exc
    return jwt


def _signing_key(jwt_mod, token: str, jwks: dict[str, Any]):
    try:
        header = jwt_mod.get_unverified_header(token)
    except jwt_mod.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OIDC Bearer JWT header. See docs/AUTH.md.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    kid = str(header.get("kid") or "")
    alg = str(header.get("alg") or "")
    if alg not in ALLOWED_ALGS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OIDC JWT alg {alg or '(missing)'} is not allowed. See docs/AUTH.md.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    keys = jwks.get("keys") if isinstance(jwks.get("keys"), list) else []
    match = None
    for key in keys:
        if not isinstance(key, dict):
            continue
        if kid and key.get("kid") == kid:
            match = key
            break
        if not kid and key.get("alg") == alg:
            match = key
            break
    if match is None and len(keys) == 1 and isinstance(keys[0], dict):
        match = keys[0]
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC JWT kid did not match issuer JWKS. See docs/AUTH.md.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return jwt_mod.algorithms.RSAAlgorithm.from_jwk(json.dumps(match))
    except Exception as exc:  # noqa: BLE001
        try:
            return jwt_mod.algorithms.ECAlgorithm.from_jwk(json.dumps(match))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="OIDC JWKS key could not be parsed. See docs/AUTH.md.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc


def display_name(claims: dict[str, Any], settings: Settings) -> str:
    preferred = (settings.oidc_name_claim or "").strip()
    order = (preferred, *NAME_CLAIM_FALLBACKS) if preferred else NAME_CLAIM_FALLBACKS
    seen: set[str] = set()
    for key in order:
        if not key or key in seen:
            continue
        seen.add(key)
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "OIDC token has no usable name claim "
            f"(tried {', '.join(order)}). See docs/AUTH.md."
        ),
        headers={"WWW-Authenticate": "Bearer"},
    )


def mapped_role(claims: dict[str, Any], settings: Settings) -> str | None:
    claim_name = (settings.oidc_role_claim or "").strip()
    if not claim_name:
        return None
    raw = claims.get(claim_name)
    values: list[str] = []
    if isinstance(raw, str) and raw.strip():
        values = [raw.strip()]
    elif isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
    mapping = parse_role_map(settings.oidc_role_map)
    for value in values:
        mapped = mapping.get(value.lower())
        if mapped:
            return mapped
        if value.lower() in ORG_ROLES:
            return value.lower()
    return None


def _audience_ok(claims: dict[str, Any], audience: str, client_id: str) -> bool:
    aud = claims.get("aud")
    expected = audience.strip()
    values = [aud] if isinstance(aud, str) else list(aud or [])
    texts = [str(item) for item in values]
    if expected and expected not in texts:
        return False
    client = client_id.strip()
    if not client:
        return True
    azp = str(claims.get("azp") or "")
    if azp and azp == client:
        return True
    return client in texts


def validate_bearer(token: str, settings: Settings) -> tuple[str, str | None]:
    """Return (display_name, optional mapped role). Raises HTTPException on failure."""
    if not oidc_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "STUDIO_AUTH_MODE=oidc requires STUDIO_OIDC_ISSUER and "
                "STUDIO_OIDC_AUDIENCE. OIDC is opt-in and off by default. "
                "This process is not a production IdP. See docs/AUTH.md."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )
    jwt_mod = _jwt()
    jwks = fetch_jwks(settings)
    key = _signing_key(jwt_mod, token, jwks)
    issuer = settings.oidc_issuer.strip()
    audience = settings.oidc_audience.strip()
    try:
        claims = jwt_mod.decode(
            token,
            key=key,
            algorithms=sorted(ALLOWED_ALGS),
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except jwt_mod.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC JWT expired. See docs/AUTH.md.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt_mod.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OIDC JWT rejected: {exc}. See docs/AUTH.md.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if not isinstance(claims, dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC JWT claims are not an object. See docs/AUTH.md.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not _audience_ok(claims, audience, settings.oidc_client_id or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC JWT audience/client id did not match. See docs/AUTH.md.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return display_name(claims, settings), mapped_role(claims, settings)
