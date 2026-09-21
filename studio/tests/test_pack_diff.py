from app.packdiff import diff_packs
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


def _schedule_row(row_id: str, hold: bool) -> dict:
    return {
        "id": row_id,
        "entityKind": "character",
        "entityName": "smith",
        "take": "A",
        "windows": "all",
        "identityHold": hold,
    }


def test_entity_schedule_rows_with_shared_natural_key_do_not_collapse():
    """Known collapse: two rows share kind/name/take/windows and used to become one."""
    left = {
        "entitySchedule": [
            _schedule_row("row-a", True),
            _schedule_row("row-b", False),
        ]
    }
    right = {
        "entitySchedule": [
            _schedule_row("row-a", False),
            _schedule_row("row-b", False),
        ]
    }
    diff = diff_packs(left, right)
    changed = diff["entity_schedule"]["changed"]
    assert diff["summary"]["schedule_changed"] is True
    assert [row["key"] for row in changed] == ["row-a"]
    assert changed[0]["fields"]["identityHold"]["from"] in {"True", "true"}
    assert "row-b" not in {row["key"] for row in changed}
    assert diff["entity_schedule"]["removed"] == []
    assert diff["entity_schedule"]["added"] == []
    assert diff["entity_schedule"]["ambiguous"]
    assert "not collapsed" in diff["entity_schedule"]["ambiguous"][0]["note"]

    dropped = diff_packs(
        left,
        {"entitySchedule": [_schedule_row("row-b", False)]},
    )
    removed_keys = {row["key"] for row in dropped["entity_schedule"]["removed"]}
    assert removed_keys == {"row-a"}
    assert dropped["summary"]["schedule_changed"] is True


def test_idless_duplicate_schedule_rows_stay_distinct_and_ambiguous():
    natural = {
        "entityKind": "prop",
        "entityName": "francisca",
        "take": "*",
        "windows": "all",
    }
    left = {
        "entitySchedule": [
            {**natural, "identityHold": True},
            {**natural, "identityHold": False},
        ]
    }
    right = {"entitySchedule": [{**natural, "identityHold": True}]}
    diff = diff_packs(left, right)
    schedule = diff["entity_schedule"]
    assert schedule["ambiguous"]
    assert schedule["ambiguous"][0]["matched_by"] == "occurrence"
    assert schedule["removed"]
    assert diff["summary"]["schedule_changed"] is True
    tracked = len(schedule["added"]) + len(schedule["removed"]) + len(schedule["changed"])
    assert tracked >= 1
    assert len(schedule["removed"]) + len(schedule["changed"]) >= 1
