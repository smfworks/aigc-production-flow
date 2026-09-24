from app.adapters.health import catalog_health, health_for, slot_health, validate_slot_config
from app.adapters.catalog import SLOT_BY_ID, STUB_NAME, hop1_watch_required
from app.config import get_settings
from tests.helpers import attach_watched_receipt, green_ready_episode, sign_off


def test_stub_health_always_ok():
    report = health_for(STUB_NAME)
    assert report["ok"] is True
    assert report["live"] is False
    assert report["not_live"] is True
    assert report["config_present"] is True
    assert report["hop1_watch_required"] is True
    assert "stub" in report["detail"].lower()


def test_comfy_slots_declare_measured_window_and_are_not_live_when_unset(monkeypatch):
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "")
    monkeypatch.setenv("STUDIO_ADAPTER_CLI", "")
    get_settings.cache_clear()
    cfg = get_settings()
    h3 = slot_health(SLOT_BY_ID["comfy-h3"], cfg)
    assert h3["ok"] is True
    assert h3["live"] is False
    assert h3["not_live"] is True
    assert h3["config_present"] is False
    assert h3["window_s"] == 10.125
    assert h3["frames"] == 243
    assert h3["fps"] == 24
    assert h3["hop1_watch_required"] is True
    assert "not live" in h3["detail"].lower()

    qwen = slot_health(SLOT_BY_ID["comfy-qwen"], cfg)
    assert qwen["live"] is False
    assert qwen["not_live"] is True
    assert qwen["canvas"] == "1344x768"
    assert qwen["hop1_watch_required"] is True

    webhook = slot_health(SLOT_BY_ID["webhook"], cfg)
    assert webhook["live"] is False
    assert webhook["not_live"] is True
    assert webhook["config_present"] is False
    get_settings.cache_clear()


def test_comfy_schema_rejects_bad_webhook(monkeypatch):
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "not-a-url")
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "comfy-h3")
    get_settings.cache_clear()
    ok, errors = validate_slot_config(SLOT_BY_ID["comfy-h3"], get_settings())
    assert ok is False
    assert errors
    report = slot_health(SLOT_BY_ID["comfy-h3"], get_settings())
    assert report["schema_ok"] is False
    assert report["ok"] is False
    get_settings.cache_clear()


def test_catalog_health_endpoint(client, auth):
    listed = client.get("/api/adapters", headers=auth)
    assert listed.status_code == 200
    body = listed.json()
    assert body["health"]
    stub = next(row for row in body["health"] if row["id"] == "stub")
    assert stub["ok"] is True
    h3 = next(row for row in body["adapters"] if row["id"] == "comfy-h3")
    assert h3["window_s"] == 10.125
    assert h3["frames"] == 243
    assert h3["fps"] == 24
    assert h3["hop1_watch_required"] is True
    qwen = next(row for row in body["adapters"] if row["id"] == "comfy-qwen")
    assert qwen["canvas"] == "1344x768"
    unset_live = [row for row in body["health"] if row["id"] != "stub"]
    assert unset_live
    assert all(row["not_live"] is True for row in unset_live)
    assert all(row["live"] is False for row in unset_live)

    one = client.get("/api/adapters/comfy-h3/health", headers=auth)
    assert one.status_code == 200
    assert one.json()["not_live"] is True
    assert one.json()["window_s"] == 10.125
    dry = client.post("/api/adapters/cli/dry-run", headers=auth)
    assert dry.status_code == 200
    assert dry.json()["id"] == "cli"
    assert dry.json()["not_live"] is True
    missing = client.get("/api/adapters/not-a-slot/health", headers=auth)
    assert missing.status_code == 404


def test_configured_webhook_unreachable_blocks_enqueue(client, auth, monkeypatch):
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
    assert ids == {"stub", "comfy-h3", "comfy-qwen", "webhook", "cli", "grok-imagine"}


def test_live_comfy_does_not_skip_hop1_watch(client, auth, monkeypatch):
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "comfy-h3")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "http://127.0.0.1:9/hook")
    get_settings.cache_clear()
    assert hop1_watch_required("comfy-h3") is True
    _, episode, shots = green_ready_episode(client, auth, "Comfy watch")
    sign_off(client, auth, episode["id"])
    refused = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "live adapter must still watch hop-1"},
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "preview_incomplete"
    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    ok = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "watched"},
    )
    assert ok.status_code == 200, ok.text
    get_settings.cache_clear()
