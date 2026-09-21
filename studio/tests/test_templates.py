def test_list_vertical_templates(client, auth):
    response = client.get("/api/templates", headers=auth)
    assert response.status_code == 200
    rows = response.json()
    ids = {row["id"] for row in rows}
    assert {"education-lesson", "brand-promo", "short-drama-ep"} <= ids
    for row in rows:
        assert row["gates_green"] is False
        assert row["fake_generate"] is False
        assert row["stages"] == ["script", "assets", "storyboard", "preview"]
        assert row["still_adapter"] == "stub"
        assert row["clip_adapter"] == "stub"


def test_new_project_from_vertical_template(client, auth):
    created = client.post(
        "/api/templates/education-lesson/projects",
        headers=auth,
        json={"name": "Lesson 12"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["gates_green"] is False
    project = body["project"]
    episode = body["episode"]
    assert project["name"] == "Lesson 12"
    assert project["still_adapter"] == "stub"
    assert episode["title"] == "Ep 1"
    assert episode["latest_revision"]["all_gates_green"] is False

    review = client.get(f"/api/episodes/{episode['id']}/review", headers=auth)
    assert review.status_code == 200
    assert review.json()["latest_gates"]["all_green"] is False

    generate = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok"},
    )
    assert generate.status_code == 409

    audit = client.get("/api/audit", headers=auth, params={"project_id": project["id"]})
    actions = {row["action"] for row in audit.json()}
    assert "project.create" in actions
