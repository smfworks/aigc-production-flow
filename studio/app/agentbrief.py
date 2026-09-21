"""Export a folder-like zip an agent can feed to Comfy MCP. Studio does not call Comfy here."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from .adapters.catalog import H3_FPS, H3_FRAMES, H3_WINDOW_S, QWEN_CANVAS, SLOT_BY_ID
from .adapters.registry import resolve_adapter_name
from .config import get_settings
from .models import Episode, MediaAsset, PackRevision
from .packzip import safe_filename, slugify
from .store import get_store

STAGES = ["script", "assets", "storyboard", "preview"]

README = """# Agent brief — feed Comfy MCP (stills, then clips)

This archive is the handoff for Hermes, OpenClaw, or a Grok bot. Studio did **not** call Comfy while building it. Pack zip remains the collaboration contract. This is not CapCut and not an MP4.

## Order

1. Read `agent-brief.json`. Jobs are ordered **still sheets, then still plates, then hop-1 clips**.
2. Feed the still factory first (documented slot `comfy-qwen`, canvas 1344×768). Sheets are the bible. Plates are the first frame of a window. Do not stretch 1024².
3. After plates exist, feed hop-1 clips (documented slot `comfy-h3`). Measured window on that slot: **10.125 s / 243 f @ 24 fps**. One hop-1 per take. Watch it before any extend.
4. `continue` keeps the motion-context latent (no new plate on hop 2+). `cut` and `fadeblack` need a new plate.

## Honesty

- `honesty.called_comfy` is false. Export does not generate.
- Adapter labels say **stub** or **live**. Unset `STUDIO_ADAPTER_WEBHOOK_URL` / `STUDIO_ADAPTER_CLI` means the live slot is **not live** and enqueue resolves to stub. Do not tell anyone H3 or Qwen ran.
- `generate_ready` is false here. `generate-ok` still needs green gates, hop-1 receipts, and a reviewer/producer sign-off.
- Approved identity plates are what plate-bind counts. Draft sheets do not.
- The Hermes plugin `smf-h3-capture` can stay. Studio is the primary place to create the pack.

## Files

