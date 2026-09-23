"""Comfy API-format workflows addressed by role tags, not node ids.

A node title such as ``Char Ref (Input:character)`` or ``Clip (Output:video)``
is the contract. New graphs are filled by those roles. The measured H3 and
Qwen builders stay as they are; this module does not replace them unless a
job names a registered workflow.
"""

from __future__ import annotations

import copy
import re
from typing import Any

_TAG = re.compile(r"\((Input|Output):([A-Za-z0-9_-]+)\)", re.IGNORECASE)
_PROFILE = re.compile(r"\((Profile):([A-Za-z0-9_-]+)\)", re.IGNORECASE)

# Canonical roles the desk knows how to fill. Aliases fold into these.
CANONICAL_ROLES = (
    "prompt",
    "negative",
    "width",
    "height",
    "character",
    "location",
    "image",
    "video",
    "audio",
    "seed",
    "duration",
)

_ALIASES = {
    "prompt": "prompt",
    "positive": "prompt",
    "text": "prompt",
    "negative": "negative",
    "neg": "negative",
    "width": "width",
    "height": "height",
    "character": "character",
    "identity": "character",
    "char": "character",
    "location": "location",
    "env": "location",
    "environment": "location",
    "image": "image",
    "img": "image",
    "video": "video",
    "clip": "video",
    "audio": "audio",
    "sound": "audio",
    "seed": "seed",
    "duration": "duration",
    "seconds": "duration",
    "length": "duration",
}

_ROLE_KEYS = {
    "prompt": ("text", "prompt", "string", "value"),
    "negative": ("text", "prompt", "string", "value"),
    "width": ("width",),
    "height": ("height",),
    "character": ("image", "images", "filename", "path"),
    "location": ("image", "images", "filename", "path"),
    "image": ("image", "images", "filename", "path"),
    "video": ("video", "filename", "path", "image"),
    "audio": ("audio", "filename", "path"),
    "seed": ("seed", "noise_seed", "value"),
    "duration": ("duration", "seconds", "length", "value"),
}

H3_SECTIONS = (
    "subject_definitions",
    "spatial_layout",
    "action",
    "camera",
    "lighting_and_style",
    "non_diegetic_music",
)

_H3_LABELS = {
    "subject_definitions": "Subject definitions",
    "spatial_layout": "Spatial layout",
    "action": "Action",
    "camera": "Camera",
    "lighting_and_style": "Lighting and style",
    "non_diegetic_music": "Non-diegetic music",
}

_H3_PROFILES = {"h3", "h3-6", "h3_6", "minimax-h3"}


class RoleWorkflowError(ValueError):
    """The graph cannot be used as a role-tagged workflow."""


def canonical_role(raw: str) -> str | None:
    key = (raw or "").strip().lower()
    if not key:
        return None
    return _ALIASES.get(key)


def _node_title(node: dict[str, Any]) -> str:
    meta = node.get("_meta")
    if isinstance(meta, dict) and meta.get("title"):
        return str(meta.get("title") or "")
    return str(node.get("title") or "")


def _sort_key(node_id: str) -> tuple[int, str]:
    if node_id.isdigit():
        return (0, f"{int(node_id):08d}")
    return (1, node_id)


def parse_workflow(graph: dict[str, Any]) -> dict[str, Any]:
    """Read ``(Input:role)`` / ``(Output:role)`` tags. Node ids are discovered."""
    if not isinstance(graph, dict) or not graph:
        raise RoleWorkflowError("Workflow JSON must be a non-empty object of nodes.")
    slots: list[dict[str, Any]] = []
    profiles: list[str] = []
    for node_id, node in graph.items():
        if str(node_id).startswith("_"):
            continue
        if not isinstance(node, dict):
            raise RoleWorkflowError(f"Node {node_id} is not an object.")
        title = _node_title(node)
        for match in _PROFILE.finditer(title):
            name = match.group(2).strip().lower()
            if name and name not in profiles:
                profiles.append(name)
        for match in _TAG.finditer(title):
            direction = match.group(1).lower()
            role = match.group(2).strip().lower()
            slots.append(
                {
                    "node_id": str(node_id),
                    "direction": direction,
                    "role": role,
                    "canonical": canonical_role(role),
                    "title": title,
                    "class_type": str(node.get("class_type") or ""),
                }
            )
    if not slots:
        raise RoleWorkflowError(
            "No (Input:role) or (Output:role) title tags. "
            "Node ids are not a contract. Title a node like Prompt (Input:prompt)."
        )
    slots.sort(key=lambda slot: (_sort_key(slot["node_id"]), slot["direction"], slot["role"]))
    prompt_profile = ""
    if any(name in _H3_PROFILES for name in profiles):
        prompt_profile = "h3"
    inputs: dict[str, list[str]] = {}
    for slot in slots:
        if slot["direction"] != "input":
            continue
        key = slot["canonical"] or slot["role"]
        inputs.setdefault(key, []).append(slot["node_id"])
    return {
        "slots": slots,
        "profiles": profiles,
        "prompt_profile": prompt_profile,
        "has_video_input": "video" in inputs,
        "inputs_by_role": inputs,
        "asks_h3": prompt_profile == "h3",
    }


