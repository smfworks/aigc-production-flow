def test_project_and_episode_crud(client, auth):
    created = client.post(
        "/api/projects",
        json={"name": "Sigils", "description": "Lyric reshoot"},
        headers=auth,
    )
    assert created.status_code == 201
    project = created.json()
    assert project["slug"] == "sigils"
    assert project["episode_count"] == 0

    listed = client.get("/api/projects", headers=auth)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == project["id"]

    episode = client.post(
        f"/api/projects/{project['id']}/episodes",
        json={"title": "Chapter 1", "synopsis": "Forge verse"},
        headers=auth,
    )
    assert episode.status_code == 201
    body = episode.json()
    assert body["chapter"] == 1
    assert body["review_state"] == "draft"
    assert body["latest_revision"] is None

    fetched = client.get(f"/api/episodes/{body['id']}", headers=auth)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Chapter 1"

    patched = client.patch(
        f"/api/episodes/{body['id']}",
        json={"title": "Ch. 1 — forge"},
        headers=auth,
    )
    assert patched.json()["title"] == "Ch. 1 — forge"

    clash = client.post(
        f"/api/projects/{project['id']}/episodes",
        json={"title": "Dup", "chapter": 1},
        headers=auth,
    )
    assert clash.status_code == 409

    deleted = client.delete(f"/api/episodes/{body['id']}", headers=auth)
    assert deleted.status_code == 204
    missing = client.get(f"/api/episodes/{body['id']}", headers=auth)
    assert missing.status_code == 404
