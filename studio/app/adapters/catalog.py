"""Named still/clip adapter slots. Stub is live-by-default; others are documented hooks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Kind = Literal["still", "clip"]
Transport = Literal["none", "webhook", "cli", "webhook-or-cli"]

STUB_NAME = "stub"


@dataclass(frozen=True)
class AdapterSlot:
    id: str
    label: str
    kinds: tuple[Kind, ...]
    live: bool
    transport: Transport
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kinds": list(self.kinds),
            "live": self.live,
            "transport": self.transport,
            "note": self.note,
        }


CATALOG: tuple[AdapterSlot, ...] = (
    AdapterSlot(
        id=STUB_NAME,
        label="Stub (fixture receipts)",
        kinds=("still", "clip"),
        live=False,
        transport="none",
        note="Default. Writes JSON fixture receipts. Never claims H3 or Qwen ran.",
    ),
    AdapterSlot(
        id="comfy-qwen",
        label="Comfy Qwen still factory (slot)",
        kinds=("still",),
        live=True,
        transport="webhook-or-cli",
        note=(
            "Documented still slot for a Qwen-Image Comfy box. "
            "Needs STUDIO_ADAPTER_WEBHOOK_URL or STUDIO_ADAPTER_CLI. Unset → stub only."
        ),
    ),
    AdapterSlot(
        id="comfy-h3",
        label="Comfy MiniMax H3 (slot)",
        kinds=("clip",),
        live=True,
        transport="webhook-or-cli",
        note=(
            "Documented clip slot for native H3 on a Comfy box. "
            "Needs STUDIO_ADAPTER_WEBHOOK_URL or STUDIO_ADAPTER_CLI. Unset → stub only."
        ),
    ),
    AdapterSlot(
        id="webhook",
        label="Webhook live hook",
        kinds=("still", "clip"),
        live=True,
        transport="webhook",
        note="POST the job payload to STUDIO_ADAPTER_WEBHOOK_URL. Unset URL → stub only.",
    ),
    AdapterSlot(
        id="cli",
        label="CLI live hook",
        kinds=("still", "clip"),
        live=True,
        transport="cli",
        note="Run STUDIO_ADAPTER_CLI with JSON on stdin. Unset command → stub only.",
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
