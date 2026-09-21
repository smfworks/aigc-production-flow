from tests.fixtures import green_pack, pack_zip_bytes
from tests.helpers import create_episode


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
