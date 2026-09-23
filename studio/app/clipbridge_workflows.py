"""CLIP_BRIDGE Comfy API stubs. Inject paths and locked widgets. No queue.

Graphs live in ``studio/fixtures/clip_bridge/workflows/``. ``_clip_bridge.inject``
is the writable set. Role-tag titles stay the Phase 14 contract. This module
does not POST ``/prompt`` and does not invent an MP4.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

_INJECT = re.compile(r"^([A-Za-z0-9_-]+)\.inputs\.(.+)$")
_IMAGE_SLOT = re.compile(r"<image\d+>")

STUB_DIR_NAME = "workflows"
PREFERRED_MOTION = "h3_fl2va_api"
H3_API_CLASS = "MinimaxHailuo03FirstLastFrameNode"
H3_NATIVE_CLASS = "MiniMaxH3ImageToVideo"
QWEN_IDS = frozenset({"qwen_t2i_sheet", "qwen_edit_start", "qwen_edit_end"})
EDIT_IDS = frozenset({"qwen_edit_start", "qwen_edit_end"})
CANVAS_IDS = frozenset({"resize_lock", "qwen_t2i_sheet", "qwen_edit_start", "qwen_edit_end", PREFERRED_MOTION})
NATIVE_CANVASES = frozenset({(1344, 768), (2560, 1440)})
_SAMPLER_FIELDS = frozenset({"steps", "cfg", "sampler_name", "scheduler", "denoise"})
_BANNED_CLASS_TOKENS = ("concat", "ffmpeg", "extract")

QWEN_LOCK = {
    "steps": 25,
    "cfg": 1,
    "sampler_name": "euler",
    "scheduler": "simple",
    "denoise": 1,
}

QUEUE_FALLBACK = (
    "If a stub fails to queue on ComfyUI, import the official template and patch widgets only: "
    "Qwen T2I templates/image_qwen_image_2_1_t2i.json, "
    "Qwen Edit templates/image_qwen_image_2_1_image_edit.json, "
    "H3 FLF2V templates/api_minimax_h3_flf2v.json. "
    "Do not rebuild the graph. Extract and stitch stay on ffmpeg "
    "(studio/scripts/clip_bridge_conform.sh, docs/CLIP_BRIDGE.md §12)."
)


class ClipBridgeWorkflowError(ValueError):
    """The stub cannot be read or the inject would break a lock."""


def stub_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "clip_bridge" / STUB_DIR_NAME


def stub_ids() -> list[str]:
    return sorted(path.stem for path in stub_dir().glob("*.json"))


def is_stub(workflow_id: str) -> bool:
    return (workflow_id or "").strip() in set(stub_ids())


def is_clip_bridge_graph(graph: Any) -> bool:
    if not isinstance(graph, dict):
        return False
    meta = graph.get("_clip_bridge")
    return isinstance(meta, dict) and isinstance(meta.get("inject"), list)


def role_registry_refusal(workflow_id: str) -> str | None:
    """Phase 14 ids are title-addressed. These stubs are not."""
    workflow_id = (workflow_id or "").strip()
    if not is_stub(workflow_id):
        return None
    return (
        f"{workflow_id} is a CLIP_BRIDGE API stub addressed by _clip_bridge.inject, "
        "not a role-tagged workflow. "
        f"GET /api/clip-bridge/workflows/{workflow_id} reads it. "
        f"POST /api/clip-bridge/workflows/{workflow_id}/inject fills those paths and does not queue. "
        "Extract and stitch stay on ffmpeg. "
        + QUEUE_FALLBACK
    )


def parse_inject_path(path: str) -> tuple[str, str]:
    match = _INJECT.match((path or "").strip())
    if not match:
        raise ClipBridgeWorkflowError(f"Inject path {path!r} must look like 10.inputs.prompt.")
    return match.group(1), match.group(2)


def load_stub(workflow_id: str) -> dict[str, Any]:
    workflow_id = (workflow_id or "").strip()
    path = stub_dir() / f"{workflow_id}.json"
    if not path.is_file():
        raise ClipBridgeWorkflowError(f"No CLIP_BRIDGE stub named {workflow_id}.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ClipBridgeWorkflowError(f"{workflow_id} is not valid JSON.") from exc
    if not isinstance(data, dict) or not is_clip_bridge_graph(data):
        raise ClipBridgeWorkflowError(f"{workflow_id} is missing _clip_bridge.inject.")
    meta = data["_clip_bridge"]
    if meta.get("id") not in {None, "", workflow_id} and meta.get("id") != workflow_id:
        raise ClipBridgeWorkflowError(
            f"{workflow_id} _clip_bridge.id is {meta.get('id')!r}."
        )
    for item in meta["inject"]:
        node_id, field = parse_inject_path(str(item))
        node = data.get(node_id)
        inputs = node.get("inputs") if isinstance(node, dict) else None
        if not isinstance(inputs, dict) or field not in inputs:
            raise ClipBridgeWorkflowError(f"{workflow_id} inject {item} is not an input on the graph.")
    return data


def _nodes(graph: dict[str, Any]):
    for node_id, node in graph.items():
        if str(node_id).startswith("_") or not isinstance(node, dict):
            continue
        yield str(node_id), node


def _same(value: Any, expected: int | str) -> bool:
    if isinstance(expected, str):
        return value == expected
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return float(value) == float(expected)


def _find_class(graph: dict[str, Any], class_type: str) -> tuple[str, dict[str, Any]] | None:
    for node_id, node in _nodes(graph):
        if node.get("class_type") == class_type:
            return node_id, node
    return None


def _inputs(node: dict[str, Any]) -> dict[str, Any]:
    raw = node.get("inputs")
    return raw if isinstance(raw, dict) else {}


def _div32(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    number = float(value)
    return number > 0 and number % 32 == 0 and number == int(number)


def _is_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2


def scope_issues(graph: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for node_id, node in _nodes(graph):
        name = str(node.get("class_type") or "")
        lowered = name.lower()
        if any(token in lowered for token in _BANNED_CLASS_TOKENS):
            issues.append(
                f"Node {node_id} class {name} is extract or stitch. Those stay on ffmpeg."
            )
    return issues


def image_slots(graph: dict[str, Any]) -> dict[str, list[str]]:
    api: list[str] = []
    prompt: list[str] = []
    for _node_id, node in _nodes(graph):
        inputs = _inputs(node)
        for key in inputs:
            if str(key).startswith("images.image_"):
                api.append(str(key))
        text = inputs.get("prompt")
        if isinstance(text, str):
            prompt.extend(_IMAGE_SLOT.findall(text))
    return {"api": sorted(set(api)), "prompt": prompt}


def _qwen_sampler(graph: dict[str, Any]) -> dict[str, Any] | None:
    found = _find_class(graph, "KSampler")
    if found is None:
        return None
    return dict(_inputs(found[1]))


def invariant_issues(graph: dict[str, Any], workflow_id: str) -> list[str]:
    """Locks inject must not break. Canvas size may follow the story lock."""
    issues = scope_issues(graph)
    if workflow_id in QWEN_IDS:
        found = _find_class(graph, "KSampler")
        if found is None:
            issues.append("Qwen graph has no KSampler.")
        else:
            node_id, node = found
            inputs = _inputs(node)
            for key, expected in QWEN_LOCK.items():
                if not _same(inputs.get(key), expected):
                    issues.append(
                        f"Node {node_id} inputs.{key} is {inputs.get(key)!r}. Qwen lock is {expected}."
                    )
    if workflow_id in EDIT_IDS:
        found = _find_class(graph, "TextEncodeQwenImage21")
        if found is None:
            issues.append("Edit graph has no TextEncodeQwenImage21.")
        else:
            node_id, node = found
            inputs = _inputs(node)
            if not _same(inputs.get("resolution"), 0):
                issues.append(
                    f"Node {node_id} inputs.resolution is {inputs.get('resolution')!r}. Edit lock is 0."
                )
            prompt = str(inputs.get("prompt") or "")
            if "<image1>" not in prompt:
                issues.append("Edit prompt text must keep <image1>. API slots stay images.image_N.")
            for slot in ("images.image_1", "images.image_2", "images.image_3"):
                if slot not in inputs:
                    issues.append(f"Edit graph is missing {slot}.")
    if workflow_id == PREFERRED_MOTION:
        found = _find_class(graph, H3_API_CLASS)
        if found is None:
            issues.append(f"H3 API graph has no {H3_API_CLASS}.")
        else:
            node_id, node = found
            inputs = _inputs(node)
            expected = {
                "model": "MiniMax H3",
                "resolution": "2K",
                "duration": 10,
                "prompt_expansion_mode": "balanced",
                "watermark": False,
            }
            for key, value in expected.items():
                current = inputs.get(key)
                if isinstance(value, str):
                    ok = current == value
                elif value is False:
                    ok = current is False
                else:
                    ok = _same(current, value)
                if not ok:
                    issues.append(f"Node {node_id} inputs.{key} is {current!r}. H3 API lock is {value!r}.")
    if workflow_id == "h3_fl2va_native":
        found = _find_class(graph, H3_NATIVE_CLASS)
        if found is None:
            issues.append(f"Native H3 graph has no {H3_NATIVE_CLASS}.")
        else:
            node_id, node = found
            inputs = _inputs(node)
            pair = (inputs.get("width"), inputs.get("height"))
            if pair not in NATIVE_CANVASES:
                issues.append(
                    f"Node {node_id} canvas is {pair[0]}×{pair[1]}. "
                    "Native H3 stays 1344×768, or 2560×1440 when the local build accepts it."
                )
            if not _same(inputs.get("length"), 243):
                issues.append(
                    f"Node {node_id} inputs.length is {inputs.get('length')!r}. Native H3 length stays 243."
                )
            if not _is_link(inputs.get("first_frame")) or not _is_link(inputs.get("last_frame")):
                issues.append(f"Node {node_id} first_frame and last_frame must both stay connected.")
    return issues


def default_issues(graph: dict[str, Any], workflow_id: str) -> list[str]:
    """Checked-in widget defaults. Inject may replace a story-lock canvas."""
    issues: list[str] = []
    if workflow_id in CANVAS_IDS:
        seen = False
        for node_id, node in _nodes(graph):
            if node.get("class_type") not in {"ImageScale", "EmptyLatentImage"}:
                continue
            seen = True
            inputs = _inputs(node)
            if inputs.get("width") != 2560 or inputs.get("height") != 1440:
                issues.append(
                    f"Node {node_id} canvas is {inputs.get('width')}×{inputs.get('height')}. "
                    "Checked-in default is 2560×1440."
                )
        if not seen:
            issues.append(f"{workflow_id} has no ImageScale or EmptyLatentImage canvas.")
    if workflow_id == "resize_lock":
        found = _find_class(graph, "ImageScale")
        if found is None:
            issues.append("resize_lock has no ImageScale.")
        else:
            inputs = _inputs(found[1])
            if inputs.get("upscale_method") != "lanczos" or inputs.get("crop") != "center":
                issues.append("resize_lock ImageScale stays lanczos / center.")
    if workflow_id == "h3_fl2va_native":
        found = _find_class(graph, H3_NATIVE_CLASS)
        if found is not None:
            inputs = _inputs(found[1])
            if inputs.get("width") != 1344 or inputs.get("height") != 768:
                issues.append("Checked-in native canvas is 1344×768 (768 short edge).")
    return issues


def locked_report(graph: dict[str, Any], workflow_id: str, *, defaults: bool) -> dict[str, Any]:
    issues = invariant_issues(graph, workflow_id)
    if defaults:
        issues.extend(default_issues(graph, workflow_id))
    qwen = _qwen_sampler(graph) if workflow_id in QWEN_IDS else None
    h3_api = None
    native = None
    if workflow_id == PREFERRED_MOTION:
        found = _find_class(graph, H3_API_CLASS)
        h3_api = dict(_inputs(found[1])) if found else None
    if workflow_id == "h3_fl2va_native":
        found = _find_class(graph, H3_NATIVE_CLASS)
        native = dict(_inputs(found[1])) if found else None
    return {
        "ok": not issues,
        "issues": issues,
        "qwen": {key: (qwen or {}).get(key) for key in QWEN_LOCK} if qwen is not None else None,
        "h3_api": h3_api,
        "h3_native": native,
    }


def _guide_locked_write(workflow_id: str, path: str, value: Any) -> bool:
    """Prose map names a few locked overwrites that are already the node defaults."""
    if workflow_id == PREFERRED_MOTION and path == "10.inputs.duration":
        return _same(value, 10)
    if workflow_id == PREFERRED_MOTION and path == "10.inputs.resolution":
        return value == "2K"
    if workflow_id in EDIT_IDS and path == "10.inputs.resolution":
        return _same(value, 0)
    return False


def _authorize_write(workflow_id: str, graph: dict[str, Any], path: str, value: Any) -> None:
    node_id, field = parse_inject_path(path)
    node = graph.get(node_id)
    inputs = node.get("inputs") if isinstance(node, dict) else None
    if not isinstance(inputs, dict) or field not in inputs:
        raise ClipBridgeWorkflowError(f"{path} is not an input on {workflow_id}.")
    if field in _SAMPLER_FIELDS:
        raise ClipBridgeWorkflowError(
            f"{path} is a locked sampler widget. Qwen stays steps 25, cfg 1, sampler euler, scheduler simple."
        )
    if workflow_id == PREFERRED_MOTION and field == "duration" and not _same(value, 10):
        raise ClipBridgeWorkflowError("H3 API duration stays 10.")
    if workflow_id == PREFERRED_MOTION and field == "resolution" and value != "2K":
        raise ClipBridgeWorkflowError("H3 API resolution stays 2K.")
    if workflow_id in EDIT_IDS and field == "resolution" and not _same(value, 0):
        raise ClipBridgeWorkflowError("Edit TextEncodeQwenImage21.resolution stays 0.")
    if workflow_id == "h3_fl2va_native" and field == "length" and not _same(value, 243):
        raise ClipBridgeWorkflowError("Native H3 length stays 243 (≈10.125s on the 17k+5 grid).")
    if field in {"width", "height"} and not _div32(value):
        raise ClipBridgeWorkflowError(f"{path} must be a positive multiple of 32.")
    if workflow_id in EDIT_IDS and field == "prompt" and "<image1>" not in str(value):
        raise ClipBridgeWorkflowError(
            "Edit prompt text must keep <image1>. API JSON slots stay images.image_1."
        )
    allowed = {str(item) for item in graph["_clip_bridge"]["inject"]}
    if path not in allowed and not _guide_locked_write(workflow_id, path, value):
        raise ClipBridgeWorkflowError(
            f"{path} is not an inject path on {workflow_id}. "
            "Overwrite only _clip_bridge.inject. Locked widgets stay at the CLIP_BRIDGE_COMFY defaults."
        )


def apply_inject(workflow_id: str, values: dict[str, Any] | None) -> dict[str, Any]:
    """Copy the stub and write inject paths. Does not call Comfy."""
    graph = load_stub(workflow_id)
    source = invariant_issues(graph, workflow_id) + default_issues(graph, workflow_id)
    if source:
        raise ClipBridgeWorkflowError(" ".join(source))
    filled = copy.deepcopy(graph)
    payload = values if isinstance(values, dict) else {}
    for path, value in payload.items():
        _authorize_write(workflow_id, filled, str(path), value)
        node_id, field = parse_inject_path(str(path))
        filled[node_id]["inputs"][field] = value
    drifted = invariant_issues(filled, workflow_id)
    if drifted:
        raise ClipBridgeWorkflowError(" ".join(drifted))
    return filled


def _class_types(graph: dict[str, Any]) -> list[str]:
    ordered = sorted(_nodes(graph), key=lambda item: (0, int(item[0])) if item[0].isdigit() else (1, item[0]))
    return [str(node.get("class_type") or "") for _node_id, node in ordered]


def summarize(graph: dict[str, Any], *, defaults: bool) -> dict[str, Any]:
    meta = graph.get("_clip_bridge") if isinstance(graph.get("_clip_bridge"), dict) else {}
    workflow_id = str(meta.get("id") or "")
    inject = [str(item) for item in meta.get("inject") or []]
    return {
        "id": workflow_id,
        "step": meta.get("step") or "",
        "purpose": meta.get("purpose") or "",
        "official_template": meta.get("official_template") or "",
        "preferred": workflow_id == PREFERRED_MOTION,
        "inject": inject,
        "inject_parsed": [
            {"path": path, "node_id": parse_inject_path(path)[0], "field": parse_inject_path(path)[1]}
            for path in inject
        ],
        "class_types": _class_types(graph),
        "image_slots": image_slots(graph),
        "locked": locked_report(graph, workflow_id, defaults=defaults),
        "called_comfy": False,
        "hermes_ran": False,
        "produced_mp4": False,
        "conform": "ffmpeg",
        "queue_fallback": QUEUE_FALLBACK,
    }


def catalog() -> dict[str, Any]:
    rows = []
    for workflow_id in stub_ids():
        rows.append(summarize(load_stub(workflow_id), defaults=True))
    return {
        "called_comfy": False,
        "hermes_ran": False,
        "produced_mp4": False,
        "conform": "ffmpeg",
        "preferred_motion": PREFERRED_MOTION,
        "queue_fallback": QUEUE_FALLBACK,
        "workflows": rows,
        "honesty": (
            "CLIP_BRIDGE Comfy stubs. Inject fills a copy of the graph. "
            "Comfy was not called. Hermes was not started. "
            "Extract and stitch stay on ffmpeg. No MP4 was invented."
        ),
    }


def detail(workflow_id: str) -> dict[str, Any]:
    graph = load_stub(workflow_id)
    body = summarize(graph, defaults=True)
    body["graph"] = graph
    return body
