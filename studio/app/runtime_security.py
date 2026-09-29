"""API token and listen-address policy.

No shipped default token. An unset ``STUDIO_API_TOKEN`` is generated on first
use and stored mode 0600. The retired value ``local-dev-token`` refuses
startup. The process listens on 127.0.0.1 unless the operator opts in and
sets a token in the environment.
"""

from __future__ import annotations

import ipaddress
import os
import secrets
import stat
from pathlib import Path

from .config import Settings

RETIRED_API_TOKEN = "local-dev-token"
TOKEN_FILENAME = "studio.api-token"
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)

# Keyed by id(settings). apply_runtime_security overwrites the entry for each
# new Settings object before anyone reads it.
_sources: dict[int, str] = {}


class StudioStartupError(RuntimeError):
    """The API must not serve with this token or listen address."""


def token_source(settings: Settings) -> str:
    return _sources.get(id(settings), "")


def is_loopback_host(host: str | None) -> bool:
    name = (host or "").strip().lower()
    if name.startswith("[") and name.endswith("]"):
        name = name[1:-1]
    if "%" in name:
        name = name.split("%", 1)[0]
    if name == "localhost":
        return True
    try:
        parsed = ipaddress.ip_address(name)
    except ValueError:
        return False
    mapped = getattr(parsed, "ipv4_mapped", None)
    if mapped is not None:
        parsed = mapped
    return bool(parsed.is_loopback)


def apply_runtime_security(settings: Settings) -> None:
    host = (settings.bind_host or "").strip() or "127.0.0.1"
    settings.bind_host = host
    configured = (settings.api_token or "").strip()
    if configured:
        _refuse_retired(configured, "STUDIO_API_TOKEN")
        settings.api_token = configured
        source = "env"
    elif not is_loopback_host(host):
        # Refuse before creating a token file. A failed publish must not
        # leave a new secret on disk.
        source = "generated"
        _sources[id(settings)] = source
        _enforce_bind(settings, source)
        return
    else:
        source = _resolve_token(settings)
    _sources[id(settings)] = source
    _enforce_bind(settings, source)


def token_file_path(settings: Settings) -> Path:
    raw = (settings.token_file or "").strip()
    if raw:
        return Path(raw).expanduser()
    database = _sqlite_file(settings.database_url)
    if database is not None:
        return database.expanduser().resolve().parent / TOKEN_FILENAME
    media = Path(settings.media_root).expanduser()
    return media.resolve().parent / TOKEN_FILENAME


def _resolve_token(settings: Settings) -> str:
    """Load or create the on-disk token. Caller already handled an env token."""
    path = token_file_path(settings)
    if path.is_symlink() or _is_symlink(path):
        raise StudioStartupError(
            f"API token path {path} is a symlink. Refusing to follow it."
        )
    if path.exists():
        value = _read_token_file(path)
        _refuse_retired(value, f"Token file {path}")
        if not value:
            raise StudioStartupError(
                f"Token file {path} is empty. Delete it or set STUDIO_API_TOKEN."
            )
        settings.api_token = value
        return "file"
    value = secrets.token_urlsafe(32)
    _refuse_retired(value, "Generated API token")
    try:
        _create_token_file(path, value)
    except FileExistsError:
        value = _read_token_file(path)
        _refuse_retired(value, f"Token file {path}")
        if not value:
            raise StudioStartupError(
                f"Token file {path} is empty. Delete it or set STUDIO_API_TOKEN."
            ) from None
        settings.api_token = value
        return "file"
    settings.api_token = value
    return "generated"


def _enforce_bind(settings: Settings, source: str) -> None:
    host = (settings.bind_host or "").strip() or "127.0.0.1"
    settings.bind_host = host
    if is_loopback_host(host):
        return
    allow = bool(settings.allow_non_loopback)
    configured = source == "env"
    if allow and configured:
        return
    missing: list[str] = []
    if not allow:
        missing.append("set STUDIO_ALLOW_NON_LOOPBACK=1")
    if not configured:
        missing.append(
            "set STUDIO_API_TOKEN to a secret you choose "
            "(a token generated on first run stays on loopback)"
        )
    raise StudioStartupError(
        f"Refusing to listen on {host}. The default bind is 127.0.0.1. "
        f"A non-loopback bind requires you to {' and '.join(missing)}."
    )


def _refuse_retired(value: str, where: str) -> None:
    if value == RETIRED_API_TOKEN:
        raise StudioStartupError(
            f"{where} is the retired API token {RETIRED_API_TOKEN!r}. "
            "Studio will not start with that value. "
            "Unset STUDIO_API_TOKEN to generate a new one, or set a new secret."
        )


def _sqlite_file(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    raw = url.removeprefix("sqlite:///")
    if raw in {":memory:", ""} or raw.startswith("file:"):
        return None
    return Path(raw)


def _is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(path.lstat().st_mode)
    except OSError:
        return False


def _read_token_file(path: Path) -> str:
    if _is_symlink(path):
        raise StudioStartupError(
            f"API token path {path} is a symlink. Refusing to follow it."
        )
    try:
        fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except OSError as exc:
        raise StudioStartupError(f"Could not read API token file {path}: {exc}") from exc
    try:
        os.fchmod(fd, 0o600)
        mode = stat.S_IMODE(os.fstat(fd).st_mode)
        if mode & 0o077:
            raise StudioStartupError(
                f"API token file {path} is readable by group or other "
                "and could not be tightened to mode 0600."
            )
        data = os.read(fd, 8192)
        if len(data) == 8192 and os.read(fd, 1):
            raise StudioStartupError(f"API token file {path} is too long.")
    finally:
        os.close(fd)
    text = data.decode("utf-8", errors="replace")
    line = text.splitlines()[0].strip() if text.strip() else ""
    return line


def _create_token_file(path: Path, value: str) -> None:
    if _is_symlink(path):
        raise StudioStartupError(
            f"API token path {path} is a symlink. Refusing to follow it."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        raise
    except OSError as exc:
        raise StudioStartupError(f"Could not create API token file {path}: {exc}") from exc
    try:
        os.write(fd, (value + "\n").encode("utf-8"))
        os.fchmod(fd, 0o600)
        mode = stat.S_IMODE(os.fstat(fd).st_mode)
        if mode & 0o077:
            raise StudioStartupError(
                f"API token file {path} is readable by group or other "
                "and could not be tightened to mode 0600."
            )
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise StudioStartupError(f"API token path {path} is not a regular file.")
    except Exception:
        os.close(fd)
        path.unlink(missing_ok=True)
        raise
    os.close(fd)
