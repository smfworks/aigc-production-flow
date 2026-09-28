"""Token generation, the retired default, and the listen address."""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

import pytest

from app.auth import bearer_matches
from app.config import get_settings
from app.main import create_app
from app.runtime_security import (
    RETIRED_API_TOKEN,
    StudioStartupError,
    is_loopback_host,
    token_source,
)

ROOT = Path(__file__).resolve().parents[2]


def _prepare(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str) -> Path:
    token_path = tmp_path / "studio.api-token"
    monkeypatch.delenv("STUDIO_API_TOKEN", raising=False)
    monkeypatch.setenv("STUDIO_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("STUDIO_ALLOW_NON_LOOPBACK", "0")
    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{tmp_path / 'studio.db'}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STUDIO_TOKEN_FILE", str(token_path))
    monkeypatch.setenv("STUDIO_JOB_WORKER", "off")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    return token_path


@pytest.fixture
def token_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = _prepare(monkeypatch, tmp_path)
    yield path
    get_settings.cache_clear()


def test_loopback_hosts():
    assert is_loopback_host("127.0.0.1") is True
    assert is_loopback_host("localhost") is True
    assert is_loopback_host("::1") is True
    assert is_loopback_host("::ffff:127.0.0.1") is True
    assert is_loopback_host("0.0.0.0") is False
    assert is_loopback_host("::") is False
    assert is_loopback_host("10.1.2.3") is False
    assert is_loopback_host("") is False
    assert is_loopback_host(None) is False


def test_missing_token_is_generated_and_persisted(token_path: Path):
    settings = get_settings()
    assert settings.api_token
    assert settings.api_token != RETIRED_API_TOKEN
    assert len(settings.api_token) >= 32
    assert token_source(settings) == "generated"
    assert token_path.is_file()
    assert not token_path.is_symlink()
    mode = stat.S_IMODE(token_path.stat().st_mode)
    assert mode == 0o600
    assert stat.S_ISREG(token_path.stat().st_mode)
    get_settings.cache_clear()
    again = get_settings()
    assert again.api_token == settings.api_token
    assert token_source(again) == "file"
    assert token_path.read_text(encoding="utf-8").strip() == settings.api_token


def test_loose_token_file_is_tightened(token_path: Path):
    token_path.write_text("operator-file-token\n", encoding="utf-8")
    os.chmod(token_path, 0o644)
    settings = get_settings()
    assert settings.api_token == "operator-file-token"
    assert token_source(settings) == "file"
    assert stat.S_IMODE(token_path.stat().st_mode) == 0o600


def test_environment_token_is_not_written(token_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_API_TOKEN", "from-the-environment")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.api_token == "from-the-environment"
    assert token_source(settings) == "env"
    assert not token_path.exists()


def test_retired_environment_token_refuses_start(
    token_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STUDIO_API_TOKEN", RETIRED_API_TOKEN)
    get_settings.cache_clear()
    with pytest.raises(StudioStartupError, match="local-dev-token"):
        create_app()
    assert not token_path.exists()


def test_retired_token_file_refuses_start(token_path: Path):
    token_path.write_text(RETIRED_API_TOKEN + "\n", encoding="utf-8")
    os.chmod(token_path, 0o600)
    with pytest.raises(StudioStartupError, match="local-dev-token"):
        get_settings()


def test_symlink_token_file_is_not_followed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    secret = tmp_path / "elsewhere"
    secret.write_text("other-secret\n", encoding="utf-8")
    link = tmp_path / "studio.api-token"
    link.symlink_to(secret)
    _prepare(monkeypatch, tmp_path)
    with pytest.raises(StudioStartupError, match="symlink"):
        get_settings()
    assert secret.read_text(encoding="utf-8") == "other-secret\n"


def test_default_bind_is_loopback(token_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("STUDIO_BIND_HOST", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.bind_host == "127.0.0.1"


def test_non_loopback_without_opt_in_refuses(token_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STUDIO_API_TOKEN", "configured-token")
    monkeypatch.setenv("STUDIO_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("STUDIO_ALLOW_NON_LOOPBACK", "0")
    get_settings.cache_clear()
    with pytest.raises(StudioStartupError, match="STUDIO_ALLOW_NON_LOOPBACK"):
        get_settings()


def test_non_loopback_with_only_a_generated_token_refuses(
    token_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STUDIO_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("STUDIO_ALLOW_NON_LOOPBACK", "1")
    get_settings.cache_clear()
    with pytest.raises(StudioStartupError, match="STUDIO_API_TOKEN"):
        get_settings()
    assert not token_path.exists()
    get_settings.cache_clear()
    monkeypatch.setenv("STUDIO_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("STUDIO_ALLOW_NON_LOOPBACK", "0")
    settings = get_settings()
    assert token_source(settings) in {"generated", "file"}
    assert settings.bind_host == "127.0.0.1"


def test_non_loopback_requires_opt_in_and_configured_token(
    token_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STUDIO_API_TOKEN", "configured-token")
    monkeypatch.setenv("STUDIO_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("STUDIO_ALLOW_NON_LOOPBACK", "1")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.bind_host == "0.0.0.0"
    assert settings.api_token == "configured-token"
    assert token_source(settings) == "env"


def test_bearer_match_uses_compare_digest(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, tuple[str, str]] = {}

    def fake(left: str, right: str) -> bool:
        seen["pair"] = (left, right)
        return left == right

    monkeypatch.setattr("app.auth.hmac.compare_digest", fake)
    assert bearer_matches("alpha", "alpha") is True
    assert seen["pair"] == ("alpha", "alpha")
    assert bearer_matches("", "alpha") is False
    assert bearer_matches(None, "alpha") is False
    assert bearer_matches("alpha", "") is False


def test_unauthorized_body_does_not_name_the_retired_token(client):
    response = client.get("/api/me")
    assert response.status_code == 401
    assert RETIRED_API_TOKEN not in response.text


def test_bearer_prefix_is_rejected(client):
    response = client.get(
        "/api/projects",
        headers={"Authorization": "Bearer test-token-extra"},
    )
    assert response.status_code == 401


def test_local_token_route_is_gone(client):
    response = client.get("/api/local-token")
    assert response.status_code == 404
    assert "test-token" not in response.text
    body = client.get("/openapi.json").json()
    assert "/api/local-token" not in body["paths"]


def _status(app, host: str | None, path: str = "/health") -> tuple[int, bytes]:
    status = 0
    chunks: list[bytes] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status
        if message["type"] == "http.response.start":
            status = int(message["status"])
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body") or b"")

    headers: list[tuple[bytes, bytes]] = []
    if host is not None:
        headers.append((b"host", host.encode("ascii")))
    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.3", "version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
        "root_path": "",
    }

    async def call():
        await app(scope, receive, send)

    asyncio.run(call())
    return status, b"".join(chunks)


def test_trusted_host_allows_loopback_names_only(client):
    app = client.app
    for host in ("127.0.0.1", "127.0.0.1:8000", "localhost", "[::1]", "[::1]:8000"):
        status, body = _status(app, host)
        assert status == 200, host
        assert b"Invalid host header" not in body
    for host in ("evil.example", "10.1.2.3", "studio-api", None):
        status, body = _status(app, host)
        assert status == 400, host
        assert b"Invalid host header" in body
        assert b"test-token" not in body


def test_trusted_host_accepts_configured_names(
    token_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STUDIO_API_TOKEN", "configured-host-token")
    monkeypatch.setenv("STUDIO_TRUSTED_HOSTS", "studio.internal, ::1")
    get_settings.cache_clear()
    app = create_app()
    status, body = _status(app, "studio.internal")
    assert status == 200
    assert b"configured-host-token" not in body
    status, _body = _status(app, "[::1]")
    assert status == 200
    status, body = _status(app, "other.example")
    assert status == 400
    assert b"configured-host-token" not in body


def test_trusted_host_rejects_a_wildcard(
    token_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STUDIO_API_TOKEN", "wildcard-token")
    monkeypatch.setenv("STUDIO_TRUSTED_HOSTS", "*")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="cannot be"):
        create_app()


def test_print_token_path_does_not_echo_the_secret(
    token_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    import sys

    from app.print_token import main

    monkeypatch.delenv("STUDIO_API_TOKEN", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(sys, "argv", ["print_token", "--path"])
    main()
    secret = get_settings().api_token
    out = capsys.readouterr().out
    assert str(token_path) in out
    assert secret not in out

    monkeypatch.setenv("STUDIO_API_TOKEN", "chosen-secret-value")
    get_settings.cache_clear()
    main()
    out = capsys.readouterr().out
    assert "chosen-secret-value" not in out
    assert "STUDIO_API_TOKEN is set" in out


def test_serve_uses_the_resolved_loopback_host(
    token_path: Path, monkeypatch: pytest.MonkeyPatch
):
    captured: dict[str, object] = {}

    def fake_run(*_args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("app.serve.uvicorn.run", fake_run)
    from app.serve import main

    main()
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8000


def test_serve_refuses_non_loopback_without_a_configured_token(
    token_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("STUDIO_BIND_HOST", "0.0.0.0")
    get_settings.cache_clear()
    from app.serve import main

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_shipped_entrypoints_do_not_bake_the_retired_token():
    dockerfile = (ROOT / "studio" / "Dockerfile").read_text(encoding="utf-8")
    assert "local-dev-token" not in dockerfile
    assert "0.0.0.0" not in dockerfile
    assert "app.serve" in dockerfile
    assert "ENV STUDIO_API_TOKEN" not in dockerfile

    script = (ROOT / "scripts" / "dev-studio.sh").read_text(encoding="utf-8")
    assert "local-dev-token" not in script
    assert "0.0.0.0" not in script
    assert "app.serve" in script
    assert "app.print_token" in script
    assert "--path" in script
    assert 'echo "Token       ${token}"' not in script
    assert 'echo "Token   ${token}"' not in script
    assert "Token file  $(token_location)" in script

    for name in ("docker-compose.yml", "docker-compose.studio.yml"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "local-dev-token" not in text
        assert "127.0.0.1:8000:8000" in text
        assert '- "8000:8000"' not in text
        assert "STUDIO_ALLOW_NON_LOOPBACK" in text
        assert "STUDIO_API_TOKEN:?" in text

    studio_compose = (ROOT / "docker-compose.studio.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:5174:80" in studio_compose
    assert '- "5174:80"' not in studio_compose

    example = (ROOT / "studio" / ".env.example").read_text(encoding="utf-8")
    assert "STUDIO_API_TOKEN=local-dev-token" not in example

    nginx = (ROOT / "studio-web" / "nginx.conf").read_text(encoding="utf-8")
    assert "$http_x_forwarded_user" not in nginx
    assert "$http_x_user_name" not in nginx
    assert "$http_authorization" not in nginx
    assert 'proxy_set_header X-Forwarded-User "";' in nginx
    assert 'proxy_set_header X-User-Name "";' in nginx
    assert "return 444;" in nginx
    assert "default_server" in nginx
    assert "server_name 127.0.0.1 localhost [::1];" in nginx
    assert "studio-auth.conf" in nginx
    assert "studio-token.js" not in nginx

    entry = (ROOT / "studio-web" / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "local-dev-token" not in entry
    assert "STUDIO_API_TOKEN" in entry
    assert "studio-token.js" not in entry
    assert "window.__STUDIO_TOKEN__" not in entry
    assert "/usr/share/nginx/html" not in entry
    assert "studio-auth.conf" in entry

    index = (ROOT / "studio-web" / "index.html").read_text(encoding="utf-8")
    assert "studio-token.js" not in index
    assert not (ROOT / "studio-web" / "public" / "studio-token.js").exists()