- `pack.zip` — collaboration pack (pack.json inside)
- `pack.json` — capture pack
- `gate-snapshot.json` — gate checklist at export time
- `agent-brief.json` — episode id, stages, ordered jobs, window metadata, plate binds, adapter labels
"""


def _rows(pack: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = pack.get(key)
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def _label(configured: str, resolved: str) -> str:
    slot = SLOT_BY_ID.get(configured)
    if resolved == "stub":
        if configured in {"", "stub"}:
            return "stub"
        return f"stub ({configured} not live)"
    if slot and slot.live and resolved == configured:
        return "live"
    return resolved or "stub"


def _job(order: int, **fields: Any) -> dict[str, Any]:
    body = {"order": order}
    body.update(fields)
    return body


def build_agent_brief(episode: Episode, revision: PackRevision) -> dict[str, Any]:
    cfg = get_settings()
    project = episode.project
    pack = revision.pack_json if isinstance(revision.pack_json, dict) else {}
    still_configured = (project.still_adapter if project else "") or cfg.still_adapter or "stub"
    clip_configured = (project.clip_adapter if project else "") or cfg.clip_adapter or "stub"
    still_resolved = resolve_adapter_name("still-sheet", cfg, project=project)
    clip_resolved = resolve_adapter_name("clip-hop1", cfg, project=project)
    still_label = _label(still_configured, still_resolved)
    clip_label = _label(clip_configured, clip_resolved)

    jobs: list[dict[str, Any]] = []
    order = 1
    characters = _rows(pack, "characters")
    props = _rows(pack, "props")
    if not characters:
        characters = [{"name": "lead"}]
    if not props:
        props = [{"name": "prop"}]
    for card in characters:
        name = str(card.get("name") or "lead").strip() or "lead"
        jobs.append(
            _job(
                order,
                stage="stills",
                kind="still-sheet",
                subject=name,
                entity_kind="character",
                canvas=QWEN_CANVAS,
                adapter_slot="comfy-qwen",
                adapter_label=still_label,
                note="Character sheet before any plate. Not a generate from this export.",
            )
        )
        order += 1
    for card in props:
        name = str(card.get("name") or "prop").strip() or "prop"
        jobs.append(
            _job(
                order,
                stage="stills",
                kind="still-sheet",
                subject=name,
                entity_kind="prop",
                canvas=QWEN_CANVAS,
                adapter_slot="comfy-qwen",
                adapter_label=still_label,
                note="Prop sheet before any plate. Numbers stay on the prop card.",
            )
        )
        order += 1

    stills = _rows(pack, "stills")
    plate_cards = [
        row
        for row in stills
        if "plate" in str(row.get("role") or "").lower() or str(row.get("file") or "").strip()
    ]
    if not plate_cards:
        plate_cards = [{"entity": "window", "role": "hop-1 plate", "file": ""}]
    for card in plate_cards:
        jobs.append(
            _job(
                order,
                stage="stills",
                kind="still-plate",
                subject=str(card.get("entity") or "window"),
                role=str(card.get("role") or "hop-1 plate"),
                file=str(card.get("file") or ""),
                canvas=QWEN_CANVAS,
                adapter_slot="comfy-qwen",
                adapter_label=still_label,
                note="Plate is the first frame of this window, not the sheet.",
            )
        )
        order += 1

    takes = _rows(pack, "takes") or [{"take": "A", "hop1Mode": "", "hop1Plate": ""}]
    for take in takes:
        jobs.append(
            _job(
                order,
                stage="clips",
                kind="clip-hop1",
                take=str(take.get("take") or "A"),
                window_s=H3_WINDOW_S,
                frames=H3_FRAMES,
                fps=H3_FPS,
                adapter_slot="comfy-h3",
                adapter_label=clip_label,
                hop1_watch_required=True,
                mode=str(take.get("hop1Mode") or ""),
                plate=str(take.get("hop1Plate") or ""),
                note="Hop-1 after plates. Watch before extend. Live adapters must not skip the watch.",
            )
        )
        order += 1

    binds: list[dict[str, Any]] = []
    for asset in episode.media or []:
        if not isinstance(asset, MediaAsset):
            continue
        if asset.kind != "plate":
            continue
        binds.append(
            {
                "source": "identity",
                "media_id": asset.id,
                "entity_label": asset.entity_label,
                "shot_id": asset.shot_id,
                "edit_row_id": asset.edit_row_id,
                "approval_status": asset.approval_status,
                "counts_for_generate": asset.approval_status == "approved",
            }
        )
    for card in _rows(pack, "stills"):
        role = str(card.get("role") or "")
        if "plate" not in role.lower() and not str(card.get("file") or "").strip():
            continue
        binds.append(
            {
                "source": "pack",
                "entity": str(card.get("entity") or ""),
                "role": role,
                "file": str(card.get("file") or ""),
                "counts_for_generate": False,
                "note": "Pack still card. Only an approved identity plate counts for generate-ok.",
            }
        )

    meta = pack.get("studioMeta") if isinstance(pack.get("studioMeta"), dict) else {}
    return {
        "episode_id": episode.id,
        "project_id": episode.project_id,
        "episode_title": episode.title,
        "revision_id": revision.id,
        "stages": STAGES,
        "window": {
            "clip_slot": "comfy-h3",
            "window_s": H3_WINDOW_S,
            "frames": H3_FRAMES,
            "fps": H3_FPS,
            "still_slot": "comfy-qwen",
            "canvas": QWEN_CANVAS,
            "source": "measured Comfy hook metadata on the adapter catalog",
        },
        "jobs": jobs,
        "plate_binds": binds,
        "adapters": {
            "still": {
                "configured": still_configured,
                "resolved": still_resolved,
                "label": still_label,
            },
            "clip": {
                "configured": clip_configured,
                "resolved": clip_resolved,
                "label": clip_label,
            },
        },
        "honesty": {
            "called_comfy": False,
            "export_is_the_contract": True,
            "generate_ready": False,
            "all_gates_green": bool(revision.all_gates_green),
            "draft": meta.get("status") == "draft" or not revision.all_gates_green,
            "model_ran": bool(meta.get("model_ran")),
            "note": (
                "Export does not call Comfy. An agent feeds Comfy MCP stills then hop-1 clips. "
                "Stub labels mean the live hook is unset or this project is on the stub adapter."
            ),
        },
    }


def agent_zip_bytes(episode: Episode, revision: PackRevision) -> tuple[bytes, str]:
    pack = revision.pack_json if isinstance(revision.pack_json, dict) else {}
    brief = build_agent_brief(episode, revision)
    snapshot = revision.gate_snapshot if isinstance(revision.gate_snapshot, dict) else {}
    store = get_store()
    try:
        pack_zip = store.get_bytes(revision.zip_path) if revision.zip_path else b""
    except OSError:
        pack_zip = b""
    if not pack_zip:
        from .blankpack import pack_zip_bytes

        pack_zip = pack_zip_bytes(pack)
    slug = slugify(episode.title or "episode", "episode")
    filename = safe_filename(f"agent-{slug}.zip", "agent-episode.zip")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", README)
        archive.writestr("agent-brief.json", json.dumps(brief, indent=2))
        archive.writestr("gate-snapshot.json", json.dumps(snapshot, indent=2))
        archive.writestr("pack.json", json.dumps({"v": 2, "pack": pack}, indent=2, ensure_ascii=False))
        archive.writestr("pack.zip", pack_zip)
    return buf.getvalue(), filename
