"""Quick Imagine path. httpx.MockTransport only — these tests do not open a socket."""

from __future__ import annotations

import json

import httpx
import pytest

from app.config import get_settings
from app.gates import GATE_DEFS, evaluate_gates
from app.imagine_bridge import (
    cast_payload_for_plan,
    set_transport_for_tests,
    studio_pack_from_imagine,
    who_is_where,
)
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
    assert pack["editList"][0]["entities"] == ""
    assert pack["editList"][1]["entities"] == ""
    assert "stage" not in pack["editList"][0]
    assert "staging:" not in pack["editList"][0]["notes"]
    assert "staging" not in pack["studioMeta"]
    assert "lock_staging" not in pack["studioMeta"]
    assert pack["studioMeta"]["generate_ready"] is False
    assert pack["studioMeta"]["called_comfy"] is False
    assert pack["studioMeta"]["called_imagine"] is False
    assert pack["studioMeta"]["produced_mp4"] is False
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
            assert sent["lock_staging"] is True
            assert "cast" not in sent
            assert "cast_notes" not in sent
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


STAGING = {
    "scenes": [
        {
            "id": "sc1",
            "shot_ids": ["s1", "s2"],
            "axis": "the chase runs along the trail; the camera stays on the sun side",
            "travel": "screen_right",
            "entities": [
                {
                    "id": "jack",
                    "label": "Jack on his buckskin horse",
                    "kind": "character",
                    "cast_id": "jack",
                    "count": 1,
                },
                {
                    "id": "bandits",
                    "label": "the three bandits on dark horses",
                    "kind": "group",
                    "cast_id": "bandits",
                    "count": 3,
                },
            ],
            "relations": [{"a": "bandits", "rel": "behind", "b": "jack", "gap": "far"}],
        }
    ]
}
CAST = [
    {"id": "jack", "name": "Jack", "role": "character", "markers": "tan hat", "image_path": ""},
    {
        "id": "bandits",
        "name": "the bandits",
        "role": "character",
        "markers": "black dusters",
        "image_path": "",
    },
]
STAGE_S1 = {
    "scene_id": "sc1",
    "camera_side": "same",
    "cross_reason": "",
    "start": [
        {
            "id": "jack",
            "x": "right_third",
            "depth": "mid",
            "facing": "screen_right",
            "travel": "screen_right",
            "visible": True,
        },
        {
            "id": "bandits",
            "x": "left_third",
            "depth": "far",
            "facing": "screen_right",
            "travel": "screen_right",
            "visible": True,
        },
    ],
    "end": [
        {
            "id": "jack",
            "x": "right_third",
            "depth": "mid",
            "facing": "screen_right",
            "travel": "screen_right",
            "visible": True,
        },
        {
            "id": "bandits",
            "x": "left_third",
            "depth": "far",
            "facing": "screen_right",
            "travel": "screen_right",
            "visible": True,
        },
    ],
}
STAGE_S2 = {
    "scene_id": "sc1",
    "camera_side": "cross",
    "cross_motivation": "looking back along the trail",
    "start": [
        {
            "id": "jack",
            "x": "right_third",
            "depth": "foreground",
            "facing": "screen_right",
            "look": "screen_left",
            "travel": "screen_right",
            "visible": True,
        },
        {
            "id": "bandits",
            "x": "left_third",
            "depth": "background",
            "facing": "screen_right",
            "travel": "screen_right",
            "visible": True,
        },
    ],
    "end": STAGE_S1["end"],
}


def _staged_plan() -> dict:
    shots = []
    for shot, stage in zip(PLAN["shots"], (STAGE_S1, STAGE_S2), strict=True):
        shots.append({**shot, "stage": stage})
    return {
        **PLAN,
        "cast": CAST,
        "staging": STAGING,
        "lock_staging": True,
        "shots": shots,
    }


