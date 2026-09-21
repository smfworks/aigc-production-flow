from tests.helpers import add_member, as_user, attach_watched_receipt, green_ready_episode, sign_off


def test_viewer_cannot_sign_off(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Signoff viewer")
    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    add_member(client, auth, "view-only", "viewer")
    blocked = client.post(
        f"/api/episodes/{episode['id']}/review/signoff",
        headers=as_user(auth, "view-only"),
        json={"note": "nope"},
    )
    assert blocked.status_code == 403


def test_editor_cannot_sign_off(client, auth):
    _, episode, _ = green_ready_episode(client, auth, "Signoff editor")
    add_member(client, auth, "ed", "editor")
    blocked = client.post(
        f"/api/episodes/{episode['id']}/review/signoff",
        headers=as_user(auth, "ed"),
        json={"note": "editors confirm shots, reviewers sign off"},
    )
    assert blocked.status_code == 403


def test_reviewer_signoff_unlocks_generate_ok(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Signoff reviewer")
    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    add_member(client, auth, "rev", "reviewer")
    add_member(client, auth, "ed", "editor")
    signed = client.post(
        f"/api/episodes/{episode['id']}/review/signoff",
        headers=as_user(auth, "rev"),
        json={"note": "hop-1 holds at the planned fades"},
    )
    assert signed.status_code == 201, signed.text
    assert signed.json()["signed_off"] is True
    assert signed.json()["signoffs"][0]["user_name"] == "rev"
    assert signed.json()["signoffs"][0]["role"] == "reviewer"

    ok = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=as_user(auth, "ed"),
        json={"state": "generate-ok", "note": "editor stamps after reviewer sign-off"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["current"] == "generate-ok"

    audit = client.get("/api/audit", headers=auth, params={"episode_id": episode["id"]})
    actions = {row["action"] for row in audit.json()}
    assert "review.signoff" in actions
    assert "review.set" in actions


def test_producer_override_is_audited(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Signoff override")
    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    refused = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "no sign-off"},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "review_unsigned"

    add_member(client, auth, "ed", "editor")
    editor_override = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=as_user(auth, "ed"),
        json={"state": "generate-ok", "note": "editor cannot override", "override": True},
    )
    assert editor_override.status_code == 403

    overridden = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "producer override: schedule", "override": True},
    )
    assert overridden.status_code == 200, overridden.text
    assert overridden.json()["current"] == "generate-ok"
    assert overridden.json()["signed_off"] is False

    audit = client.get("/api/audit", headers=auth, params={"episode_id": episode["id"]})
    actions = [row["action"] for row in audit.json()]
    assert "review.override" in actions
    override = next(row for row in audit.json() if row["action"] == "review.override")
    assert override["actor"] == "tester"


def test_producer_can_sign_off(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Signoff producer")
    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    sign_off(client, auth, episode["id"], "producer as reviewer")
    ok = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok"},
    )
    assert ok.status_code == 200
    assert ok.json()["signed_off"] is True
