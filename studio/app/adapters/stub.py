"""Honest stub factories. Fixture receipts only — never claim H3 or Qwen ran."""

from __future__ import annotations

import json
import time
from typing import Any

from .base import AdapterResult, JobContext

STUB_NAME = "stub"

H3_MEASURED_WINDOW = {
    "duration_s": 10.125,
    "frames": 243,
    "fps": 24.0,
    "note": (
        "Numbers match the measured H3 hop-1 window (10.125 s / 243 f @ 24 fps). "
        "This is a fixture receipt. No clip engine ran."
    ),
}

STUB_CLAIM = "Stub factory. fixture receipt only. No H3 or Qwen process ran."


def _maybe_sleep(ctx: JobContext) -> AdapterResult | None:
    """Test hook: payload.debug_sleep_s lets cancel-while-running be asserted."""
    raw = ctx.payload.get("debug_sleep_s") if isinstance(ctx.payload, dict) else None
    try:
        sleep_s = float(raw or 0)
    except (TypeError, ValueError):
        sleep_s = 0.0
    if sleep_s <= 0:
        return None
    deadline = time.time() + sleep_s
    while time.time() < deadline:
        if ctx.cancel_requested():
            return AdapterResult(ok=False, adapter=STUB_NAME, error="cancelled")
        time.sleep(0.05)
        remaining = max(0.0, deadline - time.time())
        ctx.set_progress(min(90, int(100 * (1 - remaining / sleep_s))))
    return None


def _receipt(kind: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {
        "adapter": STUB_NAME,
        "engine": None,
        "job": kind,
        "claim": STUB_CLAIM,
        "live_hook": "unset — stub only",
    }
    if extra:
        body.update(extra)
    return body


def _json_media(receipt: dict[str, Any], filename: str, kind: str) -> AdapterResult:
    payload = json.dumps(receipt, indent=2).encode("utf-8")
    return AdapterResult(
        ok=True,
        adapter=STUB_NAME,
        receipt=receipt,
        media_bytes=payload,
        media_name=filename,
        media_kind=kind,
        content_type="application/json",
    )


class StubStillFactory:
    name = STUB_NAME

    def generate_sheet(self, ctx: JobContext) -> AdapterResult:
        cancelled = _maybe_sleep(ctx)
        if cancelled:
            return cancelled
        ctx.set_progress(40)
        entity = str(ctx.payload.get("entity") or ctx.payload.get("entity_label") or "sheet")
        receipt = _receipt(
            "still-sheet",
            {
                "entity": entity,
                "role": "sheet",
                "canvas": "1344×768",
                "still_vs_lock": (
                    "Fixture: no sheet pixels were generated. "
                    "Do not treat this as a Qwen-Image still."
                ),
            },
        )
        ctx.set_progress(90)
        return _json_media(receipt, f"stub-sheet-{ctx.job_id[:8]}.json", "sheet")

    def generate_plate(self, ctx: JobContext) -> AdapterResult:
        cancelled = _maybe_sleep(ctx)
        if cancelled:
            return cancelled
        ctx.set_progress(40)
        entity = str(ctx.payload.get("entity") or ctx.payload.get("entity_label") or "plate")
        take = str(ctx.payload.get("take") or "")
        receipt = _receipt(
            "still-plate",
            {
                "entity": entity,
                "take": take,
                "role": "hop-1 plate",
                "canvas": "1344×768",
                "still_vs_lock": (
                    "Fixture: no plate pixels were generated. "
                    "Do not treat this as a Qwen-Image plate."
                ),
            },
        )
        ctx.set_progress(90)
        return _json_media(receipt, f"stub-plate-{ctx.job_id[:8]}.json", "plate")


class StubClipFactory:
    name = STUB_NAME

    def hop1(self, ctx: JobContext) -> AdapterResult:
        cancelled = _maybe_sleep(ctx)
        if cancelled:
            return cancelled
        ctx.set_progress(35)
        take = str(ctx.payload.get("take") or "")
        receipt = _receipt(
            "clip-hop1",
            {
                "take": take,
                "duration_s": H3_MEASURED_WINDOW["duration_s"],
                "frames": H3_MEASURED_WINDOW["frames"],
                "fps": H3_MEASURED_WINDOW["fps"],
                "window": H3_MEASURED_WINDOW["note"],
                "still_vs_lock": (
                    "Fixture still-vs-lock: no hop-1 frame exists to compare against the lock. "
                    "Attach this receipt, watch it, then stamp preview-watched by hand."
                ),
                "preview_kind": "json-receipt",
            },
        )
        ctx.set_progress(90)
        return _json_media(receipt, f"stub-hop1-{ctx.job_id[:8]}.json", "preview")

    def extend(self, ctx: JobContext) -> AdapterResult:
        cancelled = _maybe_sleep(ctx)
        if cancelled:
            return cancelled
        ctx.set_progress(35)
        receipt = _receipt(
            "clip-extend",
            {
                "duration_s": H3_MEASURED_WINDOW["duration_s"],
                "frames": H3_MEASURED_WINDOW["frames"],
                "fps": H3_MEASURED_WINDOW["fps"],
                "window": H3_MEASURED_WINDOW["note"],
                "still_vs_lock": (
                    "Fixture extend: no motion-context latent was loaded. "
                    "Not an H3 hop 2+."
                ),
            },
        )
        ctx.set_progress(90)
        return _json_media(receipt, f"stub-extend-{ctx.job_id[:8]}.json", "preview")
