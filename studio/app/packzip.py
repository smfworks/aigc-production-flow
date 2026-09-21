"""Pack zip is the collaboration contract. Studio stores pack.json + the zip bytes."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any


class PackZipError(ValueError):
    pass


# Pack zips are JSON contracts, not media libraries. Cap both the archive and pack.json.
MAX_PACK_ZIP_BYTES = 32 * 1024 * 1024
MAX_PACK_JSON_BYTES = 8 * 1024 * 1024


def _basename(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1]


def safe_filename(name: str, fallback: str = "download.bin") -> str:
    """Strip path and header characters from a download name."""
    base = _basename(name or "").replace("\r", "").replace("\n", "").replace('"', "")
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in base).strip(" .")
    return (cleaned[:180] or fallback)


def extract_pack_json(data: bytes) -> dict[str, Any]:
    if len(data) > MAX_PACK_ZIP_BYTES:
        raise PackZipError("Pack zip is too large.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise PackZipError("Not a zip file.") from exc

    json_path = next(
        (
            name
            for name in archive.namelist()
            if not name.endswith("/") and _basename(name) == "pack.json"
        ),
        None,
    )
    if not json_path:
        raise PackZipError("No pack.json in this zip. Re-export from the pack builder to round-trip.")
    info = archive.getinfo(json_path)
    if info.file_size > MAX_PACK_JSON_BYTES:
        raise PackZipError("pack.json is too large.")
    try:
        text = archive.read(json_path).decode("utf-8")
        parsed = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackZipError("pack.json is not valid JSON.") from exc

    if isinstance(parsed, dict) and isinstance(parsed.get("pack"), dict):
        return parsed["pack"]
    if isinstance(parsed, dict) and "logLine" in parsed:
        return parsed
    raise PackZipError("pack.json is not a capture pack.")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def slugify(raw: str, fallback: str = "untitled-pack") -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (raw or ""))
    slug = "-".join(part for part in cleaned.split("-") if part)[:60]
    return slug or fallback
