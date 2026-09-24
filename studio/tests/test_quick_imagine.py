"""Quick Imagine path. httpx.MockTransport only — these tests do not open a socket."""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import get_settings
from app.gates import GATE_DEFS, evaluate_gates
from app.imagine_bridge import set_transport_for_tests, studio_pack_from_imagine
from tests.helpers import add_member, as_user

MP4 = b"\x00\x00\x00\x18ftypmp42imagine-episode"
PLAN = {
    "title": "Hall light",
    "logline": "Mara waits in the hall until the light turns.",
    "aspect_ratio": "9:16",
    "resolution": "720p",
    "look_bible": {
        "cast": "Mara, tired eyes",
        "wardrobe": "wool coat",
        "palette": "sodium and blue",
        "lighting": "one practical",
        "camera": "35mm",
    },
    "beat_map": [
        {"role": "setup", "summary": "Mara waits"},
        {"role": "button", "summary": "The light turns"},
    ],
    "cast": [],
    "shots": [
        {
            "id": "s1",
            "prompt_still": "Mara at the door",
            "prompt_motion": "Mara turns her head",
            "duration_sec": 8,
            "start_state": "Mara at the door",
            "end_state": "Mara faces the hall",
            "beat": "setup",
            "camera": {"scale": "medium", "angle": "eye", "move": "dolly_in", "exit_frame": "her face"},
        },
        {
            "id": "s2",
            "prompt_still": "Mara faces the hall",
            "prompt_motion": "The light warms the coat",
            "duration_sec": 7,
            "start_state": "Mara faces the hall",
            "end_state": "warm light on the coat",
            "beat": "button",
            "camera": {"scale": "wide", "angle": "eye", "move": "orbit", "exit_frame": "the coat"},
        },
    ],
}


@pytest.fixture
def imagine_calls():
    return []


@pytest.fixture
def imagine(monkeypatch, imagine_calls):
    def install(handler, *, url: str = "http://imagine.test"):
        monkeypatch.setenv("STUDIO_IMAGINE_URL", url)
        monkeypatch.setenv("STUDIO_IMAGINE_TOKEN", "local-dev-token")
        get_settings.cache_clear()

        def wrapped(request: httpx.Request) -> httpx.Response:
            imagine_calls.append((request.method, request.url.path))
            assert request.url.host == "imagine.test"
            assert request.headers.get("authorization") == "Bearer local-dev-token"
            return handler(request)

        set_transport_for_tests(httpx.MockTransport(wrapped))

    yield install
    set_transport_for_tests(None)
    get_settings.cache_clear()


def _health(configured: bool = True) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "ok": True,
            "imagine_configured": configured,
            "ffmpeg": True,
            "image_model": "grok-imagine-image-2.0",
            "video_model": "grok-imagine-video-1.5",
        },
    )


def test_pack_mirror_maps_camera_and_does_not_force_gates():
    pack = studio_pack_from_imagine(PLAN)
    assert pack["logLine"] == PLAN["logline"]
    assert pack["editList"][0]["cameraVerb"] == "push"
    assert pack["editList"][0]["cameraAmplitude"] == "medium"
    assert pack["editList"][0]["cameraSpeed"] == ""
    assert pack["editList"][1]["cameraVerb"] == "arc"
    assert pack["editList"][1]["cameraAmplitude"] == "wide"
    assert pack["map"][0]["clock"] == "0:00"
    assert pack["map"][0]["energy"] == "verse"
    assert pack["map"][1]["clock"] == "0:08"
    assert pack["map"][1]["energy"] == "outro"
    assert "Cast: Mara, tired eyes" in pack["look"]["styleLine"]
    assert pack["studioMeta"]["generate_ready"] is False
    assert pack["studioMeta"]["called_comfy"] is False
    gates = evaluate_gates(pack)
    assert [gate["id"] for gate in gates] == [row["id"] for row in GATE_DEFS]
    assert all(gate["ok"] for gate in gates) is False
    by_id = {gate["id"]: gate["ok"] for gate in gates}
    assert by_id["log-line"] is True
    assert by_id["edit-list"] is False


