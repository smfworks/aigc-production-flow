"""Pick stub vs live. Unset live hooks always resolve to stub."""

from __future__ import annotations

from ..config import Settings, get_settings
from .base import ClipFactory, StillFactory
from .live import LiveClipFactory, LiveStillFactory
from .stub import STUB_NAME, StubClipFactory, StubStillFactory


def _mode(value: str) -> str:
    return (value or STUB_NAME).strip().lower() or STUB_NAME


def resolve_adapter_name(job_type: str, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    if job_type in {"still-sheet", "still-plate"}:
        mode = _mode(cfg.still_adapter)
        if mode == "webhook" and not (cfg.adapter_webhook_url or "").strip():
            return STUB_NAME
        if mode == "cli" and not (cfg.adapter_cli or "").strip():
            return STUB_NAME
        return mode if mode in {"stub", "webhook", "cli"} else STUB_NAME
    if job_type in {"clip-hop1", "clip-extend"}:
        mode = _mode(cfg.clip_adapter)
        if mode == "webhook" and not (cfg.adapter_webhook_url or "").strip():
            return STUB_NAME
        if mode == "cli" and not (cfg.adapter_cli or "").strip():
            return STUB_NAME
        return mode if mode in {"stub", "webhook", "cli"} else STUB_NAME
    return STUB_NAME


def get_still_factory(settings: Settings | None = None) -> StillFactory:
    cfg = settings or get_settings()
    name = resolve_adapter_name("still-sheet", cfg)
    if name == STUB_NAME:
        return StubStillFactory()
    return LiveStillFactory(cfg)


def get_clip_factory(settings: Settings | None = None) -> ClipFactory:
    cfg = settings or get_settings()
    name = resolve_adapter_name("clip-hop1", cfg)
    if name == STUB_NAME:
        return StubClipFactory()
    return LiveClipFactory(cfg)
