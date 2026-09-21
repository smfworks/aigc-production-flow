"""Celery path: mocked by default; live Redis skipped unless a broker is up."""

from __future__ import annotations

import os

import pytest

from tests.helpers import green_ready_episode


def _broker_up() -> bool:
    url = (os.environ.get("STUDIO_CELERY_BROKER_URL") or os.environ.get("REDIS_URL") or "").strip()
    if not url:
        return False
    try:
        import redis

        redis.from_url(url).ping()
    except Exception:
        return False
    return True


def test_celery_enqueue_dispatches_same_job_row(tmp_path, monkeypatch, auth):
    dispatched: list[str] = []

    def fake_send(job_id: str) -> None:
        dispatched.append(job_id)

    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{tmp_path / 'celery.db'}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("STUDIO_DEFAULT_USER", "tester")
    monkeypatch.setenv("STUDIO_JOB_WORKER", "celery")
    monkeypatch.setenv("STUDIO_CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("STUDIO_STILL_ADAPTER", "stub")
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "stub")
    monkeypatch.setattr("app.jobs.celery_app.send_execute_job", fake_send)

    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.database import reset_engine
    from app.main import create_app

    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    with TestClient(create_app()) as client:
        _, episode, _ = green_ready_episode(client, auth, "Celery mock")
        response = client.post(
            "/api/jobs",
            headers=auth,
            json={"episode_id": episode["id"], "job_type": "batch-precheck"},
        )
        assert response.status_code == 201, response.text
        job = response.json()
        assert job["status"] == "queued"
        assert dispatched == [job["id"]]
        meta = client.get("/api/meta").json()
        assert meta["job_worker"] == "celery"
        assert meta["celery_enabled"] is True
    get_settings.cache_clear()


def test_celery_dispatch_failure_is_honest(tmp_path, monkeypatch, auth):
    def boom(_job_id: str) -> None:
        raise RuntimeError("broker down")

    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{tmp_path / 'celery-fail.db'}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("STUDIO_DEFAULT_USER", "tester")
    monkeypatch.setenv("STUDIO_JOB_WORKER", "celery")
    monkeypatch.setenv("STUDIO_CELERY_BROKER_URL", "redis://localhost:6379/0")
    monkeypatch.setattr("app.jobs.celery_app.send_execute_job", boom)

    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.database import reset_engine
    from app.main import create_app

    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    with TestClient(create_app()) as client:
        _, episode, _ = green_ready_episode(client, auth, "Celery down")
        response = client.post(
            "/api/jobs",
            headers=auth,
            json={"episode_id": episode["id"], "job_type": "batch-precheck"},
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "celery_unavailable"
    get_settings.cache_clear()


@pytest.mark.skipif(not _broker_up(), reason="Redis broker not available; Celery is opt-in")
def test_celery_task_executes_job_row_when_redis_available(tmp_path, monkeypatch, auth):
    from app.jobs.celery_app import send_execute_job
    from app.jobs.runner import execute_job
    from tests.helpers import wait_job

    monkeypatch.setenv("STUDIO_DATABASE_URL", f"sqlite:///{tmp_path / 'celery-live.db'}")
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STUDIO_API_TOKEN", "test-token")
    monkeypatch.setenv("STUDIO_DEFAULT_USER", "tester")
    monkeypatch.setenv("STUDIO_JOB_WORKER", "off")
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.database import reset_engine
    from app.main import create_app

    get_settings.cache_clear()
    reset_engine(get_settings().database_url)
    with TestClient(create_app()) as client:
        _, episode, _ = green_ready_episode(client, auth, "Celery live")
        response = client.post(
            "/api/jobs",
            headers=auth,
            json={"episode_id": episode["id"], "job_type": "batch-precheck"},
        )
        assert response.status_code == 201
        job_id = response.json()["id"]
        assert response.json()["status"] == "queued"
        execute_job(None, job_id)
        finished = wait_job(client, auth, job_id)
        assert finished["status"] == "succeeded"
        _ = send_execute_job
    get_settings.cache_clear()
