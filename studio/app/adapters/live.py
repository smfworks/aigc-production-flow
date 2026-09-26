"""Optional webhook/CLI live hook. If unset, callers must fall back to stub."""

from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any
from urllib.parse import urlparse

import httpx

from ..local_only import is_cloud_generation_host

from ..config import Settings
from .base import AdapterResult, JobContext
from .stub import StubClipFactory, StubStillFactory
from .catalog import STUB_NAME

_ALLOWED_WEBHOOK_SCHEMES = {"http", "https"}


def _stub_still() -> StubStillFactory:
    return StubStillFactory()


def _stub_clip() -> StubClipFactory:
    return StubClipFactory()


def live_configured(settings: Settings) -> bool:
    return transport_ready(settings, "webhook-or-cli")


def transport_ready(settings: Settings, transport: str, slot_id: str | None = None) -> bool:
    if slot_id:
        from .comfy_client import native_ready

        if native_ready(settings, slot_id):
            return True
    webhook = bool((settings.adapter_webhook_url or "").strip())
    cli = bool((settings.adapter_cli or "").strip())
    if transport == "webhook":
        return webhook
    if transport == "cli":
        return cli
    if transport == "webhook-or-cli":
        return webhook or cli
    return False


def _fallback(ctx: JobContext, wanted: str) -> AdapterResult:
    if ctx.job_type == "still-sheet":
        result = _stub_still().generate_sheet(ctx)
    elif ctx.job_type == "still-plate":
        result = _stub_still().generate_plate(ctx)
    elif ctx.job_type == "clip-hop1":
        result = _stub_clip().hop1(ctx)
    elif ctx.job_type == "clip-extend":
        result = _stub_clip().extend(ctx)
    else:
        result = AdapterResult(ok=False, adapter="stub", error=f"Unknown job type {ctx.job_type}")
    result.receipt = {
        **(result.receipt or {}),
        "live_hook": f"{wanted} unset — stub only",
        "adapter": "stub",
        "claim": "Stub factory. fixture receipt only. No H3 or Qwen process ran.",
        "engine": None,
    }
    result.adapter = "stub"
    return result


def _payload(ctx: JobContext, slot_id: str | None = None) -> dict[str, Any]:
    from .catalog import slot_for

    slot = slot_for(slot_id)
    return {
        "job_id": ctx.job_id,
        "job_type": ctx.job_type,
        "episode_id": ctx.episode_id,
        "shot_id": ctx.shot_id,
        "payload": ctx.payload,
        "window": {
            "window_s": slot.window_s,
            "frames": slot.frames,
            "fps": slot.fps,
            "canvas": slot.canvas,
            "hop1_watch_required": slot.hop1_watch_required,
        },
    }


def _from_hook_body(body: dict[str, Any], fallback_name: str) -> AdapterResult:
    adapter = str(body.get("adapter") or fallback_name).strip() or fallback_name
    ok = bool(body.get("ok", True))
    error = str(body.get("error") or "")
    receipt = body.get("receipt") if isinstance(body.get("receipt"), dict) else body
    return AdapterResult(
        ok=ok and not error,
        adapter=adapter,
        receipt=receipt if isinstance(receipt, dict) else {"raw": receipt},
        error=error,
    )


class LiveStillFactory:
    def __init__(self, settings: Settings, slot_id: str | None = None):
        self.settings = settings
        self.name = (slot_id or settings.still_adapter or STUB_NAME).strip() or STUB_NAME

    def generate_sheet(self, ctx: JobContext) -> AdapterResult:
        return run_live(self.settings, ctx, wanted=self.name)

    def generate_plate(self, ctx: JobContext) -> AdapterResult:
        return run_live(self.settings, ctx, wanted=self.name)


class LiveClipFactory:
    def __init__(self, settings: Settings, slot_id: str | None = None):
        self.settings = settings
        self.name = (slot_id or settings.clip_adapter or STUB_NAME).strip() or STUB_NAME

    def hop1(self, ctx: JobContext) -> AdapterResult:
        return run_live(self.settings, ctx, wanted=self.name)

    def extend(self, ctx: JobContext) -> AdapterResult:
        return run_live(self.settings, ctx, wanted=self.name)


