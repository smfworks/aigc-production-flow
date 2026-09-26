"""Local quick create. Plans and runs stay in-process. No renderer client."""

from __future__ import annotations

from app.gates import GATE_DEFS, evaluate_gates
from app.quickpack import cast_payload_for_plan, local_plan, studio_pack_from_plan, who_is_where
from tests.helpers import add_member, as_user

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


def test_pack_mirror_maps_camera_and_does_not_force_gates():
    pack = studio_pack_from_plan(PLAN)
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
    assert "stage" not in pack["editList"][0]
    assert "staging:" not in pack["editList"][0]["notes"]
    assert "staging" not in pack["studioMeta"]
    assert "lock_staging" not in pack["studioMeta"]
    assert pack["studioMeta"]["aspect_ratio"] == "9:16"
    assert pack["studioMeta"]["generate_ready"] is False
    assert pack["studioMeta"]["called_comfy"] is False
    assert "called_imagine" not in pack["studioMeta"]
    assert pack["studioMeta"]["produced_mp4"] is False
    assert pack["studioMeta"]["model"] == "none"
    gates = evaluate_gates(pack)
    assert [gate["id"] for gate in gates] == [row["id"] for row in GATE_DEFS]
    assert all(gate["ok"] for gate in gates) is False
    by_id = {gate["id"]: gate["ok"] for gate in gates}
    assert by_id["log-line"] is True
    assert by_id["edit-list"] is False


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
    pack = studio_pack_from_plan(plan)
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
    assert "called_imagine" not in pack["studioMeta"]
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

    cast_only = studio_pack_from_plan({**PLAN, "cast": CAST})
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
    from_labels = studio_pack_from_plan({**PLAN, **unlabeled, "cast": []})
    assert from_labels["editList"][0]["entities"] == "Jack on his buckskin horse"
    assert from_labels["studioMeta"]["staging"]["scenes"][0]["id"] == "sc1"


def test_local_plan_places_named_cast_and_skips_a_cast_heading():
    planned = local_plan(
        prompt="A lone cowboy rides.\n\nCast:\nJonah — blue shirt",
        target_duration_sec=15,
        aspect_ratio="16:9",
    )
    assert planned["lock_staging"] is True
    assert planned["cast"][0]["name"] == "Jonah"
    assert planned["shots"][0]["prompt_still"] == "A lone cowboy rides."
    assert "Cast" not in planned["shots"][0]["prompt_still"]
    assert sum(shot["duration_sec"] for shot in planned["shots"]) == 15
    where = who_is_where(planned, planned["shots"][0])
    assert where.startswith("Jonah:")
    assert planned["staging"]["scenes"][0]["id"] == "sc1"

    empty = local_plan(prompt="Mara waits.", target_duration_sec=30, aspect_ratio="9:16")
    assert empty["cast"] == []
    assert "staging" not in empty
    assert who_is_where(empty, empty["shots"][0]) == ""
    assert empty["shots"][0]["duration_sec"] == 30


def test_meta_has_no_imagine_flag(client, auth):
    cold = client.get("/api/meta", headers=auth)
    assert cold.status_code == 200
    body = cold.json()
    assert "imagine_configured" not in body
    assert body["primary_create"] == "wizard"


