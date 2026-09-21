from tests.helpers import add_member, as_org, as_user, create_episode, org_id


def test_create_second_org_and_switch(client, auth):
    default = org_id(client, auth)
    created = client.post("/api/orgs", headers=auth, json={"name": "Second studio"})
    assert created.status_code == 201, created.text
    other = created.json()
    assert other["is_default"] is False
    assert "not SaaS" in other["note"]
    assert other["role"] == "producer"

    listed = client.get("/api/orgs", headers=auth)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert default in ids
    assert other["id"] in ids

    project_a, _ = create_episode(client, auth, "Org A show")
    switched = as_org(auth, other["id"])
    me = client.get("/api/me", headers=switched)
    assert me.status_code == 200
    assert me.json()["org_id"] == other["id"]
    assert me.json()["role"] == "producer"
    assert me.json()["multi_org"] is True

    project_b = client.post("/api/projects", headers=switched, json={"name": "Org B show"})
    assert project_b.status_code == 201, project_b.text

    default_list = client.get("/api/projects", headers=auth).json()
    other_list = client.get("/api/projects", headers=switched).json()
    assert project_a["id"] in {row["id"] for row in default_list}
    assert project_b.json()["id"] not in {row["id"] for row in default_list}
    assert project_b.json()["id"] in {row["id"] for row in other_list}
    assert project_a["id"] not in {row["id"] for row in other_list}


def test_member_cannot_see_other_org(client, auth):
    default = org_id(client, auth)
    other = client.post("/api/orgs", headers=auth, json={"name": "Private lot"}).json()
    hidden = client.post(
        "/api/projects",
        headers=as_org(auth, other["id"]),
        json={"name": "Hidden title"},
    ).json()
    add_member(client, auth, "pat", "viewer")
    viewer = as_user(auth, "pat")

    orgs = client.get("/api/orgs", headers=viewer)
    assert orgs.status_code == 200
    assert {row["id"] for row in orgs.json()} == {default}

    listed = client.get("/api/projects", headers=viewer)
    assert listed.status_code == 200
    assert hidden["id"] not in {row["id"] for row in listed.json()}

    missing = client.get(f"/api/projects/{hidden['id']}", headers=viewer)
    assert missing.status_code == 404

    foreign = client.get("/api/projects", headers=as_org(viewer, other["id"]))
    assert foreign.status_code == 403


def test_seed_demo_stays_in_active_org(client, auth):
    other = client.post("/api/orgs", headers=auth, json={"name": "Demo lot"}).json()
    switched = as_org(auth, other["id"])
    seeded = client.post("/api/demo/seed", headers=switched)
    assert seeded.status_code == 201, seeded.text
    project_id = seeded.json()["project"]["id"]
    hidden = client.get(f"/api/projects/{project_id}", headers=auth)
    assert hidden.status_code == 404
    visible = client.get(f"/api/projects/{project_id}", headers=switched)
    assert visible.status_code == 200


def test_seed_keeps_default_org(client, auth):
    me = client.get("/api/me", headers=auth).json()
    orgs = client.get("/api/orgs", headers=auth).json()
    default = next(row for row in orgs if row["id"] == me["org_id"])
    assert default["is_default"] is True
    assert "local" in default["name"].lower()
