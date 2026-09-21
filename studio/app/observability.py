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
from threading import Lock
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

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


class StructuredLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = time.perf_counter()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            ms = int((time.perf_counter() - started) * 1000)
            path = request.url.path
            method = request.method
            observe_request(method, path, status_code)
            user = request.headers.get("x-user-name") or ""
            org = request.headers.get("x-org-id") or ""
            payload: dict[str, Any] = {
                "msg": "request",
                "method": method,
                "path": normalize_path(path),
                "status": status_code,
                "ms": ms,
            }
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
