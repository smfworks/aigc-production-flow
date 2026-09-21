def test_demo_seed_is_honest_stub(client, auth):
    seeded = client.post("/api/demo/seed", headers=auth)
    assert seeded.status_code == 201, seeded.text
    body = seeded.json()
    assert body["fake_generate"] is False
    assert body["likeness"] is False
    assert body["engine_mp4"] is False
    assert body["template_id"] == "short-drama-ep"
    assert "fixture" in body["honesty"].lower() or "stub" in body["honesty"].lower()
    episode_id = body["episode"]["id"]
    media = client.get(f"/api/episodes/{episode_id}/media", headers=auth)
    assert media.status_code == 200
    assert len(media.json()) >= 1
    notes = " ".join(row.get("notes") or "" for row in media.json()).lower()
    assert "fixture" in notes
    assert "likeness" in notes
    revision = body["episode"].get("latest_revision") or {}
    assert revision.get("all_gates_green") is not True
