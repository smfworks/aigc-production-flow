"""Optional webhook/CLI live hook. If unset, callers must fall back to stub."""

from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import Settings
from .base import AdapterResult, JobContext
from .stub import StubClipFactory, StubStillFactory

_ALLOWED_WEBHOOK_SCHEMES = {"http", "https"}


def _stub_still() -> StubStillFactory:
    return StubStillFactory()


def _stub_clip() -> StubClipFactory:
    return StubClipFactory()


def live_configured(settings: Settings) -> bool:
    mode = (settings.still_adapter or "stub").strip().lower()
    clip = (settings.clip_adapter or "stub").strip().lower()
    if mode in {"webhook", "cli"} or clip in {"webhook", "cli"}:
        if mode == "webhook" or clip == "webhook":
            return bool((settings.adapter_webhook_url or "").strip())
        if mode == "cli" or clip == "cli":
            return bool((settings.adapter_cli or "").strip())
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


def _payload(ctx: JobContext) -> dict[str, Any]:
    return {
        "job_id": ctx.job_id,
        "job_type": ctx.job_type,
        "episode_id": ctx.episode_id,
        "shot_id": ctx.shot_id,
        "payload": ctx.payload,
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
    def __init__(self, settings: Settings):
        self.settings = settings
        self.name = (settings.still_adapter or "stub").strip() or "stub"

    def generate_sheet(self, ctx: JobContext) -> AdapterResult:
        return run_live(self.settings, ctx, wanted=self.name)

    def generate_plate(self, ctx: JobContext) -> AdapterResult:
        return run_live(self.settings, ctx, wanted=self.name)


class LiveClipFactory:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.name = (settings.clip_adapter or "stub").strip() or "stub"

    def hop1(self, ctx: JobContext) -> AdapterResult:
        return run_live(self.settings, ctx, wanted=self.name)

    def extend(self, ctx: JobContext) -> AdapterResult:
        return run_live(self.settings, ctx, wanted=self.name)


def run_live(settings: Settings, ctx: JobContext, wanted: str) -> AdapterResult:
    mode = (wanted or "stub").strip().lower()
    if mode in {"", "stub"}:
        return _fallback(ctx, "stub")
    if ctx.cancel_requested():
        return AdapterResult(ok=False, adapter="stub", error="cancelled")
    ctx.set_progress(20)
    if mode == "webhook":
        url = (settings.adapter_webhook_url or "").strip()
        if not url:
            return _fallback(ctx, "webhook")
        parsed = urlparse(url)
        if parsed.scheme not in _ALLOWED_WEBHOOK_SCHEMES or not parsed.netloc:
            return AdapterResult(
                ok=False,
                adapter="stub",
                error="adapter webhook URL must be http(s) with a host.",
            )
        try:
            response = httpx.post(
                url,
                json=_payload(ctx),
                timeout=settings.adapter_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        except Exception as exc:  # noqa: BLE001 — surface hook failure on the job row
            return AdapterResult(ok=False, adapter=mode, error=f"webhook adapter failed: {exc}")
        if not isinstance(body, dict):
            return AdapterResult(ok=False, adapter=mode, error="webhook adapter returned non-JSON object.")
        ctx.set_progress(85)
        return _from_hook_body(body, mode)
    if mode == "cli":
        command = (settings.adapter_cli or "").strip()
        if not command:
            return _fallback(ctx, "cli")
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
                input=json.dumps(_payload(ctx)),
                capture_output=True,
                text=True,
                timeout=settings.adapter_timeout_seconds,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(ok=False, adapter="cli", error=f"CLI adapter failed: {exc}")
        if completed.returncode != 0:
            err = (completed.stderr or completed.stdout or "").strip() or f"exit {completed.returncode}"
            return AdapterResult(ok=False, adapter="cli", error=f"CLI adapter failed: {err}")
        try:
            body = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            return AdapterResult(ok=False, adapter="cli", error=f"CLI adapter stdout is not JSON: {exc}")
        if not isinstance(body, dict):
            return AdapterResult(ok=False, adapter="cli", error="CLI adapter returned non-JSON object.")
        ctx.set_progress(85)
        return _from_hook_body(body, "cli")
    return _fallback(ctx, mode)
