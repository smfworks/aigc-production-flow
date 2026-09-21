from app.adapters.health import catalog_health, health_for, slot_health
from app.adapters.catalog import SLOT_BY_ID, STUB_NAME
from app.config import get_settings


def test_stub_health_always_ok():
    report = health_for(STUB_NAME)
    assert report["ok"] is True
    assert report["live"] is False
    assert report["config_present"] is True
    assert "stub" in report["detail"].lower()


def test_webhook_unset_is_unhealthy_not_stub_fallback_claim(monkeypatch):
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "")
    monkeypatch.setenv("STUDIO_ADAPTER_CLI", "")
    get_settings.cache_clear()
    report = slot_health(SLOT_BY_ID["webhook"], get_settings())
    assert report["ok"] is False
    assert report["live"] is True
    assert report["config_present"] is False
    assert report["reachable"] is None
    get_settings.cache_clear()


def test_catalog_health_endpoint(client, auth):
    listed = client.get("/api/adapters", headers=auth)
    assert listed.status_code == 200
    body = listed.json()
    assert body["health"]
    stub = next(row for row in body["health"] if row["id"] == "stub")
    assert stub["ok"] is True
    live = [row for row in body["health"] if row["live"]]
    assert live
    assert all(row["ok"] is False for row in live)

    one = client.get("/api/adapters/comfy-h3/health", headers=auth)
    assert one.status_code == 200
    assert one.json()["ok"] is False
    dry = client.post("/api/adapters/cli/dry-run", headers=auth)
    assert dry.status_code == 200
    assert dry.json()["id"] == "cli"
    missing = client.get("/api/adapters/not-a-slot/health", headers=auth)
    assert missing.status_code == 404


def test_configured_webhook_unreachable_blocks_enqueue(client, auth, monkeypatch):
    from tests.helpers import green_ready_episode

    monkeypatch.setenv("STUDIO_STILL_ADAPTER", "webhook")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "http://127.0.0.1:1/hook")
    get_settings.cache_clear()
    _, episode, _ = green_ready_episode(client, auth, "Unhealthy adapter")
    blocked = client.post(
        "/api/jobs",
        headers=auth,
        json={
            "episode_id": episode["id"],
            "job_type": "still-sheet",
            "adapter": "webhook",
        },
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "adapter_unhealthy"
    get_settings.cache_clear()


def test_catalog_health_helper_matches_slots():
    rows = catalog_health()
    ids = {row["id"] for row in rows}
    assert ids == {"stub", "comfy-h3", "comfy-qwen", "webhook", "cli"}
