"""Still + clip factory adapters. Stub is the CI default; live hooks are optional."""

from .base import AdapterResult, ClipFactory, JobContext, StillFactory
from .catalog import CATALOG, STUB_NAME
from .health import catalog_health, health_for
from .registry import get_clip_factory, get_still_factory, resolve_adapter_name

__all__ = [
    "CATALOG",
    "STUB_NAME",
    "AdapterResult",
    "ClipFactory",
    "JobContext",
    "StillFactory",
    "catalog_health",
    "get_clip_factory",
    "get_still_factory",
    "health_for",
    "resolve_adapter_name",
]
