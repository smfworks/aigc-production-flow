from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import reset_engine
from app.main import create_app

TOKEN = "test-token"


def _build_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, worker: str) -> TestClient:
    db_path = tmp_path / "studio.db"
    media = tmp_path / "media"
    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(media))
    monkeypatch.setenv("STUDIO_API_TOKEN", TOKEN)
    monkeypatch.setenv("STUDIO_DEFAULT_USER", "tester")
    monkeypatch.setenv("STUDIO_JOB_WORKER", worker)
    monkeypatch.setenv("STUDIO_JOB_POLL_SECONDS", "0.05")
    monkeypatch.setenv("STUDIO_STILL_ADAPTER", "stub")
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "stub")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "")
    monkeypatch.setenv("STUDIO_ADAPTER_CLI", "")
    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    app = create_app()
    return TestClient(app)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_client = _build_client(tmp_path, monkeypatch, "inline")
    with test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def queued_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_client = _build_client(tmp_path, monkeypatch, "off")
    with test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def thread_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_client = _build_client(tmp_path, monkeypatch, "thread")
    with test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}
