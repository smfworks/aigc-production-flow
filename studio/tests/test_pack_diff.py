from tests.fixtures import green_pack, pack_zip_bytes, red_haft_pack
from tests.helpers import create_episode, import_green


def test_diff_two_revisions(client, auth):
    _, episode = create_episode(client, auth, "Diff revs")
    first = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("green.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    assert first.status_code == 201, first.text
    left_id = first.json()["id"]

    red = red_haft_pack()
    red["editList"][0]["action"] = "changed title overlay"
    red["characters"][0]["lockParagraph"] = "Same face every hop, brown hair."
    second = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("red.zip", pack_zip_bytes(red), "application/zip")},
    )
    assert second.status_code == 201, second.text
    right_id = second.json()["id"]

    diffed = client.get(
        f"/api/episodes/{episode['id']}/revisions/{left_id}/diff/{right_id}",
        headers=auth,
    )
    assert diffed.status_code == 200, diffed.text
    body = diffed.json()
    assert body["auto_generate"] is False
    assert body["left"]["id"] == left_id
    assert body["right"]["id"] == right_id
    assert body["summary"]["changed"] is True
    assert any(gate["id"] == "props" and gate["changed"] for gate in body["gates"])
    assert body["edit_list"]["changed"]
    assert body["identity_keywords"]["changed"] or body["identity_keywords"]["added"]
    audit = client.get("/api/audit", headers=auth, params={"episode_id": episode["id"], "action": "pack.diff"})
    assert audit.status_code == 200
    assert audit.json()


def test_preview_candidate_import_diff_then_apply(client, auth):
    _, episode = create_episode(client, auth, "Diff import")
    import_green(client, auth, episode["id"])
    candidate = green_pack()
    candidate["title"] = "Candidate rewrite"
    candidate["editList"][0]["join"] = "cut"
    preview = client.post(
        f"/api/episodes/{episode['id']}/pack/diff",
        headers=auth,
        files={"file": ("candidate.zip", pack_zip_bytes(candidate), "application/zip")},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["right"]["candidate"] is True
    assert body["summary"]["edit_list_changed"] is True
    assert body["auto_generate"] is False

    applied = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("candidate.zip", pack_zip_bytes(candidate), "application/zip")},
    )
    assert applied.status_code == 201
    assert applied.json()["pack"]["title"] == "Candidate rewrite"
    audit = client.get("/api/audit", headers=auth, params={"episode_id": episode["id"]})
    actions = [row["action"] for row in audit.json()]
    assert "pack.diff" in actions
    assert "pack.import" in actions
