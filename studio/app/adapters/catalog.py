"""Named still/clip adapter slots. Stub is live-by-default; others are documented hooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Kind = Literal["still", "clip"]
Transport = Literal["none", "webhook", "cli", "webhook-or-cli"]

STUB_NAME = "stub"

# Measured hop-1 on the H3 Comfy box. Other clip adapters must declare their own window.
H3_WINDOW_S = 10.125
H3_FRAMES = 243
H3_FPS = 24.0
QWEN_CANVAS = "1344x768"

COMIFY_ENV_SCHEMA: dict[str, Any] = {
    "type": "object",
    "anyOf": [
        {"required": ["STUDIO_ADAPTER_WEBHOOK_URL"]},
        {"required": ["STUDIO_ADAPTER_CLI"]},
    ],
    "properties": {
        "STUDIO_ADAPTER_WEBHOOK_URL": {
            "type": "string",
            "format": "uri",
            "description": "http(s) webhook that accepts the job JSON payload.",
        },
        "STUDIO_ADAPTER_CLI": {
            "type": "string",
            "description": "Command template: {job_id} {job_type} {episode_id} {shot_id}; JSON on stdin.",
        },
        "STUDIO_ADAPTER_TIMEOUT_SECONDS": {"type": "number", "exclusiveMinimum": 0},
    },
}

WEBHOOK_ENV_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["STUDIO_ADAPTER_WEBHOOK_URL"],
    "properties": {
        "STUDIO_ADAPTER_WEBHOOK_URL": {"type": "string", "format": "uri"},
        "STUDIO_ADAPTER_TIMEOUT_SECONDS": {"type": "number", "exclusiveMinimum": 0},
    },
}

CLI_ENV_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["STUDIO_ADAPTER_CLI"],
    "properties": {
        "STUDIO_ADAPTER_CLI": {"type": "string", "minLength": 1},
        "STUDIO_ADAPTER_TIMEOUT_SECONDS": {"type": "number", "exclusiveMinimum": 0},
    },
}


@dataclass(frozen=True)
class AdapterSlot:
    id: str
    label: str
    kinds: tuple[Kind, ...]
    live: bool
    transport: Transport
    note: str
    window_s: float | None = None
    frames: int | None = None
    fps: float | None = None
    canvas: str | None = None
    hop1_watch_required: bool = True
    config_schema: dict[str, Any] = field(default_factory=dict)
    honesty: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kinds": list(self.kinds),
            "live": self.live,
            "transport": self.transport,
            "note": self.note,
            "window_s": self.window_s,
            "frames": self.frames,
            "fps": self.fps,
            "canvas": self.canvas,
            "hop1_watch_required": self.hop1_watch_required,
            "config_schema": self.config_schema,
            "honesty": self.honesty,
        }


CATALOG: tuple[AdapterSlot, ...] = (
    AdapterSlot(
        id=STUB_NAME,
        label="Stub (fixture receipts)",
        kinds=("still", "clip"),
        live=False,
        transport="none",
        note="Default. Writes JSON fixture receipts. Never claims H3 or Qwen ran.",
        window_s=H3_WINDOW_S,
        frames=H3_FRAMES,
        fps=H3_FPS,
        canvas=QWEN_CANVAS,
        hop1_watch_required=True,
        honesty="Stub fixture receipts. Not live. Hop-1 watch still required before generate-ok.",
    ),
    AdapterSlot(
        id="comfy-qwen",
        label="Comfy Qwen still factory (slot)",
        kinds=("still",),
        live=True,
        transport="webhook-or-cli",
        note=(
            "Documented still slot for a Qwen-Image Comfy box. Native canvas 1344×768. "
            "Needs STUDIO_ADAPTER_WEBHOOK_URL or STUDIO_ADAPTER_CLI. Unset → stub only. Not live until set."
        ),
        canvas=QWEN_CANVAS,
        hop1_watch_required=True,
        config_schema=COMIFY_ENV_SCHEMA,
        honesty=(
            "Measured still factory canvas 1344×768. Unset hook is not live (resolves to stub). "
            "Does not skip hop-1 watch. Not Hailuo/Veo/Kling."
        ),
    ),
    AdapterSlot(
        id="comfy-h3",
        label="Comfy MiniMax H3 (slot)",
        kinds=("clip",),
        live=True,
        transport="webhook-or-cli",
        note=(
            "Documented clip slot for native H3 on a Comfy box. Measured hop-1 window: "
            "10.125 s / 243 f @ 24 fps. Needs STUDIO_ADAPTER_WEBHOOK_URL or STUDIO_ADAPTER_CLI. "
            "Unset → stub only. Hop-1 watch protocol is required before generate-ok."
        ),
        window_s=H3_WINDOW_S,
        frames=H3_FRAMES,
        fps=H3_FPS,
        hop1_watch_required=True,
        config_schema=COMIFY_ENV_SCHEMA,
        honesty=(
            "Measured hop-1 10.125s / 243f @ 24fps. Unset hook is not live (resolves to stub). "
            "Live adapters must not skip hop-1 watch. Not Hailuo/Veo/Kling."
        ),
    ),
    AdapterSlot(
        id="webhook",
        label="Webhook live hook",
        kinds=("still", "clip"),
        live=True,
        transport="webhook",
        note="POST the job payload to STUDIO_ADAPTER_WEBHOOK_URL. Unset URL → stub only. Not live until set.",
        hop1_watch_required=True,
        config_schema=WEBHOOK_ENV_SCHEMA,
        honesty="Generic webhook transport. Unset is not live. Hop-1 watch still required.",
    ),
    AdapterSlot(
        id="cli",
        label="CLI live hook",
        kinds=("still", "clip"),
        live=True,
        transport="cli",
        note="Run STUDIO_ADAPTER_CLI with JSON on stdin. Unset command → stub only. Not live until set.",
        hop1_watch_required=True,
        config_schema=CLI_ENV_SCHEMA,
        honesty="Generic CLI transport. Unset is not live. Hop-1 watch still required.",
    ),
)

KNOWN_IDS = {slot.id for slot in CATALOG}
SLOT_BY_ID = {slot.id: slot for slot in CATALOG}

STILL_JOBS = {"still-sheet", "still-plate"}
CLIP_JOBS = {"clip-hop1", "clip-extend"}


def job_kind(job_type: str) -> Kind | None:
    if job_type in STILL_JOBS:
        return "still"
    if job_type in CLIP_JOBS:
        return "clip"
    return None


def slot_for(adapter_id: str | None) -> AdapterSlot:
    key = (adapter_id or STUB_NAME).strip().lower() or STUB_NAME
    return SLOT_BY_ID.get(key, SLOT_BY_ID[STUB_NAME])


def hop1_watch_required(adapter_id: str | None = None) -> bool:
    """Live adapters must not skip the hop-1 watch protocol. Always True for clip slots."""
    slot = slot_for(adapter_id)
    return bool(slot.hop1_watch_required)


def require_slot(adapter_id: str | None, kind: Kind | None = None) -> str:
    from fastapi import HTTPException, status

    raw = (adapter_id or STUB_NAME).strip().lower() or STUB_NAME
    slot = SLOT_BY_ID.get(raw)
    if slot is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"adapter must be one of: {', '.join(sorted(KNOWN_IDS))}",
        )
    if kind is not None and kind not in slot.kinds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{slot.id} is not a {kind} adapter.",
        )
    return slot.id
