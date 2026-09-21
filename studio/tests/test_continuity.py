from tests.helpers import create_episode, import_green


def test_continuity_summary_from_imported_pack(client, auth):
    project, episode = create_episode(client, auth, "Continuity")
    empty = client.get(f"/api/episodes/{episode['id']}/continuity", headers=auth)
    assert empty.status_code == 200, empty.text
    assert empty.json()["honesty"]
    assert "NLE" in empty.json()["honesty"]

    import_green(client, auth, episode["id"])
    summary = client.get(f"/api/episodes/{episode['id']}/continuity", headers=auth)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["episode_id"] == episode["id"]
    assert body["project_id"] == project["id"]
    assert isinstance(body["entity_schedule_problems"], list)
    assert isinstance(body["lock_diff_problems"], list)
    assert isinstance(body["shots"], list)
    if body["shots"]:
        assert body["shots"][0]["href"].startswith("#/projects/")
        assert "/shots/" in body["shots"][0]["href"]
