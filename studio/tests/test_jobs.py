from tests.helpers import (
    attach_watched_receipt,
    create_episode,
    green_ready_episode,
    wait_job,
)


def test_batch_precheck_fails_without_green_pack(client, auth):
    _, episode = create_episode(client, auth, "Precheck red")
    response = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "batch-precheck"},
    )
    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "failed"
    assert job["adapter"] == "stub"
    assert job["result"]["engine"] is None
    assert "No H3 or Qwen process ran" in job["result"]["claim"]
    codes = {row["code"] for row in job["result"]["problems"]}
    assert "no_pack" in codes or "gates_not_green" in codes


def test_path_green_precheck_stub_hop1_receipt_generate_ok(client, auth):
    project, episode, shots = green_ready_episode(client, auth, "Happy path")
    shot_id = shots[0]["id"]
    assert shots[0]["hop1_required"] is True

    blocked_hop = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": shot_id, "job_type": "clip-hop1"},
    )
    # ready + green + T2V none+why should allow hop-1
    assert blocked_hop.status_code == 201, blocked_hop.text
    hop = blocked_hop.json()
    assert hop["status"] == "succeeded"
    assert hop["adapter"] == "stub"
    assert hop["result"]["engine"] is None
    assert hop["result"]["adapter"] == "stub"
    assert "No H3 or Qwen process ran" in hop["result"]["claim"]
    assert hop["media_id"]
    dumped = str(hop["result"]).lower()
    assert "qwen ran" not in dumped
    assert "h3 ran" not in dumped
    receipt = client.get(
        f"/api/episodes/{episode['id']}/shots/{shot_id}/receipt",
        headers=auth,
    ).json()
    assert receipt["media_id"] == hop["media_id"]
    assert receipt["preview_watched"] is False
    assert receipt["duration_s"] == 10.125
    assert receipt["frames"] == 243

    precheck = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "batch-precheck"},
    )
    assert precheck.status_code == 201
    assert precheck.json()["status"] == "succeeded"
    assert precheck.json()["result"]["ok"] is True

    generate_blocked = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok"},
    )
    assert generate_blocked.status_code == 409
    assert generate_blocked.json()["detail"]["code"] == "preview_incomplete"

    extend_blocked = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": shot_id, "job_type": "clip-extend"},
    )
    assert extend_blocked.status_code == 409
    assert extend_blocked.json()["detail"]["code"] == "preview_incomplete"

    receipt = attach_watched_receipt(client, auth, episode["id"], shot_id)
    assert receipt["preview_watched"] is True
    assert receipt["complete"] is True
    assert receipt["duration_s"] == 10.125
    assert receipt["frames"] == 243

    ok = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "watched stub hop-1"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["current"] == "generate-ok"

    extend = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": shot_id, "job_type": "clip-extend"},
    )
    assert extend.status_code == 201, extend.text
    assert extend.json()["status"] == "succeeded"
    assert extend.json()["adapter"] == "stub"

    listed = client.get("/api/jobs", headers=auth)
    assert listed.status_code == 200
    types = {row["job_type"] for row in listed.json()}
    assert "clip-hop1" in types
    assert "batch-precheck" in types
    hop_row = next(row for row in listed.json() if row["id"] == hop["id"])
    assert hop_row["project_name"] == project["name"]
    assert hop_row["episode_title"] == episode["title"]
    assert hop_row["elapsed_ms"] >= 0


def test_hop1_refused_until_shot_ready(client, auth):
    _, episode = create_episode(client, auth, "Not ready")
    from tests.helpers import import_green

    import_green(client, auth, episode["id"])
    shot = client.get(f"/api/episodes/{episode['id']}/shots", headers=auth).json()[0]
    response = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": shot["id"], "job_type": "clip-hop1"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "batch_precheck_failed"


def test_cancel_queued_and_retry(queued_client, auth):
    _, episode, shots = green_ready_episode(queued_client, auth, "Cancel queue")
    enqueued = queued_client.post(
        "/api/jobs",
        headers=auth,
        json={
            "episode_id": episode["id"],
            "shot_id": shots[0]["id"],
            "job_type": "clip-hop1",
        },
    )
    assert enqueued.status_code == 201
    job = enqueued.json()
    assert job["status"] == "queued"
    cancelled = queued_client.post(f"/api/jobs/{job['id']}/cancel", headers=auth)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    retry = queued_client.post(f"/api/jobs/{job['id']}/retry", headers=auth)
    assert retry.status_code == 201
    cloned = retry.json()
    assert cloned["id"] != job["id"]
    assert cloned["retry_of_id"] == job["id"]
    assert cloned["status"] == "queued"

    refuse_retry_queued = queued_client.post(f"/api/jobs/{cloned['id']}/retry", headers=auth)
    assert refuse_retry_queued.status_code == 409


def test_cancel_running(thread_client, auth):
    _, episode, shots = green_ready_episode(thread_client, auth, "Cancel running")
    enqueued = thread_client.post(
        "/api/jobs",
        headers=auth,
        json={
            "episode_id": episode["id"],
            "shot_id": shots[0]["id"],
            "job_type": "clip-hop1",
            "payload": {"debug_sleep_s": 2.5},
        },
    )
    assert enqueued.status_code == 201
    job_id = enqueued.json()["id"]
    running = None
    for _ in range(40):
        running = thread_client.get(f"/api/jobs/{job_id}", headers=auth).json()
        if running["status"] == "running":
            break
        if running["status"] in {"succeeded", "failed", "cancelled"}:
            break
    assert running["status"] == "running", running
    cancelled = thread_client.post(f"/api/jobs/{job_id}/cancel", headers=auth)
    assert cancelled.status_code == 200
    finished = wait_job(thread_client, auth, job_id)
    assert finished["status"] == "cancelled"


def test_still_jobs_label_stub(client, auth):
    _, episode, _ = green_ready_episode(client, auth, "Stills")
    sheet = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "still-sheet", "payload": {"entity": "smith"}},
    )
    assert sheet.status_code == 201
    body = sheet.json()
    assert body["status"] == "succeeded"
    assert body["adapter"] == "stub"
    assert body["result"]["engine"] is None
    assert "Qwen" in body["result"]["claim"] and "ran" in body["result"]["claim"]

    plate = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "still-plate", "payload": {"entity": "smith", "take": "A"}},
    )
    assert plate.json()["adapter"] == "stub"
    assert plate.json()["result"]["adapter"] == "stub"
