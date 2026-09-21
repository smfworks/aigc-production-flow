from tests.fixtures import green_pack, pack_zip_bytes, red_haft_pack
from tests.helpers import attach_watched_receipt, ready_all_shots


def _episode(client, auth):
    project = client.post("/api/projects", json={"name": "Review job"}, headers=auth).json()
    return client.post(
        f"/api/projects/{project['id']}/episodes",
        json={"title": "Ep 1"},
        headers=auth,
    ).json()


def test_review_states_and_generate_ok_honesty(client, auth):
    episode = _episode(client, auth)
    draft = client.put(
        f"/api/episodes/{episode['id']}/review",
        json={"state": "draft", "note": "start"},
        headers=auth,
    )
    assert draft.status_code == 200
    assert draft.json()["current"] == "draft"

    blocked = client.put(
        f"/api/episodes/{episode['id']}/review",
        json={"state": "generate-ok"},
        headers=auth,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "gates_not_green"

    client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("red.zip", pack_zip_bytes(red_haft_pack()), "application/zip")},
    )
    still_blocked = client.put(
        f"/api/episodes/{episode['id']}/review",
        json={"state": "generate-ok"},
        headers=auth,
    )
    assert still_blocked.status_code == 409
    assert still_blocked.json()["detail"]["gates"]

    art = client.put(
        f"/api/episodes/{episode['id']}/review",
        json={"state": "needs-art", "note": "haft unpinned"},
        headers=auth,
    )
    assert art.json()["current"] == "needs-art"

    client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("green.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    still_preview = client.put(
        f"/api/episodes/{episode['id']}/review",
        json={"state": "generate-ok", "note": "nine green, no hop-1 receipt"},
        headers=auth,
    )
    assert still_preview.status_code == 409
    assert still_preview.json()["detail"]["code"] == "preview_incomplete"

    shots = ready_all_shots(client, auth, episode["id"])
    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    ok = client.put(
        f"/api/episodes/{episode['id']}/review",
        json={"state": "generate-ok", "note": "gates green, hop-1 watched"},
        headers=auth,
    )
    assert ok.status_code == 200
    assert ok.json()["current"] == "generate-ok"
    assert ok.json()["latest_gates"]["all_green"] is True
    assert len(ok.json()["history"]) >= 3
