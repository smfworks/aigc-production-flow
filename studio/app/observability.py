"""Liveness/readiness, structured JSON request logs, and a tiny Prometheus scrape.

This is not a claimed SaaS APM. Secrets (Authorization, tokens, webhook URLs)
never go in the log line.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from collections.abc import Callable
from threading import Lock
from typing import Any

log = logging.getLogger("studio.http")

_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_SECRET_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "studio_api_token",
        "token",
        "password",
        "secret",
        "s3_secret_key",
        "s3_access_key",
        "notify_webhook_url",
        "adapter_webhook_url",
        "celery_broker_url",
    }
)

_lock = Lock()
_request_counts: dict[tuple[str, str, str], int] = defaultdict(int)


def normalize_path(path: str) -> str:
    cleaned = _UUID.sub("{id}", path or "/")
    return cleaned or "/"


def observe_request(method: str, path: str, status_code: int) -> None:
    key = ((method or "GET").upper(), normalize_path(path), str(status_code))
    with _lock:
        _request_counts[key] += 1


def request_count_snapshot() -> list[tuple[str, str, str, int]]:
    with _lock:
        return [(method, path, status, count) for (method, path, status), count in _request_counts.items()]


class StructuredLogMiddleware:
    """Pure ASGI middleware so request ContextVars (active org) stay intact.

    BaseHTTPMiddleware would spawn a task and drop ``active_org_id``.
    """

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            ms = int((time.perf_counter() - started) * 1000)
            path = scope.get("path") or "/"
            method = (scope.get("method") or "GET").upper()
            observe_request(method, path, status_code)
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in (scope.get("headers") or [])
            }
            payload: dict[str, Any] = {
                "msg": "request",
                "method": method,
                "path": normalize_path(path),
                "status": status_code,
                "ms": ms,
            }
            user = headers.get("x-user-name") or ""
            org = headers.get("x-org-id") or ""
            if user:
                payload["user"] = user
            if org:
                payload["org_id"] = org
            log.info("%s", json.dumps(payload, default=str))


def redact(mapping: dict[str, Any] | None) -> dict[str, Any]:
    if not mapping:
        return {}
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        if str(key).lower() in _SECRET_KEYS:
            out[key] = "[redacted]"
        else:
            out[key] = value
    return out


def prometheus_text(
    *,
    job_queued: int,
    job_running: int,
    adapter_health: list[dict[str, Any]],
) -> str:
    lines = [
        "# HELP studio_http_requests_total HTTP requests by method, path template, and status.",
        "# TYPE studio_http_requests_total counter",
    ]
    for method, path, status, count in sorted(request_count_snapshot()):
        lines.append(
            f'studio_http_requests_total{{method="{_label(method)}",path="{_label(path)}",status="{_label(status)}"}} {count}'
        )
    lines.extend(
        [
            "# HELP studio_job_queue_depth Queued plus running job rows. Not a SaaS APM.",
            "# TYPE studio_job_queue_depth gauge",
            f"studio_job_queued {int(job_queued)}",
            f"studio_job_running {int(job_running)}",
            f"studio_job_queue_depth {int(job_queued) + int(job_running)}",
            "# HELP studio_adapter_health Adapter dry-run health (1=ok, 0=not). Stub is always 1.",
            "# TYPE studio_adapter_health gauge",
        ]
    )
    for row in adapter_health:
        adapter = _label(str(row.get("id") or "unknown"))
        ok = 1 if row.get("ok") else 0
        live = 1 if row.get("live") else 0
        lines.append(f'studio_adapter_health{{adapter="{adapter}",live="{live}"}} {ok}')
    lines.append("")
    return "\n".join(lines)


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
