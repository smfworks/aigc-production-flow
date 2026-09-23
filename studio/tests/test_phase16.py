"""Phase 16: CLIP_BRIDGE Comfy stubs, inject paths, locked widgets, ffmpeg conform."""

from pathlib import Path

from app.adapters.base import JobContext
from app.adapters.comfy_h3 import start_clip
from app.adapters.comfy_qwen import generate_still
from app.clipbridge import CLIP_DURATION, alignment_line, assemble_h3_prompt, conform_plan, load_forge_fixture
from app.clipbridge_workflows import (
    H3_API_CLASS,
    H3_NATIVE_CLASS,
    apply_inject,
    load_stub,
    parse_inject_path,
    stub_ids,
)
from app.config import get_settings
from app.workflows import list_workflows

ROOT = Path(__file__).resolve().parents[2]
STUBS = Path(__file__).resolve().parents[1] / "fixtures" / "clip_bridge" / "workflows"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "clip_bridge_conform.sh"

EXPECTED = {
    "resize_lock",
    "qwen_t2i_sheet",
    "qwen_edit_start",
    "qwen_edit_end",
    "h3_fl2va_api",
    "h3_fl2va_native",
}


def _ctx(payload: dict) -> JobContext:
    return JobContext(
        job_id="job-phase16",
        job_type="still-sheet",
        episode_id="ep-1",
        shot_id=None,
        payload=payload,
        pack={},
        cancel_requested=lambda: False,
        set_progress=lambda _n: None,
    )


def test_resize_lock_inject_paths_parse():
    graph = load_stub("resize_lock")
    meta = graph["_clip_bridge"]
    assert meta["id"] == "resize_lock"
    assert meta["step"] == "pixel_lock"
    assert meta["inject"] == [
        "1.inputs.image",
        "2.inputs.width",
        "2.inputs.height",
        "3.inputs.filename_prefix",
    ]
    parsed = [parse_inject_path(path) for path in meta["inject"]]
    assert parsed == [("1", "image"), ("2", "width"), ("2", "height"), ("3", "filename_prefix")]
    assert graph["1"]["class_type"] == "LoadImage"
    assert graph["2"]["class_type"] == "ImageScale"
    assert graph["2"]["inputs"]["width"] == 2560
    assert graph["2"]["inputs"]["height"] == 1440
    assert graph["2"]["inputs"]["upscale_method"] == "lanczos"
    assert graph["2"]["inputs"]["crop"] == "center"
    assert graph["3"]["class_type"] == "SaveImage"
    filled = apply_inject("resize_lock", {"3.inputs.filename_prefix": "clipbridge/02/start_locked"})
    assert filled["3"]["inputs"]["filename_prefix"] == "clipbridge/02/start_locked"
    assert load_stub("resize_lock")["3"]["inputs"]["filename_prefix"] == "clipbridge/01/start_locked"


def test_qwen_and_h3_stubs_keep_locked_defaults_and_metadata():
    assert set(stub_ids()) == EXPECTED
    for workflow_id in ("qwen_t2i_sheet", "qwen_edit_start", "qwen_edit_end"):
        graph = load_stub(workflow_id)
        assert graph["_clip_bridge"]["id"] == workflow_id
        sampler = graph["30"]["inputs"]
        assert sampler["steps"] == 25
        assert sampler["cfg"] == 1
        assert sampler["sampler_name"] == "euler"
        assert sampler["scheduler"] == "simple"
        assert sampler["denoise"] == 1
        assert graph["30"]["class_type"] == "KSampler"
    for workflow_id in ("qwen_edit_start", "qwen_edit_end"):
        graph = load_stub(workflow_id)
        encode = graph["10"]["inputs"]
        assert encode["resolution"] == 0
        assert "images.image_1" in encode
        assert "images.image_2" in encode
        assert "images.image_3" in encode
        assert "<image1>" in encode["prompt"]
        assert "<image2>" in encode["prompt"]
        assert "image_1" not in encode["prompt"]
    api = load_stub("h3_fl2va_api")
    assert api["_clip_bridge"]["id"] == "h3_fl2va_api"
    assert api["10"]["class_type"] == H3_API_CLASS
    assert api["10"]["inputs"]["duration"] == 10
    assert api["10"]["inputs"]["resolution"] == "2K"
    assert api["10"]["inputs"]["model"] == "MiniMax H3"
    assert api["10"]["inputs"]["watermark"] is False
    assert api["10"]["inputs"]["prompt_expansion_mode"] == "balanced"
    native = load_stub("h3_fl2va_native")
    assert native["10"]["class_type"] == H3_NATIVE_CLASS
    assert native["10"]["inputs"]["width"] == 1344
    assert native["10"]["inputs"]["height"] == 768
    assert native["10"]["inputs"]["length"] == 243
    assert native["10"]["inputs"]["first_frame"] == ["1", 0]
    assert native["10"]["inputs"]["last_frame"] == ["2", 0]
    assert native["30"]["inputs"]["steps"] == 20
    assert native["30"]["inputs"]["sampler_name"] == "res_multistep"


