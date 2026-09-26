"""Studio generation stays off public cloud hosts."""

from __future__ import annotations

from pathlib import Path

from app.adapters.base import JobContext
from app.adapters.comfy_client import validate_lane
from app.adapters.live import run_live
from app.config import Settings
from app.local_only import is_cloud_generation_host

_MARKERS = (
    "api.x.ai",
    "grok-imagine",
    "STUDIO_IMAGINE_",
    "imagine_bridge",
    "imagine-http",
    "called_imagine",
)


def test_known_cloud_generation_hosts():
    assert is_cloud_generation_host("api.x.ai") is True
    assert is_cloud_generation_host("API.X.AI.") is True
    assert is_cloud_generation_host("127.0.0.1") is False
    assert is_cloud_generation_host("localhost") is False
    assert is_cloud_generation_host("comfy.local") is False


def test_comfy_lanes_refuse_cloud_generation_hosts_even_when_allowlisted():
    settings = Settings(comfy_allow_hosts="api.x.ai,comfy.example.com")
    ok, err = validate_lane("https://api.x.ai/v1", settings)
    assert ok is False
    assert "cloud generation" in err
    ok, err = validate_lane("http://127.0.0.1:8188", settings)
    assert ok is True
    ok, err = validate_lane("http://10.1.2.3:8188", settings)
    assert ok is True


def test_webhook_refuses_a_cloud_generation_host_without_posting(monkeypatch):
    posted: list[str] = []

    def _post(*_args, **_kwargs):
        posted.append("posted")
        raise AssertionError("webhook must not call a cloud generation host")

    monkeypatch.setattr("app.adapters.live.httpx.post", _post)
    settings = Settings(adapter_webhook_url="https://api.x.ai/v1/images/generations")
    result = run_live(
        settings,
        JobContext(
            job_id="job",
            job_type="still-sheet",
            episode_id="ep",
            shot_id=None,
            payload={},
            pack={},
            cancel_requested=lambda: False,
            set_progress=lambda _value: None,
        ),
        wanted="webhook",
    )
    assert result.ok is False
    assert "cloud generation" in result.error
    assert posted == []


def test_adapter_sources_do_not_name_a_cloud_generation_client():
    root = Path(__file__).resolve().parents[1] / "app"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        if path.name == "local_only.py":
            continue
        text = path.read_text(encoding="utf-8")
        for marker in _MARKERS:
            if marker in text:
                hits.append(f"{path.relative_to(root)}: {marker}")
    assert hits == []
