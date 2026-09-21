import json

from app.adapters.live import run_live
from app.adapters.registry import resolve_adapter_name
from app.adapters.stub import StubClipFactory, StubStillFactory
from app.adapters.base import JobContext
from app.config import get_settings


def _ctx(job_type: str, payload=None) -> JobContext:
    return JobContext(
        job_id="job-1",
        job_type=job_type,
        episode_id="ep-1",
        shot_id="shot-1",
        payload=payload or {},
        pack={},
        cancel_requested=lambda: False,
        set_progress=lambda _value: None,
    )


def test_stub_never_claims_real_engine():
    sheet = StubStillFactory().generate_sheet(_ctx("still-sheet", {"entity": "smith"}))
    assert sheet.ok
    assert sheet.adapter == "stub"
    assert sheet.receipt["engine"] is None
    assert sheet.receipt["adapter"] == "stub"
    assert "No H3 or Qwen process ran" in sheet.receipt["claim"]
    hop = StubClipFactory().hop1(_ctx("clip-hop1"))
    assert hop.receipt["duration_s"] == 10.125
    assert hop.receipt["frames"] == 243
    assert hop.media_kind == "preview"
    text = json.dumps(hop.receipt).lower()
    assert "h3 ran" not in text
    assert "qwen ran" not in text


def test_webhook_unset_falls_back_to_stub(monkeypatch):
    monkeypatch.setenv("STUDIO_STILL_ADAPTER", "webhook")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "")
    get_settings.cache_clear()
    settings = get_settings()
    assert resolve_adapter_name("still-sheet", settings) == "stub"
    result = run_live(settings, _ctx("still-sheet"), wanted="webhook")
    assert result.adapter == "stub"
    assert result.ok
    assert "webhook unset" in result.receipt["live_hook"]
    assert result.receipt["engine"] is None
    get_settings.cache_clear()


def test_cli_unset_falls_back_to_stub(monkeypatch):
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "cli")
    monkeypatch.setenv("STUDIO_ADAPTER_CLI", "")
    get_settings.cache_clear()
    settings = get_settings()
    assert resolve_adapter_name("clip-hop1", settings) == "stub"
    result = run_live(settings, _ctx("clip-hop1"), wanted="cli")
    assert result.adapter == "stub"
    assert "cli unset" in result.receipt["live_hook"]
    get_settings.cache_clear()


def test_comfy_slot_unset_falls_back_to_stub(monkeypatch):
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "comfy-h3")
    monkeypatch.setenv("STUDIO_STILL_ADAPTER", "comfy-qwen")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "")
    monkeypatch.setenv("STUDIO_ADAPTER_CLI", "")
    get_settings.cache_clear()
    settings = get_settings()
    assert resolve_adapter_name("clip-hop1", settings) == "stub"
    assert resolve_adapter_name("still-sheet", settings) == "stub"
    get_settings.cache_clear()


def test_comfy_slot_with_webhook_keeps_slot_id(monkeypatch):
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "comfy-h3")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "http://127.0.0.1:9/hook")
    get_settings.cache_clear()
    settings = get_settings()
    assert resolve_adapter_name("clip-hop1", settings) == "comfy-h3"
    get_settings.cache_clear()
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "webhook")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "http://127.0.0.1:9/hook")
    get_settings.cache_clear()
    settings = get_settings()
    assert resolve_adapter_name("clip-hop1", settings) == "webhook"

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ok": True,
                "adapter": "local-cli-hook",
                "receipt": {"adapter": "local-cli-hook", "engine": "operator-box"},
            }

    def fake_post(url, json, timeout):  # noqa: A002
        assert url == "http://127.0.0.1:9/hook"
        assert json["job_type"] == "clip-hop1"
        return FakeResponse()

    monkeypatch.setattr("app.adapters.live.httpx.post", fake_post)
    result = run_live(settings, _ctx("clip-hop1"), wanted="webhook")
    assert result.ok
    assert result.adapter == "local-cli-hook"
    get_settings.cache_clear()