def _transport_for(wanted: str, settings: Settings) -> str:
    mode = (wanted or STUB_NAME).strip().lower()
    if mode in {"", STUB_NAME}:
        return STUB_NAME
    if mode == "webhook":
        return "webhook" if (settings.adapter_webhook_url or "").strip() else STUB_NAME
    if mode == "cli":
        return "cli" if (settings.adapter_cli or "").strip() else STUB_NAME
    # Documented slots (comfy-h3, comfy-qwen): prefer webhook, else CLI.
    if (settings.adapter_webhook_url or "").strip():
        return "webhook"
    if (settings.adapter_cli or "").strip():
        return "cli"
    return STUB_NAME


def run_live(settings: Settings, ctx: JobContext, wanted: str) -> AdapterResult:
    slot = (wanted or STUB_NAME).strip().lower() or STUB_NAME
    if slot in {"", STUB_NAME}:
        return _fallback(ctx, STUB_NAME)
    if ctx.cancel_requested():
        return AdapterResult(ok=False, adapter=STUB_NAME, error="cancelled")
    ctx.set_progress(20)
    transport = _transport_for(slot, settings)
    if transport == STUB_NAME:
        return _fallback(ctx, slot)
    if transport == "webhook":
        url = (settings.adapter_webhook_url or "").strip()
        if not url:
            return _fallback(ctx, slot)
        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_WEBHOOK_SCHEMES or not parsed.netloc:
            return AdapterResult(
                ok=False,
                adapter=STUB_NAME,
                error="adapter webhook URL must be http(s) with a host.",
            )
        if is_cloud_generation_host(parsed.hostname):
            return AdapterResult(
                ok=False,
                adapter=STUB_NAME,
                error=(
                    f"adapter webhook host {parsed.hostname} is a cloud generation API. "
                    "Studio stays on local inference."
                ),
            )
        try:
            response = httpx.post(
                url,
                json=_payload(ctx, slot),
                timeout=settings.adapter_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:  # noqa: BLE001 — surface hook failure on the job row
            return AdapterResult(ok=False, adapter=slot, error=f"webhook adapter failed: {exc}")
        if not isinstance(body, dict):
            return AdapterResult(ok=False, adapter=slot, error="webhook adapter returned non-JSON object.")
        ctx.set_progress(85)
        result = _from_hook_body(body, slot)
        result.receipt = {
            **(result.receipt or {}),
            "requested_slot": slot,
            "transport": "webhook",
            "hop1_watch_required": True,
        }
        from .catalog import slot_for

        meta = slot_for(slot)
        if meta.window_s:
            result.receipt.setdefault("window_s", meta.window_s)
            result.receipt.setdefault("frames", meta.frames)
            result.receipt.setdefault("fps", meta.fps)
        if meta.canvas:
            result.receipt.setdefault("canvas", meta.canvas)
        return result
    if transport == "cli":
        command = (settings.adapter_cli or "").strip()
        if not command:
            return _fallback(ctx, slot)
        try:
            filled = command.format(
                job_id=ctx.job_id,
                job_type=ctx.job_type,
                episode_id=ctx.episode_id,
                shot_id=ctx.shot_id or "",
            )
        except (KeyError, IndexError, ValueError) as exc:
            return AdapterResult(ok=False, adapter="cli", error=f"adapter CLI template failed: {exc}")
        args = shlex.split(filled)
        try:
            completed = subprocess.run(  # noqa: S603 — operator-configured local hook
                args,
                input=json.dumps(_payload(ctx, slot)),
                capture_output=True,
                text=True,
                timeout=settings.adapter_timeout_seconds,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(ok=False, adapter=slot, error=f"CLI adapter failed: {exc}")
        if completed.returncode != 0:
            err = (completed.stderr or completed.stdout or "").strip() or f"exit {completed.returncode}"
            return AdapterResult(ok=False, adapter=slot, error=f"CLI adapter failed: {err}")
        try:
            body = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            return AdapterResult(ok=False, adapter=slot, error=f"CLI adapter stdout is not JSON: {exc}")
        if not isinstance(body, dict):
            return AdapterResult(ok=False, adapter=slot, error="CLI adapter returned non-JSON object.")
        ctx.set_progress(85)
        result = _from_hook_body(body, slot)
        result.receipt = {
            **(result.receipt or {}),
            "requested_slot": slot,
            "transport": "cli",
            "hop1_watch_required": True,
        }
        from .catalog import slot_for

        meta = slot_for(slot)
        if meta.window_s:
            result.receipt.setdefault("window_s", meta.window_s)
            result.receipt.setdefault("frames", meta.frames)
            result.receipt.setdefault("fps", meta.fps)
        if meta.canvas:
            result.receipt.setdefault("canvas", meta.canvas)
        return result
    return _fallback(ctx, slot)
