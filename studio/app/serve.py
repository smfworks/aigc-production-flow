"""Start the Studio API on the resolved listen address.

Docker and ``scripts/dev-studio.sh`` use this module so the process bind
matches ``STUDIO_BIND_HOST``. The default is 127.0.0.1.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

from .config import get_settings
from .runtime_security import StudioStartupError


def main() -> None:
    try:
        settings = get_settings()
        port = _port()
    except StudioStartupError as exc:
        print(f"studio: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    reload = os.environ.get("STUDIO_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}
    app_dir = str(Path(__file__).resolve().parent)
    uvicorn.run(
        "app.main:app",
        host=settings.bind_host,
        port=port,
        reload=reload,
        reload_dirs=[app_dir] if reload else None,
    )


def _port() -> int:
    raw = (os.environ.get("STUDIO_PORT") or "8000").strip() or "8000"
    try:
        port = int(raw)
    except ValueError as exc:
        raise StudioStartupError(f"STUDIO_PORT {raw!r} is not an integer.") from exc
    if port < 1 or port > 65535:
        raise StudioStartupError(f"STUDIO_PORT {raw!r} is not a valid port.")
    return port


if __name__ == "__main__":
    main()
