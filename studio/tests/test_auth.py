def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_openapi_is_public(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "AIGC Studio Spine"
    assert "/api/projects" in body["paths"]


def test_api_requires_token(client):
    response = client.get("/api/projects")
    assert response.status_code == 401


def test_wrong_token_is_rejected(client):
    response = client.get("/api/projects", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_me_and_default_org(client, auth):
    me = client.get("/api/me", headers=auth)
    assert me.status_code == 200
    assert me.json()["auth_mode"] == "local"
    assert me.json()["role"] == "producer"
    assert "jobs" in me.json()["permissions"]
    assert "AUTH.md" in me.json()["sso"]
    orgs = client.get("/api/orgs", headers=auth)
    assert orgs.status_code == 200
    assert len(orgs.json()) == 1
    assert "local" in orgs.json()[0]["name"].lower()


def test_forward_header_mode(tmp_path, monkeypatch, auth):
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.database import reset_engine
    from app.main import create_app

    db_path = tmp_path / "fwd.db"
    media = tmp_path / "media"
    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(media))
    monkeypatch.setenv("STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("STUDIO_AUTH_MODE", "forward-header")
    monkeypatch.setenv("STUDIO_JOB_WORKER", "off")
    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    app = create_app()
    with TestClient(app) as client:
        missing = client.get("/api/me", headers=auth)
        assert missing.status_code == 401
        ok = client.get(
            "/api/me",
            headers={**auth, "X-Forwarded-User": "proxy-user"},
        )
        assert ok.status_code == 200
        assert ok.json()["name"] == "proxy-user"
        assert ok.json()["auth_mode"] == "forward-header"
        assert ok.json()["role"] is None
        assert "AUTH.md" in ok.json()["sso"]
        meta = client.get("/api/meta")
        assert meta.status_code == 200
        assert meta.json()["auth_mode"] == "forward-header"
        assert meta.json()["phase"] == 9
        assert meta.json()["media_backend"] == "local"
    del Path
