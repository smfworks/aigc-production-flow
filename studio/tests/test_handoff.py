from tests.fixtures import green_pack, pack_zip_bytes, red_haft_pack
from tests.helpers import as_org, create_episode


def test_builder_handoff_stages_zip_then_imports_without_reupload(client, auth):
    _, episode = create_episode(client, auth, "Handoff")
    staged = client.post(
        "/api/handoffs",
        headers=auth,
        files={"file": ("from-builder.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    assert staged.status_code == 201, staged.text
    handoff = staged.json()
    assert handoff["auto_generate"] is False
    assert handoff["consumed"] is False
    assert "not auto-generate" in handoff["honesty"].lower() or "Never auto-generate" in handoff["honesty"]

    fetched = client.get(f"/api/handoffs/{handoff['id']}", headers=auth)
    assert fetched.status_code == 200
    assert fetched.json()["filename"] == "from-builder.zip"

    preview = client.post(
        f"/api/episodes/{episode['id']}/pack/diff",
        headers=auth,
        data={"handoff_id": handoff["id"]},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["right"]["candidate"] is True

    imported = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        data={"handoff_id": handoff["id"]},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["pack"]["title"] == "Green fixture"
    assert imported.json()["all_gates_green"] is True

    again = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        data={"handoff_id": handoff["id"]},
    )
    assert again.status_code == 409

    missing = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        data={"handoff_id": "does-not-exist"},
    )
    assert missing.status_code == 404


def test_handoff_id_wins_over_a_different_file_and_is_single_use(client, auth):
    _, episode = create_episode(client, auth, "Handoff wins")
    staged = client.post(
        "/api/handoffs",
        headers=auth,
        files={"file": ("from-builder.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    assert staged.status_code == 201, staged.text
    handoff_id = staged.json()["id"]
    imported = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        data={"handoff_id": handoff_id},
        files={"file": ("other.zip", pack_zip_bytes(red_haft_pack()), "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["pack"]["title"] == "Green fixture"
    again = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        data={"handoff_id": handoff_id},
    )
    assert again.status_code == 409


def test_uploaded_zip_does_not_consume_a_live_handoff(client, auth):
    _, episode = create_episode(client, auth, "Handoff kept")
    staged = client.post(
        "/api/handoffs",
        headers=auth,
        files={"file": ("from-builder.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    handoff_id = staged.json()["id"]
    imported = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("red.zip", pack_zip_bytes(red_haft_pack()), "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["pack"]["title"] == "Red haft fixture"
    still = client.get(f"/api/handoffs/{handoff_id}", headers=auth)
    assert still.status_code == 200
    assert still.json()["consumed"] is False


def test_handoff_rejects_other_org_episode_and_is_not_readable_across_orgs(client, auth):
    other = client.post("/api/orgs", headers=auth, json={"name": "Handoff lot"}).json()
    _, foreign = create_episode(client, as_org(auth, other["id"]), "Foreign episode")
    refused = client.post(
        "/api/handoffs",
        headers=auth,
        data={"episode_id": foreign["id"]},
        files={"file": ("from-builder.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    assert refused.status_code == 404

    staged = client.post(
        "/api/handoffs",
        headers=as_org(auth, other["id"]),
        files={"file": ("from-builder.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    assert staged.status_code == 201, staged.text
    hidden = client.get(f"/api/handoffs/{staged.json()['id']}", headers=auth)
    assert hidden.status_code == 404
