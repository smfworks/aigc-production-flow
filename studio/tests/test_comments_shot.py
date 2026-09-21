from tests.helpers import add_member, as_user, create_episode, green_ready_episode


def test_shot_comment_thread_and_resolve(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Shot comments")
    shot_id = shots[0]["id"]
    created = client.post(
        f"/api/episodes/{episode['id']}/comments",
        headers=auth,
        json={"body": "Still-vs-lock is off on this hop-1.", "shot_id": shot_id},
    )
    assert created.status_code == 201, created.text
    assert created.json()["shot_id"] == shot_id
    assert created.json()["resolved"] is False

    listed = client.get(
        f"/api/episodes/{episode['id']}/comments",
        headers=auth,
        params={"shot_id": shot_id},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["body"].startswith("Still-vs-lock")

    resolved = client.post(f"/api/comments/{created.json()['id']}/resolve", headers=auth)
    assert resolved.status_code == 200
    assert resolved.json()["resolved"] is True
    assert resolved.json()["resolved_by"] == "tester"

    audit = client.get(
        "/api/audit",
        headers=auth,
        params={"episode_id": episode["id"], "action": "comment.create"},
    )
    assert audit.status_code == 200
    assert audit.json()
    resolve_audit = client.get(
        "/api/audit",
        headers=auth,
        params={"episode_id": episode["id"], "action": "comment.resolve"},
    )
    assert resolve_audit.json()


def test_editor_comments_on_shot_after_promote(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Promote then comment")
    add_member(client, auth, "pat", "viewer")
    viewer = as_user(auth, "pat")
    blocked = client.post(
        f"/api/episodes/{episode['id']}/comments",
        headers=viewer,
        json={"body": "as viewer", "shot_id": shots[0]["id"]},
    )
    assert blocked.status_code == 403

    from tests.helpers import org_id

    oid = org_id(client, auth)
    member = next(
        row
        for row in client.get(f"/api/orgs/{oid}/members", headers=auth).json()
        if row["user_name"] == "pat"
    )
    client.patch(f"/api/orgs/{oid}/members/{member['id']}", headers=auth, json={"role": "editor"})
    ok = client.post(
        f"/api/episodes/{episode['id']}/comments",
        headers=as_user(auth, "pat"),
        json={"body": "as editor on the shot", "shot_id": shots[0]["id"]},
    )
    assert ok.status_code == 201
    assert ok.json()["author"] == "pat"


def test_board_node_comment(client, auth):
    _, episode = create_episode(client, auth, "Board comments")
    created = client.post(
        f"/api/episodes/{episode['id']}/comments",
        headers=auth,
        json={"body": "Join should be fadeblack.", "board_node_id": "take-a"},
    )
    assert created.status_code == 201
    listed = client.get(
        f"/api/episodes/{episode['id']}/comments",
        headers=auth,
        params={"board_node_id": "take-a"},
    )
    assert listed.json()[0]["board_node_id"] == "take-a"