def test_plan_is_local_and_records_no_spend(client, auth):
    response = client.post(
        "/api/quick/plan",
        headers=auth,
        json={
            "prompt": "Mara waits. The light turns.",
            "target_duration_sec": 15,
            "aspect_ratio": "9:16",
            "cast_notes": "Jack — tan hat\nthe bandits — black dusters",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["estimated_cost_units"] == 0
    assert body["called_comfy"] is False
    assert body["produced_mp4"] is False
    assert "called_imagine" not in body
    plan = body["plan"]
    assert [row["name"] for row in plan["cast"]] == ["Jack", "the bandits"]
    assert plan["lock_staging"] is True
    assert plan["aspect_ratio"] == "9:16"
    assert sum(shot["duration_sec"] for shot in plan["shots"]) == 15
    assert who_is_where(plan, plan["shots"][0])
    audit = client.get("/api/audit", headers=auth, params={"action": "quick.plan"})
    assert audit.status_code == 200
    assert audit.json()[0]["action"] == "quick.plan"
    assert audit.json()[0]["detail"]["estimated_cost_units"] == 0
    assert audit.json()[0]["detail"]["called_comfy"] is False


def test_run_refused_without_confirm_and_for_viewer(client, auth):
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
    assert no_confirm.json()["detail"]["code"] == "confirm_required"


def test_run_saves_episode_without_an_mp4_or_cloud_job(client, auth):
    started = client.post("/api/quick/run", headers=auth, json={"plan": PLAN, "confirm": True})
    assert started.status_code == 201, started.text
    run = started.json()
    assert run["called_comfy"] is False
    assert run["produced_mp4"] is False
    assert run["stitched_episode"] is False
    assert run["media_id"] is None
    assert run["estimated_cost_units"] == 0
    assert run["status"] == "saved"
    assert run["review_state"] == "draft"
    assert run["still_adapter"] == "stub"
    assert run["clip_adapter"] == "stub"
    assert "called_imagine" not in run
    assert "imagine" not in run["message"].lower()

    again = client.get(f"/api/quick/{run['run_id']}", headers=auth)
    assert again.status_code == 200, again.text
    assert again.json()["produced_mp4"] is False
    assert again.json()["called_comfy"] is False

    episode = client.get(f"/api/episodes/{run['episode_id']}", headers=auth)
    assert episode.status_code == 200
    assert episode.json()["review_state"] == "draft"
    revision_id = episode.json()["latest_revision"]["id"]
    revision = client.get(
        f"/api/episodes/{run['episode_id']}/revisions/{revision_id}",
        headers=auth,
    )
    stored = revision.json()["pack"]
    gates = evaluate_gates(stored)
    snapshot = revision.json()["gate_snapshot"]
    assert snapshot["all_green"] is False
    assert snapshot["all_green"] == all(gate["ok"] for gate in gates)
    assert revision.json()["all_gates_green"] is False
    assert stored["studioMeta"]["produced_mp4"] is False
    assert stored["studioMeta"]["called_comfy"] is False

    refused = client.put(
        f"/api/episodes/{run['episode_id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "quick path must not stamp this"},
    )
    assert refused.status_code == 409, refused.text
    still = client.get(f"/api/episodes/{run['episode_id']}", headers=auth)
    assert still.json()["review_state"] != "generate-ok"

    listed = client.get(f"/api/episodes/{run['episode_id']}/jobs", headers=auth)
    assert listed.status_code == 200
    assert listed.json() == []
    audit = client.get("/api/audit", headers=auth, params={"action": "quick.run"})
    assert audit.json()[0]["detail"]["called_comfy"] is False
    assert audit.json()[0]["detail"]["produced_mp4"] is False
    assert audit.json()[0]["detail"]["estimated_cost_units"] == 0


def test_run_persists_staging_mirror(client, auth):
    plan = _staged_plan()
    started = client.post("/api/quick/run", headers=auth, json={"plan": plan, "confirm": True})
    assert started.status_code == 201, started.text
    run = started.json()
    assert run["called_comfy"] is False
    assert run["produced_mp4"] is False
    assert run["review_state"] == "draft"

    episode = client.get(f"/api/episodes/{run['episode_id']}", headers=auth)
    revision_id = episode.json()["latest_revision"]["id"]
    revision = client.get(
        f"/api/episodes/{run['episode_id']}/revisions/{revision_id}",
        headers=auth,
    )
    stored = revision.json()["pack"]
    assert stored["studioMeta"]["staging"] == STAGING
    assert stored["studioMeta"]["lock_staging"] is True
    assert stored["studioMeta"]["called_comfy"] is False
    assert "called_imagine" not in stored["studioMeta"]
    assert stored["studioMeta"]["produced_mp4"] is False
    assert stored["studioMeta"]["generate_ready"] is False
    assert stored["editList"][0]["entities"] == "Jack, the bandits"
    assert stored["editList"][0]["stage"]["start"][0]["x"] == "right_third"
    assert stored["studioMeta"]["shot_stages"][1]["id"] == "s2"
    assert stored["studioMeta"]["shot_stages"][1]["stage"]["cross_motivation"] == "looking back along the trail"
    assert "staging: Jack: right third, mid" in stored["editList"][0]["notes"]
    snapshot = revision.json()["gate_snapshot"]
    assert snapshot["all_green"] is False
    shots = client.get(f"/api/episodes/{run['episode_id']}/shots", headers=auth)
    assert shots.json()[0]["entities"] == "Jack, the bandits"
    assert shots.json()[1]["entities"] == "Jack, the bandits"

    refused = client.put(
        f"/api/episodes/{run['episode_id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "staging must not stamp this"},
    )
    assert refused.status_code == 409, refused.text


def test_desk_rejects_removed_imagine_job_type(client, auth):
    from tests.helpers import green_ready_episode

    _, episode, _ = green_ready_episode(client, auth, "No cloud job")
    refused = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "imagine-episode"},
    )
    assert refused.status_code == 422, refused.text
    detail = refused.json()["detail"][0]
    assert detail["input"] == "imagine-episode"
    assert "imagine-episode" not in detail["ctx"]["expected"]
