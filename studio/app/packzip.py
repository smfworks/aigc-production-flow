"""Pack zip is the collaboration contract. Studio stores pack.json + the zip bytes."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any


class PackZipError(ValueError):
    pass


def _basename(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1]


def extract_pack_json(data: bytes) -> dict[str, Any]:
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
