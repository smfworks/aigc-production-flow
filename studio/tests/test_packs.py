from tests.fixtures import green_pack, pack_zip_bytes, red_haft_pack


def _episode(client, auth):
    project = client.post("/api/projects", json={"name": "Pack job"}, headers=auth).json()
    episode = client.post(
        f"/api/projects/{project['id']}/episodes",
        json={"title": "Ep 1"},
        headers=auth,
    ).json()
    return episode


def test_import_export_pack_zip_round_trip(client, auth):
    episode = _episode(client, auth)
    payload = pack_zip_bytes(green_pack())
    imported = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("pack-green.zip", payload, "application/zip")},
    )
    assert imported.status_code == 201
    body = imported.json()
    assert body["all_gates_green"] is True
    assert body["pack"]["title"] == "Green fixture"
    assert len(body["gate_snapshot"]["gates"]) == 11
    assert {gate["id"] for gate in body["gate_snapshot"]["gates"]} >= {
        "entity-schedule",
        "lock-diff",
    }

    exported = client.get(f"/api/episodes/{episode['id']}/pack", headers=auth)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/zip")
    assert exported.content == payload

    gates = client.get(f"/api/episodes/{episode['id']}/gates", headers=auth)
    assert gates.json()["all_green"] is True


def test_import_rejects_zip_without_pack_json(client, auth):
    import io
    import zipfile

    episode = _episode(client, auth)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("README.md", "no pack json")
    response = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("empty.zip", buf.getvalue(), "application/zip")},
    )
    assert response.status_code == 400
    assert "pack.json" in response.json()["detail"]


def test_red_pack_snapshot_is_not_all_green(client, auth):
    episode = _episode(client, auth)
    imported = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("pack-red.zip", pack_zip_bytes(red_haft_pack()), "application/zip")},
    )
    assert imported.status_code == 201
    assert imported.json()["all_gates_green"] is False
    props = next(
        gate for gate in imported.json()["gate_snapshot"]["gates"] if gate["id"] == "props"
    )
    assert props["ok"] is False