def test_cast_payload_comes_from_notes_or_story_and_skips_empty():
    assert cast_payload_for_plan(prompt="Mara waits.") == []
    notes = cast_payload_for_plan(cast_notes="Jack — tan hat\nthe bandits — black dusters")
    assert [row["name"] for row in notes] == ["Jack", "the bandits"]
    assert notes[0]["id"] == "Jack"
    assert notes[0]["markers"] == "tan hat"
    assert notes[0]["role"] == "character"
    assert notes[0]["image_path"] == ""
    assert notes[1]["id"] == "the_bandits"
    story = "A lone cowboy rides.\n\nCast:\nJack — tan hat"
    from_story = cast_payload_for_plan(prompt=story)
    assert from_story[0]["name"] == "Jack"
    structured = cast_payload_for_plan(
        cast=[{"name": "Mara", "role": "hero", "image_path": "../secret.png"}],
        cast_notes="Jack — tan hat",
        prompt=story,
    )
    assert structured == [
        {"id": "Mara", "name": "Mara", "role": "character", "markers": "", "image_path": ""}
    ]
    kept = cast_payload_for_plan(
        cast=[{"id": "jack", "name": "Jack", "role": "character", "image_path": "references/jack.png"}]
    )
    assert kept[0]["image_path"] == "references/jack.png"


def test_mirror_stores_staging_entities_and_blocking_without_greening_gates():
    plan = _staged_plan()
    pack = studio_pack_from_imagine(plan)
    assert pack["editList"][0]["entities"] == "Jack, the bandits"
    assert pack["editList"][1]["entities"] == "Jack, the bandits"
    assert pack["editList"][0]["stage"] == STAGE_S1
    assert pack["editList"][1]["stage"]["cross_motivation"] == "looking back along the trail"
    assert "cross_reason" not in pack["editList"][1]["stage"]
    assert pack["studioMeta"]["staging"] == STAGING
    assert pack["studioMeta"]["lock_staging"] is True
    assert pack["studioMeta"]["shot_stages"][0]["id"] == "s1"
    assert pack["studioMeta"]["shot_stages"][0]["stage"] == STAGE_S1
    assert pack["studioMeta"]["shot_stages"][1]["stage"]["cross_motivation"] == "looking back along the trail"
    assert pack["studioMeta"]["called_comfy"] is False
    assert pack["studioMeta"]["called_imagine"] is False
    assert pack["studioMeta"]["produced_mp4"] is False
    assert pack["studioMeta"]["generate_ready"] is False
    where = who_is_where(plan, plan["shots"][0])
    assert where == "Jack: right third, mid; the bandits: left third, far, behind Jack"
    assert f"staging: {where}" in pack["editList"][0]["notes"]
    assert "looking screen-left" in pack["editList"][1]["notes"]
    assert [row["name"] for row in pack["characters"] if row.get("name")] == ["Jack", "the bandits"]
    assert pack["characters"][0]["lockParagraph"] == ""
    gates = evaluate_gates(pack)
    assert all(gate["ok"] for gate in gates) is False
    assert {gate["id"]: gate["ok"] for gate in gates}["edit-list"] is False

    cast_only = studio_pack_from_imagine({**PLAN, "cast": CAST})
    assert cast_only["editList"][0]["entities"] == "Jack, the bandits"
    assert "staging" not in cast_only["studioMeta"]
    assert "shot_stages" not in cast_only["studioMeta"]
    assert "stage" not in cast_only["editList"][0]

    unlabeled = {
        "staging": {
            "scenes": [
                {
                    "id": "sc1",
                    "entities": [
                        {"id": "jack", "label": "Jack on his buckskin horse", "kind": "character"},
                    ],
                }
            ]
        },
        "shots": PLAN["shots"],
    }
    from_labels = studio_pack_from_imagine({**PLAN, **unlabeled, "cast": []})
    assert from_labels["editList"][0]["entities"] == "Jack on his buckskin horse"
    assert from_labels["studioMeta"]["staging"]["scenes"][0]["id"] == "sc1"


