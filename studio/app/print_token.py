"""Print the resolved API token for local Studio clients.

``scripts/dev-studio.sh`` captures the token for ``VITE_API_TOKEN`` and
``VITE_STUDIO_TOKEN``. ``--path`` prints the token file path and not the
secret. It does not invent a listen address.
"""

from __future__ import annotations

import sys

from .config import get_settings
from .runtime_security import StudioStartupError, token_file_path, token_source


def main() -> None:
    try:
        settings = get_settings()
    except StudioStartupError as exc:
        print(f"studio: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if "--path" in sys.argv[1:]:
        if token_source(settings) == "env":
            sys.stdout.write("STUDIO_API_TOKEN is set; value not printed\n")
        else:
            sys.stdout.write(str(token_file_path(settings)) + "\n")
        return
    sys.stdout.write(settings.api_token + "\n")


if __name__ == "__main__":
    main()
