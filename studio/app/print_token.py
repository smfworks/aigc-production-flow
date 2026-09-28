"""Print the resolved API token for local Studio clients.

``scripts/dev-studio.sh`` captures this for ``VITE_API_TOKEN`` and
``VITE_STUDIO_TOKEN``. It does not invent a listen address.
"""

from __future__ import annotations

import sys

from .config import get_settings
from .runtime_security import StudioStartupError


def main() -> None:
    try:
        settings = get_settings()
    except StudioStartupError as exc:
        print(f"studio: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    sys.stdout.write(settings.api_token + "\n")


if __name__ == "__main__":
    main()
