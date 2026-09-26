"""Shared check for hosts that are cloud generation APIs.

Comfy lanes already refuse public addresses. This list is the extra stop for
well-known generation APIs, including a name someone put on
``STUDIO_COMFY_ALLOW_HOSTS``. Webhook posts use the same list. Brain-dump chat
and operator webhooks to other hosts are unchanged.
"""

from __future__ import annotations

CLOUD_GENERATION_HOSTS = (
    "api.x.ai",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "api.anthropic.com",
)


def is_cloud_generation_host(host: str | None) -> bool:
    name = (host or "").strip().lower().rstrip(".")
    if not name:
        return False
    return any(name == item or name.endswith("." + item) for item in CLOUD_GENERATION_HOSTS)