def test_inject_refuses_locked_widgets_and_keeps_image_dialect():
    refused = None
    try:
        apply_inject("qwen_t2i_sheet", {"30.inputs.steps": 8})
    except ValueError as exc:
        refused = str(exc)
    assert refused and "locked sampler" in refused
    edit = apply_inject(
        "qwen_edit_start",
        {
            "10.inputs.prompt": "Using <image1> as identity lock. Hold the face.",
            "14.inputs.width": 2560,
            "14.inputs.height": 1440,
            "10.inputs.resolution": 0,
        },
    )
    assert edit["30"]["inputs"]["steps"] == 25
    assert edit["30"]["inputs"]["sampler_name"] == "euler"
    assert "images.image_1" in edit["10"]["inputs"]
    assert "<image1>" in edit["10"]["inputs"]["prompt"]
    missing_scale = None
    try:
        apply_inject("qwen_edit_start", {"12.inputs.width": 2560})
    except ValueError as exc:
        missing_scale = str(exc)
    assert missing_scale and "not an input" in missing_scale
    dropped = None
    try:
        apply_inject("qwen_edit_end", {"10.inputs.prompt": "A new face."})
    except ValueError as exc:
        dropped = str(exc)
    assert dropped and "<image1>" in dropped
    duration = None
    try:
        apply_inject("h3_fl2va_api", {"10.inputs.duration": 8})
    except ValueError as exc:
        duration = str(exc)
    assert duration and "duration stays 10" in duration
    held = apply_inject("h3_fl2va_api", {"10.inputs.duration": 10, "10.inputs.resolution": "2K"})
    assert held["10"]["inputs"]["duration"] == 10
    assert held["10"]["inputs"]["resolution"] == "2K"
    length = None
    try:
        apply_inject("h3_fl2va_native", {"10.inputs.length": 200})
    except ValueError as exc:
        length = str(exc)
    assert length and "243" in length


def test_assemble_h3_still_uses_10_00_from_clip_bridge():
    lock, clips = load_forge_fixture()
    spec_line = alignment_line()
    assert "10.00-second mark" in spec_line
    assert CLIP_DURATION == 10.0
    prompt = assemble_h3_prompt(lock, clips[0])
    assert prompt.startswith(spec_line + "\n\n")
    assert "10.00-second mark" in prompt
    assert clips[0].start_state in prompt
    assert clips[0].end_state in prompt


def test_extract_and_stitch_stay_on_ffmpeg():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "ffmpeg" in script
    assert "Extract and stitch stay on ffmpeg" in script
    _lock, clips = load_forge_fixture()
    plan = conform_plan(clips)
    assert plan["called_comfy"] is False
    assert plan["produced_mp4"] is False
    commands = [*plan["extract"], *plan["trim"], plan["concat"]]
    assert commands
    assert all(cmd[0] == "ffmpeg" for cmd in commands)
    for workflow_id in EXPECTED:
        for _node_id, node in load_stub(workflow_id).items():
            if not isinstance(node, dict):
                continue
            name = str(node.get("class_type") or "").lower()
            assert "concat" not in name
            assert "ffmpeg" not in name
            assert "extract" not in name


