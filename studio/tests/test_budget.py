from tests.helpers import create_episode, green_ready_episode


def test_adapter_catalog_lists_documented_slots(client, auth):
    response = client.get("/api/adapters", headers=auth)
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["adapters"]}
    assert ids == {"stub", "comfy-h3", "comfy-qwen", "webhook", "cli", "grok-imagine"}
    live = {row["id"]: row["live"] for row in response.json()["adapters"]}
    assert live["stub"] is False
    assert live["comfy-h3"] is True
    assert live["comfy-qwen"] is True


def test_job_records_operator_cost_units(client, auth):
    _, episode, _ = green_ready_episode(client, auth, "Budget units")
    sheet = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "still-sheet"},
    )
    assert sheet.status_code == 201, sheet.text
    body = sheet.json()
    assert body["adapter"] == "stub"
    assert body["estimated_cost_units"] == 0.1
    assert body["actual_cost_units"] == 0.1
    assert body["cost_currency"] == "credits"
    assert "not a cloud bill" in body["cost_note"]
    assert body["result"]["engine"] is None

    precheck = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "batch-precheck"},
    )
    assert precheck.json()["estimated_cost_units"] == 0
    assert precheck.json()["actual_cost_units"] == 0


def test_budget_dashboard_and_hard_stop(client, auth):
    project, episode, _ = green_ready_episode(client, auth, "Cap project")
    patched = client.patch(
        f"/api/projects/{project['id']}",
        headers=auth,
        json={"budget_cap_units": 0.05, "budget_hard_stop": True, "still_adapter": "stub"},
    )
    assert patched.status_code == 200
    assert patched.json()["budget_hard_stop"] is True
    assert patched.json()["budget_cap_units"] == 0.05

    blocked = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "still-sheet"},
    )
    assert blocked.status_code == 409
    detail = blocked.json()["detail"]
    assert detail["code"] == "budget_cap"
    assert "not a cloud bill" in detail["disclaimer"].lower() or "operator" in detail["message"].lower()

    raised = client.patch(
        f"/api/projects/{project['id']}",
        headers=auth,
        json={"budget_cap_units": 10, "budget_hard_stop": True},
    )
    assert raised.status_code == 200
    ok = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "still-sheet"},
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["actual_cost_units"] == 0.1

    dash = client.get(f"/api/projects/{project['id']}/budget", headers=auth)
    assert dash.status_code == 200
    body = dash.json()
    assert "operator-configured" in body["disclaimer"].lower()
    assert body["spent_units"] == 0.1
    assert body["job_counts"]["succeeded"] >= 1
    assert body["adapter_mix"]["stub"] >= 1
    assert body["projects"][0]["episodes"][0]["episode_id"] == episode["id"]
    assert body["usd_estimate"] is None


def test_project_adapter_defaults_reject_wrong_kind(client, auth):
    _, episode = create_episode(client, auth, "Kind check")
    project_id = episode["project_id"] if "project_id" in episode else None
    listed = client.get("/api/projects", headers=auth).json()
    project_id = listed[0]["id"]
    bad = client.patch(
        f"/api/projects/{project_id}",
        headers=auth,
        json={"still_adapter": "comfy-h3"},
    )
    assert bad.status_code == 400
    good = client.patch(
        f"/api/projects/{project_id}",
        headers=auth,
        json={"clip_adapter": "comfy-h3", "still_adapter": "comfy-qwen"},
    )
    assert good.status_code == 200
    assert good.json()["clip_adapter"] == "comfy-h3"
    assert good.json()["still_adapter"] == "comfy-qwen"
