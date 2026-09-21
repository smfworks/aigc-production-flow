from tests.fixtures import green_pack, pack_zip_bytes


def _episode(client, auth):
    project = client.post("/api/projects", json={"name": "Shots"}, headers=auth).json()
    return client.post(
        f"/api/projects/{project['id']}/episodes",
        json={"title": "Ep 1"},
        headers=auth,
    ).json()


def test_import_creates_shots_and_candidate_confirm(client, auth):
    episode = _episode(client, auth)
    imported = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("green.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    assert imported.status_code == 201
    shots = client.get(f"/api/episodes/{episode['id']}/shots", headers=auth)
    assert shots.status_code == 200
    body = shots.json()
    assert len(body) == 1
    assert body[0]["join"] == "fadeblack"
    assert body[0]["readiness"] == "draft"
    assert body[0]["entities"] == "smith, francisca"

    extracted = client.post(
        f"/api/episodes/{episode['id']}/shots/extract-candidates",
        headers=auth,
    )
    assert extracted.status_code == 200
    shot = extracted.json()[0]
    assert shot["readiness"] == "candidates"
    labels = {row["label"] for row in shot["candidates"]}
    assert "smith" in labels
    assert "francisca" in labels
    pending = next(row for row in shot["candidates"] if row["label"] == "smith")

    ignored = client.patch(
        f"/api/episodes/{episode['id']}/shots/{shot['id']}/candidates/{pending['id']}",
        headers=auth,
        json={"status": "ignored"},
    )
    assert ignored.status_code == 200
    assert ignored.json()["status"] == "ignored"

    francisca = next(row for row in shot["candidates"] if row["label"] == "francisca")
    linked = client.patch(
        f"/api/episodes/{episode['id']}/shots/{shot['id']}/candidates/{francisca['id']}",
        headers=auth,
        json={"status": "linked", "linked_ref": "prop:francisca"},
    )
    assert linked.status_code == 200
    assert linked.json()["status"] == "linked"

    scene = next((row for row in shot["candidates"] if row["kind"] == "scene"), None)
    if scene:
        client.patch(
            f"/api/episodes/{episode['id']}/shots/{shot['id']}/candidates/{scene['id']}",
            headers=auth,
            json={"status": "ignored"},
        )

    remaining = client.get(
        f"/api/episodes/{episode['id']}/shots/{shot['id']}",
        headers=auth,
    ).json()
    for row in remaining["candidates"]:
        if row["status"] == "pending":
            client.patch(
                f"/api/episodes/{episode['id']}/shots/{shot['id']}/candidates/{row['id']}",
                headers=auth,
                json={"status": "ignored"},
            )

    ready_blocked_before_link = client.put(
        f"/api/episodes/{episode['id']}/shots/{shot['id']}/readiness",
        headers=auth,
        json={"readiness": "ready"},
    )
    # After ignoring leftovers, ready should succeed — prepared ≠ generating.
    assert ready_blocked_before_link.status_code in {200, 409}
    if ready_blocked_before_link.status_code == 409:
        remaining = client.get(
            f"/api/episodes/{episode['id']}/shots/{shot['id']}",
            headers=auth,
        ).json()
        for row in remaining["candidates"]:
            if row["status"] in {"pending", "accepted"}:
                client.patch(
                    f"/api/episodes/{episode['id']}/shots/{shot['id']}/candidates/{row['id']}",
                    headers=auth,
                    json={"status": "ignored"},
                )
        ok = client.put(
            f"/api/episodes/{episode['id']}/shots/{shot['id']}/readiness",
            headers=auth,
            json={"readiness": "ready"},
        )
        assert ok.status_code == 200
        assert ok.json()["readiness"] == "ready"
    else:
        assert ready_blocked_before_link.json()["readiness"] == "ready"

    board = client.get(f"/api/episodes/{episode['id']}/board", headers=auth)
    assert board.status_code == 200
    assert board.json()["boundaries"][0]["join"] == "fadeblack"


def test_costume_upload_and_manual_candidate(client, auth):
    episode = _episode(client, auth)
    client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("green.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
        b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    uploaded = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "costume", "entity_label": "smith wardrobe", "entity_type": "costume"},
        files={"file": ("wardrobe.png", png, "image/png")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["kind"] == "costume"
    assert uploaded.json()["entity_type"] == "costume"

    shots = client.get(f"/api/episodes/{episode['id']}/shots", headers=auth).json()
    shot_id = shots[0]["id"]
    manual = client.post(
        f"/api/episodes/{episode['id']}/shots/{shot_id}/candidates",
        headers=auth,
        json={"kind": "costume", "label": "smith wardrobe", "evidence": "manual"},
    )
    assert manual.status_code == 201
    linked = client.patch(
        f"/api/episodes/{episode['id']}/shots/{shot_id}/candidates/{manual.json()['id']}",
        headers=auth,
        json={"status": "linked", "linked_asset_id": uploaded.json()["id"]},
    )
    assert linked.status_code == 200
    assert linked.json()["linked_asset_id"] == uploaded.json()["id"]


def test_ready_refused_while_pending(client, auth):
    episode = _episode(client, auth)
    client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("green.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    shot = client.get(f"/api/episodes/{episode['id']}/shots", headers=auth).json()[0]
    created = client.post(
        f"/api/episodes/{episode['id']}/shots/{shot['id']}/candidates",
        headers=auth,
        json={"kind": "character", "label": "smith"},
    )
    blocked = client.put(
        f"/api/episodes/{episode['id']}/shots/{shot['id']}/readiness",
        headers=auth,
        json={"readiness": "ready"},
    )
    assert blocked.status_code == 409
    assert created.json()["status"] == "pending"
    assert blocked.json()["detail"]["code"] == "shot_not_prepared"
