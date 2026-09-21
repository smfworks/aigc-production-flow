"""Still + clip factory adapters. Stub is the CI default; live hooks are optional."""

from .base import AdapterResult, ClipFactory, JobContext, StillFactory
from .registry import get_clip_factory, get_still_factory, resolve_adapter_name

__all__ = [
    "AdapterResult",
    "ClipFactory",
    "JobContext",
    "StillFactory",
    "get_clip_factory",
    "get_still_factory",
    "resolve_adapter_name",
]