def test_meta_imagine_configured_uses_health_and_stays_false_when_unset(client, auth, imagine, imagine_calls):
    cold = client.get("/api/meta", headers=auth)
    assert cold.status_code == 200
    assert cold.json()["imagine_configured"] is False
    assert cold.json()["primary_create"] == "wizard"
    assert imagine_calls == []

    imagine(lambda request: _health(True))
    warm = client.get("/api/meta", headers=auth)
    assert warm.json()["imagine_configured"] is True
    assert ("GET", "/api/health") in imagine_calls

    imagine_calls.clear()
    cached = client.get("/api/meta", headers=auth)
    assert cached.json()["imagine_configured"] is True
    assert imagine_calls == []


def test_plan_passthrough_records_no_spend(client, auth, imagine):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/health":
            return _health(True)
        if request.url.path == "/api/packs/plan" and request.method == "POST":
            sent = json.loads(request.content.decode())
            assert sent["prompt"] == "Mara waits."
            assert sent["target_duration_sec"] == 15
            assert sent["aspect_ratio"] == "9:16"
            return httpx.Response(200, json=PLAN)
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    imagine(handler)
    response = client.post(
        "/api/quick/plan",
        headers=auth,
        json={"prompt": "Mara waits.", "target_duration_sec": 15, "aspect_ratio": "9:16"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["plan"]["title"] == "Hall light"
    assert body["plan"]["shots"][0]["prompt_motion"] == "Mara turns her head"
    assert body["estimated_cost_units"] == 0
    assert body["called_comfy"] is False
    assert body["produced_mp4"] is False
    audit = client.get("/api/audit", headers=auth, params={"action": "quick.plan"})
    assert audit.status_code == 200
    assert audit.json()[0]["action"] == "quick.plan"
    assert audit.json()[0]["detail"]["estimated_cost_units"] == 0


def test_run_refused_without_confirm_without_config_and_for_viewer(client, auth, imagine_calls):
    add_member(client, auth, "quick-viewer", "viewer")
    viewer = as_user(auth, "quick-viewer")
    blocked_role = client.post(
        "/api/quick/run",
        headers=viewer,
        json={"plan": PLAN, "confirm": True},
    )
    assert blocked_role.status_code == 403
    assert blocked_role.json()["detail"]["code"] == "forbidden_role"

    no_confirm = client.post("/api/quick/run", headers=auth, json={"plan": PLAN, "confirm": False})
    assert no_confirm.status_code == 409
    assert no_confirm.json()["detail"]["code"] == "imagine_confirm_required"

    unconfigured = client.post("/api/quick/run", headers=auth, json={"plan": PLAN, "confirm": True})
    assert unconfigured.status_code == 409, unconfigured.text
    assert "STUDIO_IMAGINE_URL" in unconfigured.json()["detail"]
    assert imagine_calls == []


def test_poll_imports_mp4_and_leaves_gates_and_generate_ok(client, auth, imagine):
    phase = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/health":
            return _health(True)
        if path == "/api/packs" and request.method == "POST":
            body = json.loads(request.content.decode())
            assert body["shots"][0]["camera"]["move"] == "dolly_in"
            return httpx.Response(201, json={**body, "id": "pack-1", "created_at": "2026-09-24T00:00:00Z"})
        if path == "/api/packs/pack-1/run":
            return httpx.Response(200, json={"job_id": "job-1", "pack_id": "pack-1", "status": "queued"})
        if path == "/api/packs/pack-1/jobs":
            phase["n"] += 1
            stitched = phase["n"] > 1
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "id": "job-1",
                            "pack_id": "pack-1",
                            "status": "done" if stitched else "running",
                            "called_imagine_still": True,
                            "produced_still": True,
                            "called_imagine_video": stitched,
                            "produced_mp4": stitched,
                            "stitched_episode": stitched,
                            "episode_path": "packs/pack-1/episode.mp4" if stitched else None,
                            "shots": [],
                        }
                    ]
                },
            )
        if path == "/api/packs/pack-1/episode":
            assert phase["n"] > 1
            return httpx.Response(200, content=MP4, headers={"content-type": "video/mp4"})
        raise AssertionError(f"unexpected {request.method} {path}")

    imagine(handler)
    started = client.post("/api/quick/run", headers=auth, json={"plan": PLAN, "confirm": True})
    assert started.status_code == 201, started.text
    run = started.json()
    assert run["called_comfy"] is False
    assert run["called_imagine"] is True
    assert run["produced_mp4"] is False
    assert run["estimated_cost_units"] == 4.0
    assert run["review_state"] == "draft"
    assert run["imagine_pack_id"] == "pack-1"
    assert run["imagine_job_id"] == "job-1"

    waiting = client.get(f"/api/quick/{run['run_id']}", headers=auth)
    assert waiting.status_code == 200, waiting.text
    assert waiting.json()["produced_mp4"] is False
    assert waiting.json()["called_comfy"] is False
    assert waiting.json()["media_id"] is None

    done = client.get(f"/api/quick/{run['run_id']}", headers=auth)
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["produced_mp4"] is True
    assert body["called_imagine"] is True
    assert body["called_comfy"] is False
    assert body["stitched_episode"] is True
    assert body["status"] == "succeeded"
    assert body["review_state"] == "draft"
    media = client.get(f"/api/media/{body['media_id']}", headers=auth)
    assert media.status_code == 200, media.text
    assert media.content == MP4
    assert media.headers["content-type"].startswith("video/mp4")

    episode = client.get(f"/api/episodes/{body['episode_id']}", headers=auth)
    assert episode.status_code == 200
    assert episode.json()["review_state"] == "draft"
    revision_id = episode.json()["latest_revision"]["id"]
    revision = client.get(
        f"/api/episodes/{body['episode_id']}/revisions/{revision_id}",
        headers=auth,
    )
    assert revision.status_code == 200, revision.text
    stored = revision.json()["pack"]
    gates = evaluate_gates(stored)
    snapshot = revision.json()["gate_snapshot"]
    assert snapshot["all_green"] is False
    assert snapshot["all_green"] == all(gate["ok"] for gate in gates)
    assert [gate["id"] for gate in snapshot["gates"]] == [row["id"] for row in GATE_DEFS]
    assert revision.json()["all_gates_green"] is False

    refused = client.put(
        f"/api/episodes/{body['episode_id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "quick path must not stamp this"},
    )
    assert refused.status_code == 409, refused.text
    still = client.get(f"/api/episodes/{body['episode_id']}", headers=auth)
    assert still.json()["review_state"] != "generate-ok"

    listed = client.get(
        f"/api/episodes/{body['episode_id']}/jobs",
        headers=auth,
        params={"job_type": "imagine-episode"},
    )
    assert listed.status_code == 200
    job = listed.json()[0]
    assert job["adapter"] == "grok-imagine"
    assert job["result"]["called_comfy"] is False
    assert job["result"]["produced_mp4"] is True
    audit = client.get("/api/audit", headers=auth, params={"action": "quick.run"})
    assert audit.json()[0]["detail"]["called_comfy"] is False
    assert audit.json()[0]["detail"]["estimated_cost_units"] == 4.0


def test_desk_enqueue_does_not_start_imagine(client, auth, imagine, imagine_calls):
    from tests.helpers import green_ready_episode

    imagine(lambda request: _health(True))
    _, episode, _ = green_ready_episode(client, auth, "No desk imagine")
    before = len(imagine_calls)
    refused = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "imagine-episode"},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "imagine_confirm_required"
    assert [path for _, path in imagine_calls[before:] if path != "/api/health"] == []
