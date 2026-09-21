from tests.helpers import add_member, as_org, as_user, create_episode, wait_job


def test_job_success_creates_notification(client, auth):
    _, episode = create_episode(client, auth, "Notify job")
    job = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "batch-precheck"},
    )
    assert job.status_code == 201, job.text
    wait_job(client, auth, job.json()["id"])
    notes = client.get("/api/notifications", headers=auth)
    assert notes.status_code == 200, notes.text
    body = notes.json()
    kinds = {row["kind"] for row in body["items"]}
    assert "job.succeeded" in kinds or "job.failed" in kinds
    assert body["unread_count"] >= 1
    first = body["items"][0]
    marked = client.post(f"/api/notifications/{first['id']}/read", headers=auth)
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None


def test_comment_mention_notifies_member(client, auth):
    _, episode = create_episode(client, auth, "Notify mention")
    add_member(client, auth, "pat", "editor")
    comment = client.post(
        f"/api/episodes/{episode['id']}/comments",
        headers=auth,
        json={"body": "Hey @pat watch the hop-1."},
    )
    assert comment.status_code == 201, comment.text
    notes = client.get("/api/notifications", headers=as_user(auth, "pat"))
    assert notes.status_code == 200
    kinds = {row["kind"] for row in notes.json()["items"]}
    assert "comment.mention" in kinds


def test_meta_reports_webhook_unset(client, auth):
    meta = client.get("/api/meta", headers=auth).json()
    assert meta["notify_webhook_configured"] is False
    assert meta["multi_org"] is True


def test_notifications_scoped_to_active_org(client, auth):
    other = client.post("/api/orgs", headers=auth, json={"name": "Notify lot"}).json()
    switched = as_org(auth, other["id"])
    _, episode = create_episode(client, switched, "Hidden jobs")
    job = client.post(
        "/api/jobs",
        headers=switched,
        json={"episode_id": episode["id"], "job_type": "batch-precheck"},
    )
    assert job.status_code == 201, job.text
    finished = wait_job(client, switched, job.json()["id"])
    notes_b = client.get("/api/notifications", headers=switched).json()
    notes_a = client.get("/api/notifications", headers=auth).json()
    ids_b = {row["job_id"] for row in notes_b["items"]}
    ids_a = {row["job_id"] for row in notes_a["items"]}
    assert finished["id"] in ids_b
    assert finished["id"] not in ids_a
