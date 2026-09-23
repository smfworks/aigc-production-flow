"""@Name bindings for Create prompts.

A token binds only when a cast identity or a sheet/plate asset already has that
name. Unmatched tokens stay unresolved. This does not create an asset.
"""

from __future__ import annotations

import re
from typing import Any

_AT = re.compile(r"(?<![\w@])@([A-Za-z][A-Za-z0-9_-]{0,40})")


def mention_tokens(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _AT.finditer(text or ""):
        token = match.group(1)
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(token)
    return found


def _cast_names(cast_notes: str) -> list[str]:
    notes = (cast_notes or "").strip()
    names: list[str] = []
    seen: set[str] = set()
    for line in notes.splitlines():
        row = line.strip().lstrip("-*").strip()
        if not row or row.lower().startswith("prop:"):
            continue
        if row.lower().startswith("character:"):
            row = row.split(":", 1)[1].strip()
        for sep in ("—", "–", " - ", ":"):
            if sep in row:
                row = row.split(sep, 1)[0].strip()
                break
        cleaned = row.strip(" .")[:80]
        key = cleaned.lower()
        if not cleaned or key in seen or key in {"character", "prop", "the", "a", "an"}:
            continue
        seen.add(key)
        names.append(cleaned)
    return names


def bind_subject_mentions(prompt: str, cast_notes: str) -> list[dict[str, Any]]:
    """Bind @tokens to cast identity drafts. Plates are not invented here."""
    slots = {name.lower(): name for name in _cast_names(cast_notes)}
    rows: list[dict[str, Any]] = []
    for token in mention_tokens(prompt):
        name = slots.get(token.lower(), "")
        rows.append(
            {
                "token": token,
                "name": name,
                "role": "identity" if name else "",
                "slot": "cast" if name else "",
                "bound": bool(name),
            }
        )
    return rows


def unresolved_mentions(answers: dict[str, Any] | None) -> list[str]:
    src = answers if isinstance(answers, dict) else {}
    refs = src.get("subject_refs")
    if not isinstance(refs, list):
        refs = bind_subject_mentions(str(src.get("prompt") or ""), str(src.get("cast_notes") or ""))
    tokens: list[str] = []
    for row in refs:
        if isinstance(row, dict) and row.get("token") and not row.get("bound"):
            tokens.append(str(row["token"]))
    return tokens


def asset_mention_refs(prompt: str, assets: list[Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Bind @tokens to existing sheet or plate assets. Other kinds are not slots."""
    refs: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for token in mention_tokens(prompt):
        match = None
        for asset in assets:
            kind = str(getattr(asset, "kind", "") or "")
            if kind not in {"sheet", "plate"}:
                continue
            label = str(getattr(asset, "entity_label", "") or "").strip()
            original = str(getattr(asset, "original_name", "") or "")
            stem = original.rsplit(".", 1)[0] if original else ""
            if token.lower() in {label.lower(), stem.lower()} and token.lower():
                match = asset
                break
        if match is None:
            unresolved.append(token)
            continue
        kind = str(getattr(match, "kind", "") or "")
        refs.append(
            {
                "role": "character" if kind == "sheet" else "image",
                "ref_role": "identity-lock" if kind == "sheet" else "",
                "label": str(getattr(match, "entity_label", "") or token),
                "value": str(getattr(match, "original_name", "") or ""),
                "media_id": getattr(match, "id", ""),
                "source": "mention",
                "token": token,
                "slot": kind,
                "bound": True,
            }
        )
    return refs, unresolved
