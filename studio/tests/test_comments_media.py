TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _episode(client, auth):
    project = client.post("/api/projects", json={"name": "Notes"}, headers=auth).json()
    return client.post(
        f"/api/projects/{project['id']}/episodes",
        json={"title": "Ep 1"},
        headers=auth,
    ).json()


def test_comments_thread(client, auth):
    episode = _episode(client, auth)
    created = client.post(
        f"/api/episodes/{episode['id']}/comments",
        json={"body": "Haft is still none — not generate-ok.", "author": "editor"},
        headers=auth,
    )
    assert created.status_code == 201
    assert created.json()["author"] == "editor"
    listed = client.get(f"/api/episodes/{episode['id']}/comments", headers=auth)
    assert listed.status_code == 200
    assert listed.json()[0]["body"].startswith("Haft")
    assert listed.json()[0]["resolved"] is False


def test_media_upload_download_plate(client, auth):
    episode = _episode(client, auth)
    uploaded = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "plate", "entity_label": "take A hop-1", "notes": "1344x768 stand-in"},
        files={"file": ("take-a-hop1-plate.png", TINY_PNG, "image/png")},
    )
    assert uploaded.status_code == 201
    asset = uploaded.json()
    assert asset["kind"] == "plate"
    assert asset["entity_label"] == "take A hop-1"
    assert "take-a-hop1-plate" in asset["stored_name"]

    downloaded = client.get(f"/api/media/{asset['id']}", headers=auth)
    assert downloaded.status_code == 200
    assert downloaded.content == TINY_PNG

    listed = client.get(f"/api/episodes/{episode['id']}/media", headers=auth)
    assert listed.json()[0]["id"] == asset["id"]

    refused = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "other"},
        files={"file": ("clip.mp4", b"not-an-mp4", "video/mp4")},
    )
    assert refused.status_code == 400
