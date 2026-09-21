"""Pick stub vs documented live slots. Unset live hooks always resolve to stub."""

from __future__ import annotations

from ..config import Settings, get_settings
from ..models import Project
from .base import ClipFactory, StillFactory
from .catalog import (
    CLIP_JOBS,
    STILL_JOBS,
    STUB_NAME,
    job_kind,
    slot_for,
)
from .live import LiveClipFactory, LiveStillFactory, transport_ready
from .stub import StubClipFactory, StubStillFactory


def _mode(value: str | None) -> str:
    return (value or STUB_NAME).strip().lower() or STUB_NAME


def env_default(job_type: str, settings: Settings) -> str:
    if job_type in STILL_JOBS:
        return _mode(settings.still_adapter)
    if job_type in CLIP_JOBS:
        return _mode(settings.clip_adapter)
    return STUB_NAME


def project_default(job_type: str, project: Project | None, settings: Settings) -> str:
    if project is None:
        return env_default(job_type, settings)
    if job_type in STILL_JOBS:
        return _mode(project.still_adapter) or env_default(job_type, settings)
    if job_type in CLIP_JOBS:
        return _mode(project.clip_adapter) or env_default(job_type, settings)
    return STUB_NAME


def resolve_adapter_name(
    job_type: str,
    settings: Settings | None = None,
    *,
    requested: str | None = None,
    project: Project | None = None,
) -> str:
    cfg = settings or get_settings()
    kind = job_kind(job_type)
    if kind is None:
        return STUB_NAME
    candidate = _mode(requested) if requested else project_default(job_type, project, cfg)
    slot = slot_for(candidate)
    if slot.id != candidate:
        return STUB_NAME
    if kind not in slot.kinds:
        return STUB_NAME
    if not slot.live:
        return STUB_NAME
    if not transport_ready(cfg, slot.transport):
        return STUB_NAME
    return slot.id


def get_still_factory(
    settings: Settings | None = None,
    *,
    requested: str | None = None,
    project: Project | None = None,
) -> StillFactory:
    cfg = settings or get_settings()
    name = resolve_adapter_name("still-sheet", cfg, requested=requested, project=project)
    if name == STUB_NAME:
        return StubStillFactory()
    return LiveStillFactory(cfg, slot_id=name)


def get_clip_factory(
    settings: Settings | None = None,
    *,
    requested: str | None = None,
    project: Project | None = None,
) -> ClipFactory:
    cfg = settings or get_settings()
    name = resolve_adapter_name("clip-hop1", cfg, requested=requested, project=project)
    if name == STUB_NAME:
        return StubClipFactory()
    return LiveClipFactory(cfg, slot_id=name)
