from tests.helpers import add_member, as_user, create_episode, green_ready_episode, org_id


def test_default_user_is_producer(client, auth):
    me = client.get("/api/me", headers=auth)
    assert me.status_code == 200
    body = me.json()
    assert body["name"] == "tester"
    assert body["role"] == "producer"
    members = client.get(f"/api/orgs/{body['org_id']}/members", headers=auth)
    assert members.status_code == 200
    names = {row["user_name"]: row["role"] for row in members.json()}
    assert names["tester"] == "producer"


def test_viewer_cannot_enqueue_until_promoted(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "RBAC enqueue")
    add_member(client, auth, "pat", "viewer")
    viewer = as_user(auth, "pat")
    me = client.get("/api/me", headers=viewer)
    assert me.json()["role"] == "viewer"

    blocked = client.post(
        "/api/jobs",
        headers=viewer,
        json={"episode_id": episode["id"], "job_type": "batch-precheck"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "forbidden_role"

    oid = org_id(client, auth)
    member = next(row for row in client.get(f"/api/orgs/{oid}/members", headers=auth).json() if row["user_name"] == "pat")
    promoted = client.patch(
        f"/api/orgs/{oid}/members/{member['id']}",
        headers=auth,
        json={"role": "editor"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "editor"

    ok = client.post(
        "/api/jobs",
        headers=as_user(auth, "pat"),
        json={"episode_id": episode["id"], "job_type": "batch-precheck"},
    )
    assert ok.status_code == 201, ok.text


def test_viewer_is_read_only_on_listed_mutations(client, auth):
    _, episode, _ = green_ready_episode(client, auth, "RBAC viewer")
    add_member(client, auth, "view-only", "viewer")
    viewer = as_user(auth, "view-only")

    listed = client.get(f"/api/episodes/{episode['id']}/shots", headers=viewer)
    assert listed.status_code == 200

    review = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=viewer,
        json={"state": "needs-art"},
    )
    assert review.status_code == 403

    pack = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=viewer,
        files={"file": ("x.zip", b"not-a-zip", "application/zip")},
    )
    assert pack.status_code == 403

    media = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=viewer,
        data={"kind": "other"},
        files={"file": ("note.txt", b"hi", "text/plain")},
    )
    assert media.status_code == 403

    comment = client.post(
        f"/api/episodes/{episode['id']}/comments",
        headers=viewer,
        json={"body": "nope"},
    )
    assert comment.status_code == 403


def test_editor_cannot_override_budget_or_apply_retention(client, auth):
    project, _, _ = green_ready_episode(client, auth, "RBAC producer-only")
    add_member(client, auth, "ed", "editor")
    editor = as_user(auth, "ed")

    adapters = client.patch(
        f"/api/projects/{project['id']}",
        headers=editor,
        json={"still_adapter": "stub"},
    )
    assert adapters.status_code == 200

    hard_stop = client.patch(
        f"/api/projects/{project['id']}",
        headers=editor,
        json={"budget_hard_stop": True, "budget_cap_units": 1},
    )
    assert hard_stop.status_code == 403

    apply = client.post(
        "/api/retention",
        headers=editor,
        json={"dry_run": False, "confirm": "expire", "project_id": project["id"]},
    )
    assert apply.status_code == 403

    dry = client.post(
        "/api/retention",
        headers=editor,
        json={"dry_run": True, "project_id": project["id"]},
    )
    assert dry.status_code == 200
    assert dry.json()["dry_run"] is True


def test_reviewer_can_comment_not_enqueue(client, auth):
    _, episode = create_episode(client, auth, "RBAC reviewer")
    add_member(client, auth, "rev", "reviewer")
    reviewer = as_user(auth, "rev")
    comment = client.post(
        f"/api/episodes/{episode['id']}/comments",
        headers=reviewer,
        json={"body": "NG the hop-1 still-vs-lock."},
    )
    assert comment.status_code == 201
    job = client.post(
        "/api/jobs",
        headers=reviewer,
        json={"episode_id": episode["id"], "job_type": "batch-precheck"},
    )
    assert job.status_code == 403


def test_unknown_user_is_not_a_member(client, auth):
    ghost = as_user(auth, "stranger")
    me = client.get("/api/me", headers=ghost)
    assert me.status_code == 200
    assert me.json()["role"] is None
    projects = client.get("/api/projects", headers=ghost)
    assert projects.status_code == 403


def test_viewer_cannot_manage_members(client, auth):
    add_member(client, auth, "view-only", "viewer")
    oid = org_id(client, auth)
    forbidden = client.post(
        f"/api/orgs/{oid}/members",
        headers=as_user(auth, "view-only"),
        json={"user_name": "another", "role": "viewer"},
    )
    assert forbidden.status_code == 403
