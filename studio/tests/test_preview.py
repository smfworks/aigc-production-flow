import json

from tests.helpers import attach_watched_receipt, create_episode, green_ready_episode, import_green


def test_preview_desk_and_parsed_receipt(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Desk")
    shot_id = shots[0]["id"]
    desk = client.get(f"/api/episodes/{episode['id']}/preview-desk", headers=auth)
    assert desk.status_code == 200
    body = desk.json()
    assert body["required_count"] == 1
    assert body["complete_count"] == 0
    assert body["generate_ok_ready"] is False

    watched_blocked = client.put(
        f"/api/episodes/{episode['id']}/shots/{shot_id}/preview-watched",
        headers=auth,
        json={"watched": True},
    )
    assert watched_blocked.status_code == 409

    receipt = attach_watched_receipt(client, auth, episode["id"], shot_id)
    assert receipt["source"] == "parsed"
    assert receipt["preview_watched"] is True
    assert receipt["media_id"]

    desk2 = client.get(f"/api/episodes/{episode['id']}/preview-desk", headers=auth).json()
    assert desk2["complete_count"] == 1
    assert desk2["generate_ok_ready"] is True


def test_ng_reason_blocks_generate_ok_and_extend(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "NG")
    shot_id = shots[0]["id"]
    attach_watched_receipt(
        client,
        auth,
        episode["id"],
        shot_id,
        ng_reason="identity drift at fade",
    )
    blocked = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "preview_incomplete"
    extend = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": shot_id, "job_type": "clip-extend"},
    )
    assert extend.status_code == 409


def test_manual_receipt_fields(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Manual")
    shot_id = shots[0]["id"]
    uploaded = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "preview", "entity_label": "take A"},
        files={"file": ("notes.txt", b"watched on the desk", "text/plain")},
    )
    assert uploaded.status_code == 201
    updated = client.put(
        f"/api/episodes/{episode['id']}/shots/{shot_id}/receipt",
        headers=auth,
        json={
            "media_id": uploaded.json()["id"],
            "duration_s": 10.125,
            "frames": 243,
            "still_vs_lock": "Manual note: lock holds in this fixture.",
            "source": "manual",
            "watched": True,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["source"] == "manual"
    assert updated.json()["preview_watched"] is True
    assert updated.json()["complete"] is True


def test_preview_mp4_allowed_other_mp4_refused(client, auth):
    _, episode = create_episode(client, auth, "Media kinds")
    import_green(client, auth, episode["id"])
    refused = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "other"},
        files={"file": ("clip.mp4", b"not-an-mp4", "video/mp4")},
    )
    assert refused.status_code == 400
    allowed = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "preview", "entity_label": "hop-1"},
        files={"file": ("clip.mp4", b"not-an-mp4", "video/mp4")},
    )
    assert allowed.status_code == 201
    assert allowed.json()["kind"] == "preview"


def test_json_preview_parses_duration(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Parse")
    shot_id = shots[0]["id"]
    payload = json.dumps({"duration_s": 9.5, "frames": 228, "still_vs_lock": "parsed lock note"}).encode()
    posted = client.post(
        f"/api/episodes/{episode['id']}/shots/{shot_id}/preview",
        headers=auth,
        files={"file": ("probe.json", payload, "application/json")},
    )
    assert posted.status_code == 201
    body = posted.json()
    assert body["duration_s"] == 9.5
    assert body["frames"] == 228
    assert body["still_vs_lock"] == "parsed lock note"
    assert body["preview_watched"] is False
    assert body["source"] == "parsed"