def test_plan_sends_cast_and_lock_staging(client, auth, imagine):
    seen: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/health":
            return _health(True)
        if request.url.path == "/api/packs/plan" and request.method == "POST":
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(200, json=PLAN)
        raise AssertionError(f"unexpected {request.method} {request.url.path}")

    imagine(handler)
    notes = client.post(
        "/api/quick/plan",
        headers=auth,
        json={
            "prompt": "A lone cowboy is chased across the desert.",
            "target_duration_sec": 30,
            "aspect_ratio": "16:9",
            "cast_notes": "Jack — tan hat\nthe bandits — black dusters",
        },
    )
    assert notes.status_code == 200, notes.text
    sent = seen["body"]
    assert sent["lock_staging"] is True
    assert sent["prompt"] == "A lone cowboy is chased across the desert."
    assert "cast_notes" not in sent
    assert [row["name"] for row in sent["cast"]] == ["Jack", "the bandits"]
    assert sent["cast"][0]["markers"] == "tan hat"
    assert notes.json()["called_imagine"] is False
    assert notes.json()["produced_mp4"] is False
    assert notes.json()["estimated_cost_units"] == 0

    story = "A lone cowboy rides.\n\nCast:\nJonah — blue shirt"
    embedded = client.post(
        "/api/quick/plan",
        headers=auth,
        json={"prompt": story, "target_duration_sec": 15, "aspect_ratio": "16:9"},
    )
    assert embedded.status_code == 200, embedded.text
    assert seen["body"]["prompt"] == story
    assert seen["body"]["lock_staging"] is True
    assert seen["body"]["cast"][0]["name"] == "Jonah"
    assert seen["body"]["cast"][0]["id"] == "Jonah"


def test_run_forwards_staging_and_persists_the_mirror(client, auth, imagine):
    plan = _staged_plan()
    forwarded: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/health":
            return _health(True)
        if path == "/api/packs" and request.method == "POST":
            body = json.loads(request.content.decode())
            forwarded["body"] = body
            return httpx.Response(201, json={**body, "id": "pack-stage", "created_at": "2026-09-26T00:00:00Z"})
        if path == "/api/packs/pack-stage/run":
            return httpx.Response(200, json={"job_id": "job-stage", "pack_id": "pack-stage", "status": "queued"})
        raise AssertionError(f"unexpected {request.method} {path}")

    imagine(handler)
    started = client.post("/api/quick/run", headers=auth, json={"plan": plan, "confirm": True})
    assert started.status_code == 201, started.text
    run = started.json()
    assert run["called_imagine"] is True
    assert run["called_comfy"] is False
    assert run["produced_mp4"] is False
    assert run["review_state"] == "draft"
    sent = forwarded["body"]
    assert sent["staging"] == plan["staging"]
    assert sent["lock_staging"] is True
    assert sent["shots"][0]["stage"] == plan["shots"][0]["stage"]
    assert sent["shots"][1]["stage"] == plan["shots"][1]["stage"]
    assert sent["shots"][1]["stage"]["cross_motivation"] == "looking back along the trail"
    assert "cross_reason" not in sent["shots"][1]["stage"]
    assert sent["cast"] == []

    episode = client.get(f"/api/episodes/{run['episode_id']}", headers=auth)
    assert episode.status_code == 200
    assert episode.json()["review_state"] == "draft"
    revision_id = episode.json()["latest_revision"]["id"]
    revision = client.get(
        f"/api/episodes/{run['episode_id']}/revisions/{revision_id}",
        headers=auth,
    )
    assert revision.status_code == 200, revision.text
    stored = revision.json()["pack"]
    assert stored["studioMeta"]["staging"] == STAGING
    assert stored["studioMeta"]["lock_staging"] is True
    assert stored["studioMeta"]["called_comfy"] is False
    assert stored["studioMeta"]["called_imagine"] is False
    assert stored["studioMeta"]["produced_mp4"] is False
    assert stored["studioMeta"]["generate_ready"] is False
    assert stored["editList"][0]["entities"] == "Jack, the bandits"
    assert stored["editList"][0]["stage"]["start"][0]["x"] == "right_third"
    assert stored["studioMeta"]["shot_stages"][1]["id"] == "s2"
    assert stored["studioMeta"]["shot_stages"][1]["stage"]["cross_motivation"] == "looking back along the trail"
    assert stored["editList"][1]["stage"]["cross_motivation"] == "looking back along the trail"
    assert "staging: Jack: right third, mid" in stored["editList"][0]["notes"]
    snapshot = revision.json()["gate_snapshot"]
    assert snapshot["all_green"] is False
    gates = evaluate_gates(stored)
    assert snapshot["all_green"] == all(gate["ok"] for gate in gates)
    shots = client.get(f"/api/episodes/{run['episode_id']}/shots", headers=auth)
    assert shots.status_code == 200, shots.text
    assert shots.json()[0]["entities"] == "Jack, the bandits"
    assert shots.json()[1]["entities"] == "Jack, the bandits"

    refused = client.put(
        f"/api/episodes/{run['episode_id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "staging must not stamp this"},
    )
    assert refused.status_code == 409, refused.text
