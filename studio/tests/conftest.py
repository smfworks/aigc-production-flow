from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import reset_engine
from app.main import create_app

TOKEN = "test-token"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "studio.db"
    media = tmp_path / "media"
    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(media))
    monkeypatch.setenv("STUDIO_API_TOKEN", TOKEN)
    monkeypatch.setenv("STUDIO_DEFAULT_USER", "tester")
    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}
