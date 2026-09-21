from pathlib import Path

from app.config import get_settings
from app.store import BACKEND_LOCAL, LocalMediaStore, active_backend, media_note, requested_backend
from tests.helpers import create_episode


def test_meta_media_backend_is_local_by_default(client, auth):
    meta = client.get("/api/meta")
    assert meta.status_code == 200
    body = meta.json()
    assert body["media_backend"] == BACKEND_LOCAL
    assert body["media_s3_configured"] is False
    assert "S3" in body["media_note"] or "local" in body["media_note"].lower()


def test_s3_without_bucket_stays_local(tmp_path, monkeypatch, auth):
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.database import reset_engine
    from app.main import create_app

    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{tmp_path / 'studio.db'}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("STUDIO_DEFAULT_USER", "tester")
    monkeypatch.setenv("STUDIO_JOB_WORKER", "off")
    monkeypatch.setenv("STUDIO_MEDIA_BACKEND", "s3")
    monkeypatch.setenv("STUDIO_S3_BUCKET", "")
    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    app = create_app()
    with TestClient(app) as client:
        meta = client.get("/api/meta")
        assert meta.status_code == 200
        assert meta.json()["media_backend"] == BACKEND_LOCAL
        assert meta.json()["media_s3_configured"] is False
        assert "not live" in meta.json()["media_note"].lower() or "unset" in meta.json()["media_note"].lower()
        assert requested_backend(get_settings()) == "s3"
        assert active_backend(get_settings()) == BACKEND_LOCAL
    get_settings.cache_clear()


def test_local_store_put_get_roundtrip(tmp_path):
    store = LocalMediaStore(tmp_path / "media")
    store.put("ep/assets/hello.txt", b"hello")
    assert store.exists("ep/assets/hello.txt")
    assert store.get_bytes("ep/assets/hello.txt") == b"hello"
    assert store.local_path("ep/assets/hello.txt") == (tmp_path / "media" / "ep" / "assets" / "hello.txt")
    store.delete("ep/assets/hello.txt")
    assert not store.exists("ep/assets/hello.txt")


def test_upload_goes_through_local_adapter(client, auth, tmp_path):
    _, episode = create_episode(client, auth, "Local store")
    uploaded = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "other"},
        files={"file": ("note.txt", b"adapter-local", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    asset = uploaded.json()
    downloaded = client.get(f"/api/media/{asset['id']}", headers=auth)
    assert downloaded.status_code == 200
    assert downloaded.content == b"adapter-local"
    root = Path(get_settings().media_root)
    assert (root / asset["path"]).is_file()


def test_media_note_never_claims_s3_when_local():
    note = media_note()
    assert "not live" in note.lower() or "local disk" in note.lower()