def test_docs_match_the_official_pack():
    spec = (ROOT / "docs" / "CLIP_BRIDGE.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "CLIP_BRIDGE_COMFY.md").read_text(encoding="utf-8")
    assert "## 20. ComfyUI workflow stubs" in spec
    assert "images.image_1" in spec
    assert "steps `25`" in guide
    assert "scheduler `simple`" in guide
    assert H3_API_CLASS in guide
    assert "duration `10`" in guide
    assert "resolution `2K`" in guide
    assert "Last-frame extraction (ffmpeg, not Comfy)" in guide
    assert "Concat / stitch (ffmpeg)" in guide
    for name in EXPECTED:
        assert (STUBS / f"{name}.json").is_file()
        assert f'"id": "{name}"' in (STUBS / f"{name}.json").read_text(encoding="utf-8")


def test_role_registry_does_not_swallow_clip_bridge_stubs():
    ids = {row["id"] for row in list_workflows()}
    assert "character-sheet" in ids
    assert "h3-extend" in ids
    assert EXPECTED.isdisjoint(ids)


def test_live_adapters_refuse_stubs_before_queue():
    settings = get_settings()
    still = generate_still(
        settings,
        _ctx({"prompt": "Mara waits.", "workflow_id": "qwen_t2i_sheet"}),
        role="sheet",
    )
    assert still.ok is False
    assert still.receipt["called_comfy"] is False
    assert "inject" in still.error
    assert "ffmpeg" in still.error
    clip = start_clip(
        settings,
        _ctx({"prompt": "Hold the anvil.", "workflow_id": "h3_fl2va_api"}),
    )
    assert clip.ok is False
    assert clip.receipt["called_comfy"] is False
    assert "h3_fl2va_api" in clip.error


def test_workflow_api_lists_locks_and_inject_does_not_enqueue(client, auth):
    listed = client.get("/api/clip-bridge/workflows", headers=auth)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["called_comfy"] is False
    assert body["produced_mp4"] is False
    assert body["conform"] == "ffmpeg"
    assert body["preferred_motion"] == "h3_fl2va_api"
    rows = {row["id"]: row for row in body["workflows"]}
    assert set(rows) == EXPECTED
    assert rows["h3_fl2va_api"]["preferred"] is True
    assert rows["h3_fl2va_native"]["preferred"] is False
    assert rows["resize_lock"]["inject"][0] == "1.inputs.image"
    assert rows["qwen_t2i_sheet"]["locked"]["ok"] is True
    assert rows["qwen_t2i_sheet"]["locked"]["qwen"]["steps"] == 25
    assert rows["qwen_t2i_sheet"]["locked"]["qwen"]["cfg"] == 1
    assert rows["qwen_t2i_sheet"]["locked"]["qwen"]["sampler_name"] == "euler"
    assert rows["qwen_t2i_sheet"]["locked"]["qwen"]["scheduler"] == "simple"
    assert rows["h3_fl2va_api"]["locked"]["h3_api"]["duration"] == 10
    assert rows["h3_fl2va_api"]["locked"]["h3_api"]["resolution"] == "2K"
    assert H3_API_CLASS in rows["h3_fl2va_api"]["class_types"]
    assert rows["qwen_edit_start"]["image_slots"]["api"] == [
        "images.image_1",
        "images.image_2",
        "images.image_3",
    ]
    assert "<image1>" in rows["qwen_edit_start"]["image_slots"]["prompt"]
    one = client.get("/api/clip-bridge/workflows/h3_fl2va_api", headers=auth)
    assert one.status_code == 200, one.text
    assert one.json()["graph"]["10"]["class_type"] == H3_API_CLASS
    assert one.json()["graph"]["_clip_bridge"]["inject"]
    injected = client.post(
        "/api/clip-bridge/workflows/qwen_t2i_sheet/inject",
        headers=auth,
        json={"values": {"10.inputs.prompt": "Photoreal sheet of Mara."}},
    )
    assert injected.status_code == 200, injected.text
    assert injected.json()["called_comfy"] is False
    assert injected.json()["produced_mp4"] is False
    assert injected.json()["graph"]["10"]["inputs"]["prompt"] == "Photoreal sheet of Mara."
    assert injected.json()["graph"]["30"]["inputs"]["steps"] == 25
    blocked = client.post(
        "/api/clip-bridge/workflows/qwen_edit_start/inject",
        headers=auth,
        json={"values": {"30.inputs.cfg": 4}},
    )
    assert blocked.status_code == 400, blocked.text
    role = client.get("/api/workflows/qwen_t2i_sheet", headers=auth)
    assert role.status_code == 400, role.text
    assert "inject" in role.json()["detail"]
    names = {row["id"] for row in client.get("/api/workflows", headers=auth).json()}
    assert "character-sheet" in names
    assert "qwen_t2i_sheet" not in names
