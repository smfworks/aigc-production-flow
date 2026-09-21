from tests.helpers import green_ready_episode


def test_audit_covers_review_jobs_pack_media(client, auth):
    project, episode, shots = green_ready_episode(client, auth, "Audit trail")
    episode_id = episode["id"]

    review = client.put(
        f"/api/episodes/{episode_id}/review",
        headers=auth,
        json={"state": "needs-art", "note": "sheets"},
    )
    assert review.status_code == 200

    job = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode_id, "job_type": "still-sheet"},
    )
    assert job.status_code == 201

    media = client.post(
        f"/api/episodes/{episode_id}/media",
        headers=auth,
        data={"kind": "other", "notes": "temp note"},
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert media.status_code == 201

    exported = client.get(f"/api/episodes/{episode_id}/pack", headers=auth)
    assert exported.status_code == 200

    all_rows = client.get("/api/audit", headers=auth)
    assert all_rows.status_code == 200
    actions = {row["action"] for row in all_rows.json()}
    assert "pack.import" in actions
    assert "review.set" in actions
    assert "job.enqueue" in actions
    assert "media.upload" in actions
    assert "pack.export" in actions

    filtered = client.get(
        "/api/audit",
        headers=auth,
        params={"episode_id": episode_id, "action": "review.set"},
    )
    assert filtered.status_code == 200
    rows = filtered.json()
    assert rows
    assert all(row["episode_id"] == episode_id for row in rows)
    assert all(row["action"] == "review.set" for row in rows)
    assert rows[0]["actor"] == "tester"
    assert rows[0]["project_id"] == project["id"]

    by_project = client.get("/api/audit", headers=auth, params={"project_id": project["id"]})
    assert by_project.status_code == 200
    assert len(by_project.json()) >= len(rows)


def test_cancel_is_audited(queued_client, auth):
    _, episode, shots = green_ready_episode(queued_client, auth, "Audit cancel")
    enqueued = queued_client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": shots[0]["id"], "job_type": "clip-hop1"},
    )
    assert enqueued.status_code == 201
    cancelled = queued_client.post(f"/api/jobs/{enqueued.json()['id']}/cancel", headers=auth)
    assert cancelled.status_code == 200
    rows = queued_client.get(
        "/api/audit",
        headers=auth,
        params={"episode_id": episode["id"], "action": "job.cancel"},
    ).json()
    assert rows
    assert rows[0]["entity_id"] == enqueued.json()["id"]
