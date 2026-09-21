"""Native ComfyUI still + clip engines. HTTP is mocked. No GPU."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.adapters.base import JobContext
from app.adapters.catalog import CATALOG, SLOT_BY_ID
from app.adapters.comfy_client import ComfyClient, ComfyError, first_images_output, validate_lane
from app.adapters.comfy_h3 import build_h3_graph, poll_clip, resolve_frames, start_clip
from app.adapters.comfy_qwen import build_qwen_graph, generate_still
from app.adapters.health import slot_health
from app.adapters.registry import resolve_adapter_name
from app.config import Settings, get_settings
from tests.helpers import create_episode, green_ready_episode

PNG = b"\x89PNG\r\n\x1a\nstill"
MP4 = b"\x00\x00\x00\x18ftypmp42clip"
STILL = "http://127.0.0.1:8190"
CLIP = "http://127.0.0.1:8188"
FILES = {"unet": "unet.safetensors", "clip": "clip.safetensors", "vae": "vae.safetensors"}
H3_FILES = {
    "unet_full": "h3-full.safetensors",
    "unet_turbo": "h3-turbo.safetensors",
    "clip": "h3-clip.safetensors",
    "video_vae": "video-vae.safetensors",
    "audio_vae": "audio-vae.safetensors",
}


def _ctx(job_type: str, payload=None) -> JobContext:
    return JobContext(
        job_id="job-live-1",
        job_type=job_type,
        episode_id="ep-1",
        shot_id="shot-1",
        payload=payload or {},
        pack={},
        cancel_requested=lambda: False,
        set_progress=lambda _value: None,
    )


def _settings(monkeypatch, tmp_path: Path) -> Settings:
    monkeypatch.setenv("STUDIO_MEDIA_ROOT", str(tmp_path / "media"))
    monkeypatch.setenv("STUDIO_COMFY_STILL_LANES", STILL)
    monkeypatch.setenv("STUDIO_COMFY_CLIP_LANES", CLIP)
    monkeypatch.setenv("STUDIO_COMFY_IMAGE_LANES_FOR_FREE", STILL)
    monkeypatch.setenv("STUDIO_COMFY_STILL_POLL_SECONDS", "0")
    monkeypatch.setenv("STUDIO_COMFY_POLL_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("STUDIO_COMFY_STILL_TIMEOUT_SECONDS", "2")
    monkeypatch.setenv("STUDIO_COMFY_H3_STYLES", "")
    get_settings.cache_clear()
    return get_settings()


def _queue(busy: bool = False) -> httpx.Response:
    running = [{"prompt_id": "busy"}] if busy else []
    return httpx.Response(200, json={"queue_running": running, "queue_pending": []})


def test_catalog_product_strings_do_not_use_harness_names():
    blob = json.dumps([slot.as_dict() for slot in CATALOG])
    lowered = blob.lower()
    assert "dsh" not in lowered
    assert "deepseek" not in lowered
    assert "qwen" in lowered
    assert "minimax" in lowered or "h3" in lowered


def test_private_lanes_only():
    settings = Settings()
    assert validate_lane("http://127.0.0.1:8190", settings)[0] is True
    assert validate_lane("http://10.1.2.3:8188", settings)[0] is True
    assert validate_lane("http://192.168.1.9:8188", settings)[0] is True
    ok, err = validate_lane("http://8.8.8.8:8188", settings)
    assert ok is False
    assert "public" in err or "private" in err
    ok, err = validate_lane("http://comfy.example.com:8188", settings)
    assert ok is False


def test_snap_measured_window_and_down():
    measured = resolve_frames({}, fps=24, max_frames=362)
    assert measured["frames"] == 243
    assert measured["raw"] == 243
    ten = resolve_frames({"seconds": 10}, fps=24, max_frames=362)
    assert ten["raw"] == 240
    assert ten["frames"] == 226
    assert ten["frames"] < ten["raw"]
    with pytest.raises(ComfyError, match="maximum"):
        resolve_frames({"seconds": 16}, fps=24, max_frames=362)


def test_graphs_are_smf_branded_and_sigma_shift_is_turbo_only():
    still = build_qwen_graph("a hallway", 1344, 768, 1, FILES)
    assert still["9"]["inputs"]["filename_prefix"] == "smf_still"
    assert "dsh" not in json.dumps(still).lower()

    full = build_h3_graph(
        prompt="hallway",
        negative="blurry",
        frames=243,
        width=960,
        height=544,
        seed=1,
        quality="full",
        style=None,
        files=H3_FILES,
        fps=24,
    )
    dumped = json.dumps(full)
    assert "MiniMaxH3SigmaShift" not in dumped
    assert full["7"]["inputs"]["steps"] == 20
    assert full["13"]["inputs"]["filename_prefix"] == "video/smf_clip"
    assert "dsh" not in dumped.lower()

    fast = build_h3_graph(
        prompt="hallway",
        negative="blurry",
        frames=90,
        width=960,
        height=544,
        seed=1,
        quality="fast",
        style=None,
        files=H3_FILES,
        fps=24,
    )
    assert fast["3"]["class_type"] == "MiniMaxH3SigmaShift"
    assert fast["3"]["inputs"]["shift_video"] == 12.0
    assert fast["3"]["inputs"]["shift_audio"] == 3.0
    assert fast["7"]["inputs"]["steps"] == 8
    assert fast["1"]["inputs"]["unet_name"] == "h3-turbo.safetensors"

    styled = build_h3_graph(
        prompt="hallway",
        negative="blurry",
        frames=243,
        width=960,
        height=544,
        seed=1,
        quality="full",
        style={"file": "look.safetensors", "trigger": "look"},
        files=H3_FILES,
        fps=24,
    )
    assert "MiniMaxH3SigmaShift" not in json.dumps(styled)
    assert styled["14"]["inputs"]["lora_name"] == "look.safetensors"
    assert styled["7"]["inputs"]["model"] == ["14", 0]


def test_images_key_is_required_for_video_outputs():
    assert first_images_output({"13": {"video": [{"filename": "clip.mp4"}]}}) is None
    found = first_images_output({"13": {"images": [{"filename": "clip.mp4", "type": "output"}]}})
    assert found is not None
    assert found["filename"] == "clip.mp4"


@respx.mock
def test_busy_lanes_refuse_without_prompt(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path)
    respx.get(f"{STILL}/queue").mock(return_value=_queue(busy=True))
    prompt = respx.post(f"{STILL}/prompt").mock(return_value=httpx.Response(200, json={"prompt_id": "nope"}))
    result = generate_still(settings, _ctx("still-sheet", {"prompt": "a plate"}), role="sheet")
    assert result.ok is False
    assert result.receipt["called_comfy"] is False
    assert "busy" in result.error.lower()
    assert prompt.called is False
    get_settings.cache_clear()


@respx.mock
def test_qwen_saves_png_path_not_pixels(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path)
    respx.get(f"{STILL}/queue").mock(return_value=_queue())

    def _prompt(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["prompt"]["9"]["inputs"]["filename_prefix"] == "smf_still"
        assert body["client_id"] == "smf-aigc-studio"
        assert "dsh" not in request.content.decode()
        return httpx.Response(200, json={"prompt_id": "p-still"})

    respx.post(f"{STILL}/prompt").mock(side_effect=_prompt)
    respx.get(f"{STILL}/history/p-still").mock(
        return_value=httpx.Response(
            200,
            json={
                "p-still": {
                    "outputs": {
                        "9": {"images": [{"filename": "smf_still_00001_.png", "subfolder": "", "type": "output"}]}
                    }
                }
            },
        )
    )
    respx.get(url__startswith=f"{STILL}/view").mock(return_value=httpx.Response(200, content=PNG))
    result = generate_still(
        settings,
        _ctx("still-sheet", {"prompt": "a white pier. reference: /tmp/ref.png", "size": "studio"}),
        role="sheet",
    )
    assert result.ok is True
    assert result.receipt["called_comfy"] is True
    assert result.receipt["width"] == 1344
    assert result.receipt["height"] == 768
    assert result.receipt["references"] == ["/tmp/ref.png"]
    assert result.receipt["path"].endswith(".png")
    assert Path(result.receipt["path"]).read_bytes() == PNG
    assert result.media_bytes == PNG
    dumped = json.dumps(result.receipt)
    assert "dsh" not in dumped.lower()
    assert PNG.decode("latin1") not in dumped
    get_settings.cache_clear()


@respx.mock
def test_h3_returns_job_then_mp4_and_ignores_video_key(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path)
    respx.get(f"{CLIP}/queue").mock(return_value=_queue())
    free = respx.post(f"{STILL}/free").mock(return_value=httpx.Response(200, json={"ok": True}))

    def _prompt(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "MiniMaxH3SigmaShift" not in json.dumps(body["prompt"])
        assert body["prompt"]["13"]["inputs"]["filename_prefix"] == "video/smf_clip"
        return httpx.Response(200, json={"prompt_id": "p-clip"})

    respx.post(f"{CLIP}/prompt").mock(side_effect=_prompt)
    started = start_clip(settings, _ctx("clip-hop1", {"prompt": "an empty corridor"}))
    assert started.pending is True
    assert started.receipt["job_id"] == "job-live-1"
    assert started.receipt["eta"]
    assert started.receipt["frames"] == 243
    assert started.receipt["called_comfy"] is True
    assert started.receipt["sigma_shift"] is False
    assert free.called is True
    assert started.media_bytes is None

    respx.get(f"{CLIP}/history/p-clip").mock(
        return_value=httpx.Response(
            200,
            json={"p-clip": {"outputs": {"13": {"video": [{"filename": "trap.mp4"}]}}}},
        )
    )
    waiting = poll_clip(settings, started.receipt)
    assert waiting.pending is True
    assert waiting.media_bytes is None

    respx.get(f"{CLIP}/history/p-clip").mock(
        return_value=httpx.Response(
            200,
            json={
                "p-clip": {
                    "outputs": {
                        "13": {"images": [{"filename": "smf_clip_00001_.mp4", "subfolder": "video", "type": "output"}]}
                    },
                    "status": {"completed": True, "status_str": "success"},
                }
            },
        )
    )
    respx.get(url__startswith=f"{CLIP}/view").mock(return_value=httpx.Response(200, content=MP4))
    done = poll_clip(settings, waiting.receipt)
    assert done.ok is True
    assert done.pending is False
    assert done.receipt["path"].endswith(".mp4")
    assert Path(done.receipt["path"]).read_bytes() == MP4
    assert done.content_type == "video/mp4"
    assert "dsh" not in json.dumps(done.receipt).lower()
    calls = [str(call.request.url) for call in respx.calls]
    free_at = next(i for i, url in enumerate(calls) if url.endswith("/free"))
    prompt_at = next(i for i, url in enumerate(calls) if url.endswith("/prompt"))
    assert free_at < prompt_at
    get_settings.cache_clear()


def test_unset_lanes_stay_stub(monkeypatch):
    monkeypatch.setenv("STUDIO_STILL_ADAPTER", "comfy-qwen")
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "comfy-h3")
    monkeypatch.setenv("STUDIO_COMFY_STILL_LANES", "")
    monkeypatch.setenv("STUDIO_COMFY_CLIP_LANES", "")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "")
    monkeypatch.setenv("STUDIO_ADAPTER_CLI", "")
    get_settings.cache_clear()
    settings = get_settings()
    assert resolve_adapter_name("still-sheet", settings) == "stub"
    assert resolve_adapter_name("clip-hop1", settings) == "stub"
    health = slot_health(SLOT_BY_ID["comfy-qwen"], settings)
    assert health["not_live"] is True
    assert health["lanes_configured"] is False
    get_settings.cache_clear()


def test_public_lane_is_unhealthy_without_a_request(monkeypatch):
    monkeypatch.setenv("STUDIO_COMFY_CLIP_LANES", "http://8.8.8.8:8188")
    monkeypatch.setenv("STUDIO_ADAPTER_WEBHOOK_URL", "")
    monkeypatch.setenv("STUDIO_ADAPTER_CLI", "")
    get_settings.cache_clear()
    report = slot_health(SLOT_BY_ID["comfy-h3"], get_settings())
    assert report["lanes_configured"] is True
    assert report["not_live"] is False
    assert report["live"] is True
    assert report["ok"] is False
    assert report["schema_ok"] is False
    get_settings.cache_clear()


def _pass_app():
    respx.route(host="testserver").pass_through()


def test_api_still_job_stores_png(client, auth, monkeypatch):
    monkeypatch.setenv("STUDIO_STILL_ADAPTER", "comfy-qwen")
    monkeypatch.setenv("STUDIO_COMFY_STILL_LANES", STILL)
    monkeypatch.setenv("STUDIO_COMFY_STILL_POLL_SECONDS", "0")
    monkeypatch.setenv("STUDIO_COMFY_STILL_TIMEOUT_SECONDS", "2")
    get_settings.cache_clear()
    _, episode = create_episode(client, auth, "Qwen still")
    with respx.mock:
        _pass_app()
        respx.get(f"{STILL}/queue").mock(return_value=_queue())
        respx.post(f"{STILL}/prompt").mock(return_value=httpx.Response(200, json={"prompt_id": "api-still"}))
        respx.get(f"{STILL}/history/api-still").mock(
            return_value=httpx.Response(
                200,
                json={
                    "api-still": {
                        "outputs": {"9": {"images": [{"filename": "smf_still_00001_.png", "subfolder": "", "type": "output"}]}}
                    }
                },
            )
        )
        respx.get(url__startswith=f"{STILL}/view").mock(return_value=httpx.Response(200, content=PNG))
        response = client.post(
            "/api/jobs",
            headers=auth,
            json={
                "episode_id": episode["id"],
                "job_type": "still-sheet",
                "adapter": "comfy-qwen",
                "payload": {"prompt": "a grey studio sweep", "size": "square"},
            },
        )
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["status"] == "succeeded"
    assert job["adapter"] == "comfy-qwen"
    assert job["result"]["called_comfy"] is True
    assert job["result"]["path"].endswith(".png")
    assert Path(job["result"]["path"]).read_bytes() == PNG
    assert job["result"]["width"] == 1328
    media = client.get(f"/api/media/{job['media_id']}", headers=auth)
    assert media.status_code == 200
    assert media.content == PNG
    assert "dsh" not in json.dumps(job["result"]).lower()
    health = client.get("/api/adapters/comfy-qwen/health", headers=auth)
    assert health.status_code == 200
    assert health.json()["lanes_configured"] is True
    assert health.json()["live"] is True
    assert health.json()["not_live"] is False
    get_settings.cache_clear()


def test_api_clip_is_async_then_mp4_and_not_watched(client, auth, monkeypatch):
    monkeypatch.setenv("STUDIO_CLIP_ADAPTER", "comfy-h3")
    monkeypatch.setenv("STUDIO_COMFY_CLIP_LANES", CLIP)
    monkeypatch.setenv("STUDIO_COMFY_IMAGE_LANES_FOR_FREE", STILL)
    monkeypatch.setenv("STUDIO_COMFY_POLL_INTERVAL_SECONDS", "0")
    get_settings.cache_clear()
    _, episode, shots = green_ready_episode(client, auth, "H3 clip")
    shot_id = shots[0]["id"]
    history = {"ready": False}

    def _history(_request: httpx.Request) -> httpx.Response:
        if not history["ready"]:
            return httpx.Response(200, json={"api-clip": {"outputs": {"13": {"video": [{"filename": "trap.mp4"}]}}}})
        return httpx.Response(
            200,
            json={
                "api-clip": {
                    "outputs": {
                        "13": {"images": [{"filename": "smf_clip_00001_.mp4", "subfolder": "video", "type": "output"}]}
                    },
                    "status": {"completed": True, "status_str": "success"},
                }
            },
        )

    with respx.mock:
        _pass_app()
        respx.get(f"{CLIP}/queue").mock(return_value=_queue())
        respx.post(f"{STILL}/free").mock(return_value=httpx.Response(200, json={}))
        respx.post(f"{CLIP}/prompt").mock(return_value=httpx.Response(200, json={"prompt_id": "api-clip"}))
        respx.get(f"{CLIP}/history/api-clip").mock(side_effect=_history)
        respx.get(url__startswith=f"{CLIP}/view").mock(return_value=httpx.Response(200, content=MP4))
        started = client.post(
            "/api/jobs",
            headers=auth,
            json={
                "episode_id": episode["id"],
                "shot_id": shot_id,
                "job_type": "clip-hop1",
                "adapter": "comfy-h3",
                "payload": {"prompt": "an empty motel corridor"},
            },
        )
        assert started.status_code == 201, started.text
        job = started.json()
        assert job["status"] == "running"
        assert job["result"]["job_id"] == job["id"]
        assert job["result"]["eta"]
        assert job["result"]["called_comfy"] is True
        assert job["result"]["comfy_pending"] is True
        assert not str(job["result"].get("path") or "").endswith(".mp4")

        waiting = client.get(f"/api/jobs/{job['id']}", headers=auth)
        assert waiting.status_code == 200
        assert waiting.json()["status"] == "running"

        history["ready"] = True
        finished = client.get(f"/api/jobs/{job['id']}", headers=auth)
    assert finished.status_code == 200, finished.text
    done = finished.json()
    assert done["status"] == "succeeded"
    assert done["result"]["path"].endswith(".mp4")
    assert Path(done["result"]["path"]).read_bytes() == MP4
    assert done["result"]["called_comfy"] is True
    media = client.get(f"/api/media/{done['media_id']}", headers=auth)
    assert media.content == MP4
    receipt = client.get(
        f"/api/episodes/{episode['id']}/shots/{shot_id}/receipt",
        headers=auth,
    )
    assert receipt.status_code == 200, receipt.text
    assert receipt.json()["preview_watched"] is False
    assert receipt.json()["frames"] == 243
    assert "dsh" not in json.dumps(done["result"]).lower()
    get_settings.cache_clear()


def test_api_busy_still_fails_cleanly(client, auth, monkeypatch):
    monkeypatch.setenv("STUDIO_STILL_ADAPTER", "comfy-qwen")
    monkeypatch.setenv("STUDIO_COMFY_STILL_LANES", STILL)
    get_settings.cache_clear()
    _, episode = create_episode(client, auth, "Busy lane")
    with respx.mock:
        _pass_app()
        respx.get(f"{STILL}/queue").mock(return_value=_queue(busy=True))
        prompt = respx.post(f"{STILL}/prompt").mock(return_value=httpx.Response(200, json={"prompt_id": "no"}))
        response = client.post(
            "/api/jobs",
            headers=auth,
            json={
                "episode_id": episode["id"],
                "job_type": "still-sheet",
                "payload": {"prompt": "a plate"},
            },
        )
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["status"] == "failed"
    assert "busy" in job["error"].lower()
    assert job["result"]["called_comfy"] is False
    assert prompt.called is False
    get_settings.cache_clear()


def test_second_free_lane_is_chosen(monkeypatch, tmp_path):
    settings = _settings(monkeypatch, tmp_path)
    other = "http://127.0.0.1:8191"
    monkeypatch.setenv("STUDIO_COMFY_STILL_LANES", f"{STILL},{other}")
    get_settings.cache_clear()
    settings = get_settings()
    with respx.mock:
        respx.get(f"{STILL}/queue").mock(return_value=_queue(busy=True))
        respx.get(f"{other}/queue").mock(return_value=_queue())
        lane = ComfyClient(settings).pick_lane([STILL, other])
    assert lane == other
    get_settings.cache_clear()
