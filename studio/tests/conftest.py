import os
from pathlib import Path

# Pin the listen address before importing the app. Importing app.main builds
# the ASGI app and resolves the API token. An ambient non-loopback bind, or
# the retired token, would refuse that import.
os.environ["STUDIO_BIND_HOST"] = "127.0.0.1"
os.environ["STUDIO_ALLOW_NON_LOOPBACK"] = "0"
if os.environ.get("STUDIO_API_TOKEN") == "local-dev-token":
    del os.environ["STUDIO_API_TOKEN"]

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
    monkeypatch.setenv("STUDIO_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("STUDIO_ALLOW_NON_LOOPBACK", "0")
    monkeypatch.setenv("STUDIO_DEFAULT_USER", "tester")
    monkeypatch.setenv("STUDIO_JOB_WORKER", worker)
    monkeypatch.setenv("STUDIO_JOB_POLL_SECONDS", "0.05")
    monkeypatch.setenv("STUDIO_STILL_ADAPTER", "stub")
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "stub")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "")
    monkeypatch.setenv("STUDIO_ADAPTER_CLI", "")
    monkeypatch.setenv("STUDIO_COMFY_STILL_LANES", "")
    monkeypatch.setenv("STUDIO_COMFY_CLIP_LANES", "")
    monkeypatch.setenv("STUDIO_COMFY_IMAGE_LANES_FOR_FREE", "")
    monkeypatch.setenv("STUDIO_COMFY_ALLOW_HOSTS", "")
    monkeypatch.setenv("STUDIO_COMFY_H3_STYLES", "")
    monkeypatch.setenv("STUDIO_REQUIRE_PROMPT_PREVIEW", "false")
    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    app = create_app()
    # Host must be a loopback name. TestClient's default host is testserver.
    return TestClient(app, base_url="http://127.0.0.1")


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