def _primary_key(node: dict[str, Any], canonical: str | None) -> str:
    inputs = node.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
        node["inputs"] = inputs
    keys = _ROLE_KEYS.get(canonical or "", ())
    for key in keys:
        if key in inputs:
            return key
    if keys:
        return keys[0]
    for key, value in inputs.items():
        if isinstance(value, (str, int, float)) or value in {None, ""}:
            return key
    return "value"


def _take(values: dict[str, Any], canonical: str | None, role: str, index: int) -> Any:
    if canonical and canonical in values:
        raw = values[canonical]
    elif role in values:
        raw = values[role]
    else:
        return None
    if isinstance(raw, list):
        if index >= len(raw):
            return None
        return raw[index]
    if index > 0 and canonical in {"image", "character", "location"}:
        return None
    return raw


def fill_workflow(graph: dict[str, Any], values: dict[str, Any] | None) -> dict[str, Any]:
    """Copy the graph and write role values into the tagged nodes.

    Node ids are whatever the file used. Nothing here addresses ``"1"`` or ``"3"``.
    """
    contract = parse_workflow(graph)
    filled = copy.deepcopy(graph)
    seen: dict[str, int] = {}
    payload = values if isinstance(values, dict) else {}
    for slot in contract["slots"]:
        if slot["direction"] != "input":
            continue
        key = slot["canonical"] or slot["role"]
        index = seen.get(key, 0)
        seen[key] = index + 1
        value = _take(payload, slot["canonical"], slot["role"], index)
        if value is None:
            continue
        node = filled.get(slot["node_id"])
        if not isinstance(node, dict):
            raise RoleWorkflowError(f"Node {slot['node_id']} disappeared while filling.")
        field = _primary_key(node, slot["canonical"])
        node.setdefault("inputs", {})
        if isinstance(node["inputs"], dict):
            node["inputs"][field] = value
    return filled


def h3_sections(
    *,
    prompt: str = "",
    subjects: str = "",
    location: str = "",
    action: str = "",
    camera: str = "",
    look: str = "",
    audio: str = "",
) -> dict[str, str]:
    """Structured 6-section profile. No model is called."""
    text = (prompt or "").strip()
    return {
        "subject_definitions": (subjects or "").strip() or "No locked subject was named.",
        "spatial_layout": (location or "").strip() or "Location not specified.",
        "action": (action or "").strip() or text or "Action not specified.",
        "camera": (camera or "").strip() or "Camera not specified.",
        "lighting_and_style": (look or "").strip() or "Look not specified.",
        "non_diegetic_music": (audio or "").strip() or "No score unless the brief names one.",
    }


def h3_profile_text(sections: dict[str, str]) -> str:
    blocks = []
    for key in H3_SECTIONS:
        blocks.append(f"{_H3_LABELS[key]}:\n{sections.get(key) or ''}".rstrip())
    return "\n\n".join(blocks)


def values_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a job payload onto canonical role values. Missing keys stay absent."""
    body = payload if isinstance(payload, dict) else {}
    values: dict[str, Any] = {}
    prompt = str(body.get("prompt") or body.get("text") or "").strip()
    if prompt:
        values["prompt"] = prompt
    negative = str(body.get("negative") or "").strip()
    if negative:
        values["negative"] = negative
    for key in ("width", "height", "seed", "duration", "character", "location", "image", "video", "audio"):
        if key in body and body.get(key) not in {None, ""}:
            values[key] = body.get(key)
    seconds = body.get("seconds", body.get("duration_s"))
    if "duration" not in values and seconds not in {None, ""}:
        values["duration"] = seconds
    refs = body.get("refs")
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            role = canonical_role(str(ref.get("role") or "")) or str(ref.get("role") or "").strip().lower()
            value = ref.get("value")
            if not role or value in {None, ""}:
                continue
            if role in {"image", "character", "location"} and role in values and not isinstance(values[role], list):
                values[role] = [values[role], value]
            elif role in {"image", "character", "location"} and isinstance(values.get(role), list):
                values[role].append(value)
            else:
                values.setdefault(role, value)
    return values
