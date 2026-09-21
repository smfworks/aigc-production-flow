"""Health / dry-run for adapter slots. Stub is always ok. Live slots report config + reachability."""

from __future__ import annotations

from pathlib import Path
from shutil import which
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import Settings, get_settings
from .catalog import CATALOG, STUB_NAME, AdapterSlot, slot_for
from .live import transport_ready

_HEALTH_TIMEOUT = 2.5


def _webhook_reachable(url: str, timeout: float) -> tuple[bool | None, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "webhook URL must be http(s) with a host"
    try:
        response = httpx.request("HEAD", url, timeout=timeout, follow_redirects=True)
        if response.status_code in {404, 405, 501}:
            response = httpx.request("GET", url, timeout=timeout, follow_redirects=True)
        if response.status_code >= 500:
            return False, f"webhook returned HTTP {response.status_code}"
        return True, f"webhook reachable (HTTP {response.status_code})"
    except Exception as exc:  # noqa: BLE001 — health is advisory
        return False, f"webhook unreachable: {exc}"


def _cli_reachable(command: str) -> tuple[bool | None, str]:
    token = command.strip().split()[0] if command.strip() else ""
    if not token:
        return False, "CLI command empty"
    if "/" in token or token.startswith("."):
        path = Path(token).expanduser()
        if path.exists():
            return True, f"CLI binary present ({path})"
        return False, f"CLI binary missing: {path}"
    found = which(token)
    if found:
        return True, f"CLI binary on PATH ({found})"
    return False, f"CLI binary not on PATH: {token}"


def slot_health(slot: AdapterSlot, settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    timeout = min(_HEALTH_TIMEOUT, max(0.5, float(cfg.adapter_timeout_seconds or 2)))
    webhook = (cfg.adapter_webhook_url or "").strip()
    cli = (cfg.adapter_cli or "").strip()
    if slot.id == STUB_NAME or not slot.live:
        return {
            "id": slot.id,
            "ok": True,
            "live": False,
            "config_present": True,
            "reachable": True,
            "transport": slot.transport,
            "detail": "Stub fixture receipts. Always healthy. Never claims H3 or Qwen ran.",
        }
    present = transport_ready(cfg, slot.transport)
    reachable: bool | None = None
    detail = ""
    if not present:
        needed = []
        if slot.transport in {"webhook", "webhook-or-cli"}:
            needed.append("STUDIO_ADAPTER_WEBHOOK_URL")
        if slot.transport in {"cli", "webhook-or-cli"}:
            needed.append("STUDIO_ADAPTER_CLI")
        detail = (
            f"{slot.id} hook unset ({' or '.join(needed)}). "
            "Enqueue falls back to stub. Live adapter is not healthy."
        )
        return {
            "id": slot.id,
            "ok": False,
            "live": True,
            "config_present": False,
            "reachable": None,
            "transport": slot.transport,
            "detail": detail,
        }
    notes: list[str] = []
    ok = True
    if slot.transport in {"webhook", "webhook-or-cli"} and webhook:
        reachable, note = _webhook_reachable(webhook, timeout)
        notes.append(note)
        ok = ok and bool(reachable)
    if slot.transport in {"cli", "webhook-or-cli"} and cli and (slot.transport == "cli" or not webhook):
        reachable, note = _cli_reachable(cli)
        notes.append(note)
        ok = ok and bool(reachable)
    return {
        "id": slot.id,
        "ok": ok,
        "live": True,
        "config_present": True,
        "reachable": reachable,
        "transport": slot.transport,
        "detail": "; ".join(notes) or "config present",
    }


def catalog_health(settings: Settings | None = None) -> list[dict[str, Any]]:
    cfg = settings or get_settings()
    return [slot_health(slot, cfg) for slot in CATALOG]


def health_for(adapter_id: str, settings: Settings | None = None) -> dict[str, Any]:
    return slot_health(slot_for(adapter_id), settings)


def refuse_if_unhealthy(adapter_id: str, settings: Settings | None = None) -> dict[str, Any]:
    """Block enqueue when the *resolved* live adapter is configured but not reachable."""
    from fastapi import HTTPException, status as http_status

    report = health_for(adapter_id, settings)
    if report["id"] == STUB_NAME or not report["live"]:
        return report
    if report["ok"]:
        return report
    if not report["config_present"]:
        # Unset hooks already resolve to stub; callers should not hit this after resolve.
        return report
    raise HTTPException(
        status_code=http_status.HTTP_409_CONFLICT,
        detail={
            "code": "adapter_unhealthy",
            "message": (
                f"Live adapter {report['id']} is unhealthy. "
                "Fix the hook or enqueue with adapter=stub. "
                "Unset live hooks stay stub — this is a configured-but-down box."
            ),
            "health": report,
        },
    )
