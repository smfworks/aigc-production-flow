from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class AdapterResult:
    ok: bool
    adapter: str
    receipt: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    media_bytes: bytes | None = None
    media_name: str = ""
    media_kind: str = "other"
    content_type: str = "application/json"
    pending: bool = False


@dataclass
class JobContext:
    job_id: str
    job_type: str
    episode_id: str
    shot_id: str | None
    payload: dict[str, Any]
    pack: dict[str, Any]
    cancel_requested: Callable[[], bool]
    set_progress: Callable[[int], None]


class StillFactory(Protocol):
    name: str

    def generate_sheet(self, ctx: JobContext) -> AdapterResult: ...

    def generate_plate(self, ctx: JobContext) -> AdapterResult: ...


class ClipFactory(Protocol):
    name: str

    def hop1(self, ctx: JobContext) -> AdapterResult: ...

    def extend(self, ctx: JobContext) -> AdapterResult: ...
