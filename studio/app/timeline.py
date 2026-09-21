"""Assemble edit-list metadata for Resolve/CapCut import. Not an NLE."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from .models import Episode, MediaAsset, Shot
from .shots import continue_chains
from .store import get_store

DEFAULT_FPS = 24.0
DEFAULT_DURATION_S = 10.125


def _fps(pack: dict[str, Any]) -> float:
    raw = pack.get("fps") if isinstance(pack, dict) else None
    try:
        value = float(raw)
        if value > 0:
            return value
    except (TypeError, ValueError):
        pass
    return DEFAULT_FPS


def _duration_s(shot: Shot, pack: dict[str, Any]) -> float:
    if shot.receipt and shot.receipt.duration_s:
        return float(shot.receipt.duration_s)
    if shot.receipt and shot.receipt.frames and shot.receipt.fps:
        return float(shot.receipt.frames) / float(shot.receipt.fps)
    rows = pack.get("editList") if isinstance(pack.get("editList"), list) else []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("id") or "") != shot.edit_row_id:
            continue
        try:
            dur = float(raw.get("durS") or 0)
            if dur > 0:
                return dur
        except (TypeError, ValueError):
            break
    return DEFAULT_DURATION_S


def _frames(shot: Shot, pack: dict[str, Any], fps: float) -> int:
    if shot.receipt and shot.receipt.frames:
        return int(shot.receipt.frames)
    return max(1, int(round(_duration_s(shot, pack) * fps)))


def _chain_index(chains: list[list[str]], shot_id: str) -> int:
    for index, chain in enumerate(chains):
        if shot_id in chain:
            return index + 1
    return 0


def _media_path(shot: Shot) -> str:
    receipt = shot.receipt
    if not receipt or not receipt.media:
        return ""
    asset: MediaAsset = receipt.media
    stored = asset.path or ""
    if not stored:
        return ""
    store = get_store()
    local = store.local_path(stored)
    if local is not None:
        return str(local.resolve())
    return stored


def _tc(frames: int, fps: float) -> str:
    fps_i = max(1, int(round(fps)))
    total = max(0, int(frames))
    ff = total % fps_i
    total //= fps_i
    ss = total % 60
    total //= 60
    mm = total % 60
    hh = total // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def _pack_of(episode: Episode) -> dict[str, Any]:
    if not episode.revisions:
        return {}
    pack = episode.revisions[0].pack_json
    return pack if isinstance(pack, dict) else {}


def shot_events(episode: Episode) -> dict[str, Any]:
    pack = _pack_of(episode)
    fps = _fps(pack)
    shots = list(episode.shots)
    chains, boundaries = continue_chains(shots)
    events: list[dict[str, Any]] = []
    rec = 0
    for shot in shots:
        frames = _frames(shot, pack, fps)
        src_out = frames
        rec_out = rec + frames
        events.append(
            {
                "shot_id": shot.id,
                "edit_row_id": shot.edit_row_id,
                "sort_index": shot.sort_index,
                "take": shot.take,
                "join": shot.join,
                "song_t": shot.song_t,
                "location_grade": shot.location_grade,
                "camera_verb": shot.camera_verb,
                "action": shot.action,
                "entities": shot.entities,
                "duration_s": _duration_s(shot, pack),
                "frames": frames,
                "fps": fps,
                "src_in": 0,
                "src_out": src_out,
                "rec_in": rec,
                "rec_out": rec_out,
                "src_in_tc": _tc(0, fps),
                "src_out_tc": _tc(src_out, fps),
                "rec_in_tc": _tc(rec, fps),
                "rec_out_tc": _tc(rec_out, fps),
                "continue_chain": _chain_index(chains, shot.id),
                "boundary": shot.join if shot.join in {"cut", "fadeblack"} else "",
                "media_path": _media_path(shot),
                "clip_name": _clip_name(shot),
            }
        )
        rec = rec_out
    return {
        "episode_id": episode.id,
        "title": episode.title,
        "project_id": episode.project_id,
        "fps": fps,
        "continue_chains": chains,
        "boundaries": boundaries,
        "events": events,
        "assembled_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Metadata-only timeline from the edit list and continue chains. "
            "Not a full NLE. Media paths appear when a hop-1 preview receipt is attached."
        ),
    }


def _clip_name(shot: Shot) -> str:
    take = (shot.take or "AX").strip() or "AX"
    return f"take-{take}-shot{shot.sort_index + 1:02d}"


def render_edl(episode: Episode) -> str:
    body = shot_events(episode)
    lines = [
        f"TITLE: {episode.title or 'AIGC episode'}",
        "FCM: NON-DROP FRAME",
        "",
    ]
    for index, event in enumerate(body["events"], start=1):
        reel = (event["take"] or "AX")[:8].upper() or "AX"
        lines.append(
            f"{index:03d}  {reel:<8} V     C        "
            f"{event['src_in_tc']} {event['src_out_tc']} "
            f"{event['rec_in_tc']} {event['rec_out_tc']}"
        )
        lines.append(f"* FROM CLIP NAME: {event['clip_name']}")
        join = event["join"] or "join"
        chain = event["continue_chain"]
        comment = f"join={join} continue-chain={chain}"
        if event["song_t"]:
            comment += f" song_t={event['song_t']}"
        if event["camera_verb"]:
            comment += f" camera={event['camera_verb']}"
        lines.append(f"* COMMENT: {comment}")
        if event["media_path"]:
            lines.append(f"* SOURCE FILE: {event['media_path']}")
        else:
            lines.append("* SOURCE FILE: (no preview receipt yet)")
        lines.append("")
    lines.append("* NOTE: CMX3600-ish EDL assembled from pack edit list. Not an NLE timeline.")
    return "\n".join(lines).rstrip() + "\n"


def render_fcpxml(episode: Episode) -> str:
    body = shot_events(episode)
    fps = int(round(float(body["fps"])))
    seq_name = escape(episode.title or "AIGC episode")
    clips: list[str] = []
    for event in body["events"]:
        name = escape(str(event["clip_name"]))
        path = event["media_path"]
        pathurl = escape(f"file://{path}") if path else ""
        file_xml = (
            f"            <file id=\"file-{event['sort_index']}\">\n"
            f"              <name>{name}</name>\n"
            + (f"              <pathurl>{pathurl}</pathurl>\n" if pathurl else "")
            + "            </file>\n"
            if path
            else ""
        )
        clips.append(
            "          <clipitem>\n"
            f"            <name>{name}</name>\n"
            f"            <start>{event['rec_in']}</start>\n"
            f"            <end>{event['rec_out']}</end>\n"
            f"            <in>{event['src_in']}</in>\n"
            f"            <out>{event['src_out']}</out>\n"
            f"{file_xml}"
            f"            <comment>join={escape(str(event['join']))} chain={event['continue_chain']}</comment>\n"
            "          </clipitem>"
        )
    clip_block = "\n".join(clips)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!DOCTYPE xmeml>\n"
        '<xmeml version="4">\n'
        "  <sequence>\n"
        f"    <name>{seq_name}</name>\n"
        "    <rate>\n"
        f"      <timebase>{fps}</timebase>\n"
        "      <ntsc>FALSE</ntsc>\n"
        "    </rate>\n"
        "    <media>\n"
        "      <video>\n"
        "        <track>\n"
        f"{clip_block}\n"
        "        </track>\n"
        "      </video>\n"
        "    </media>\n"
        "    <comment>FCP XML lite from AIGC studio. Metadata only — not a full NLE.</comment>\n"
        "  </sequence>\n"
        "</xmeml>\n"
    )


def render_playlist(episode: Episode) -> dict[str, Any]:
    body = shot_events(episode)
    return {
        "format": "aigc-shot-playlist",
        "version": 1,
        "nle": "resolve-or-capcut-import",
        "episode_id": body["episode_id"],
        "project_id": body["project_id"],
        "title": body["title"],
        "fps": body["fps"],
        "continue_chains": body["continue_chains"],
        "boundaries": body["boundaries"],
        "shots": [
            {
                "sort_index": event["sort_index"],
                "edit_row_id": event["edit_row_id"],
                "take": event["take"],
                "join": event["join"],
                "song_t": event["song_t"],
                "duration_s": event["duration_s"],
                "frames": event["frames"],
                "rec_in_tc": event["rec_in_tc"],
                "rec_out_tc": event["rec_out_tc"],
                "continue_chain": event["continue_chain"],
                "media_path": event["media_path"] or None,
                "clip_name": event["clip_name"],
                "action": event["action"],
                "camera_verb": event["camera_verb"],
                "location_grade": event["location_grade"],
            }
            for event in body["events"]
        ],
        "note": body["note"],
        "assembled_at": body["assembled_at"],
    }


def playlist_json(episode: Episode) -> str:
    return json.dumps(render_playlist(episode), indent=2) + "\n"
