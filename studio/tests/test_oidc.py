"""Optional OIDC resource-server tests. No live IdP and no client secrets."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import reset_engine
from app.main import create_app
from app.oidc import clear_jwks_cache, parse_role_map

ISSUER = "https://idp.example.invalid/realms/studio"
AUDIENCE = "aigc-studio-api"


def _rsa_jwk():
    jwt = pytest.importorskip("jwt")
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    numbers = public.public_numbers()

    def b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return jwt.utils.base64url_encode(raw).decode("ascii")

    jwk = {
        "kty": "RSA",
        "kid": "test-key",
        "use": "sig",
        "alg": "RS256",
        "n": b64(numbers.n),
        "e": b64(numbers.e),
    }
    return private, {"keys": [jwk]}


def _token(private, *, name="oidc-user", role=None, expired=False, aud=AUDIENCE) -> str:
    jwt = pytest.importorskip("jwt")
    now = datetime.now(timezone.utc)
    payload = {
        "iss": ISSUER,
        "aud": aud,
        "iat": now,
        "exp": now + timedelta(minutes=-5 if expired else 10),
        "preferred_username": name,
        "sub": "user-1",
    }
    if role:
        payload["studio_role"] = role
    return jwt.encode(payload, private, algorithm="RS256", headers={"kid": "test-key"})


def _oidc_client(tmp_path, monkeypatch, *, apply_role=False):
    private, jwks = _rsa_jwk()
    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{tmp_path / 'oidc.db'}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STUDIO_JOB_WORKER", "off")
    monkeypatch.setenv("STUDIO_AUTH_MODE", "oidc")
    monkeypatch.setenv("STUDIO_OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("STUDIO_OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("STUDIO_OIDC_NAME_CLAIM", "preferred_username")
    monkeypatch.setenv("STUDIO_OIDC_ROLE_CLAIM", "studio_role")
    monkeypatch.setenv("STUDIO_OIDC_ROLE_MAP", "admin:producer,review:reviewer")
    monkeypatch.setenv("STUDIO_OIDC_APPLY_ROLE_CLAIM", "true" if apply_role else "false")
    monkeypatch.setattr("app.oidc.fetch_jwks", lambda _settings: jwks)
    clear_jwks_cache()
    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    return private, TestClient(create_app())


def test_parse_role_map_named_pairs():
    mapping = parse_role_map("admin:producer, review:reviewer, nonsense")
    assert mapping["admin"] == "producer"
    assert mapping["review"] == "reviewer"
    assert "nonsense" not in mapping


def test_oidc_missing_config_is_honest(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{tmp_path / 'oidc-empty.db'}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STUDIO_JOB_WORKER", "off")
    monkeypatch.setenv("STUDIO_AUTH_MODE", "oidc")
    monkeypatch.setenv("STUDIO_OIDC_ISSUER", "")
    monkeypatch.setenv("STUDIO_OIDC_AUDIENCE", "")
    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    with TestClient(create_app()) as client:
        response = client.get("/api/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert response.status_code == 401
        assert "opt-in" in response.json()["detail"]
        meta = client.get("/api/meta").json()
        assert meta["auth_mode"] == "oidc"
        assert meta["oidc_configured"] is False
        assert meta["phase"] == 8
    get_settings.cache_clear()


def test_oidc_valid_jwt_maps_name(tmp_path, monkeypatch):
    private, client = _oidc_client(tmp_path, monkeypatch)
    token = _token(private, name="ada")
    with client:
        me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, me.text
        body = me.json()
        assert body["name"] == "ada"
        assert body["auth_mode"] == "oidc"
        assert body["role"] is None
        assert "AUTH.md" in body["sso"]
        assert "opt-in" in body["sso"]
    get_settings.cache_clear()


def test_oidc_expired_jwt_is_rejected(tmp_path, monkeypatch):
    private, client = _oidc_client(tmp_path, monkeypatch)
    token = _token(private, expired=True)
    with client:
        me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 401
    get_settings.cache_clear()


def test_oidc_wrong_audience_is_rejected(tmp_path, monkeypatch):
    private, client = _oidc_client(tmp_path, monkeypatch)
    token = _token(private, aud="other-api")
    with client:
        me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 401
    get_settings.cache_clear()


def test_oidc_role_claim_is_ignored_unless_enabled(tmp_path, monkeypatch):
    private, client = _oidc_client(tmp_path, monkeypatch, apply_role=False)
    token = _token(private, name="ada", role="admin")
    with client:
        me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["role"] is None
        assert me.json()["oidc_role"] == "producer"
    get_settings.cache_clear()


def test_oidc_apply_role_claim_upserts_member(tmp_path, monkeypatch):
    private, client = _oidc_client(tmp_path, monkeypatch, apply_role=True)
    token = _token(private, name="ada", role="admin")
    with client:
        me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, me.text
        assert me.json()["role"] == "producer"
        assert "members" in me.json()["permissions"]
        projects = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"})
        assert projects.status_code == 200
    get_settings.cache_clear()


def test_local_mode_unchanged_by_oidc_settings(client, auth):
    me = client.get("/api/me", headers=auth)
    assert me.status_code == 200
    assert me.json()["auth_mode"] == "local"
    assert me.json()["role"] == "producer"
    # Keep this file free of username/password tuples that trip secret scanners.
    assert json.dumps({"mode": me.json()["auth_mode"]})
    _ = time.time()
