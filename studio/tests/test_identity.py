from sqlalchemy.orm.attributes import flag_modified

from app.database import SessionLocal
from app.models import Episode, PackRevision
from tests.fixtures import pack_zip_bytes, green_pack
from tests.helpers import (
    attach_watched_receipt,
    create_episode,
    green_ready_episode,
    import_green,
    sign_off,
)


def test_identity_approve_and_link_plate(client, auth):
    project, episode = create_episode(client, auth, "Identity")
    import_green(client, auth, episode["id"])
    shots = client.get(f"/api/episodes/{episode['id']}/shots", headers=auth).json()
    shot = shots[0]
    fixture = (
        b'{"kind":"sheet","entity":"smith","claim":"Fixture metadata only. No likeness still."}'
    )
    sheet = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={
            "kind": "sheet",
            "entity_label": "smith",
            "entity_type": "character",
            "notes": "fixture metadata only — no likeness",
        },
        files={"file": ("smith-sheet.fixture.json", fixture, "application/json")},
    )
    assert sheet.status_code == 201, sheet.text
    body = sheet.json()
    assert body["approval_status"] == "draft"
    assert body["approved"] is False

    listed = client.get(f"/api/episodes/{episode['id']}/identity", headers=auth)
    assert listed.status_code == 200, listed.text
    store = listed.json()
    assert store["embeddings"] is False
    assert store["likeness"] is False
    assert any(row["id"] == body["id"] for row in store["sheets"])
    assert "not embeddings" in store["honesty"].lower() or "Not embeddings" in store["honesty"]

    approved = client.post(
        f"/api/episodes/{episode['id']}/identity/{body['id']}/approve",
        headers=auth,
        json={"note": "lock looks right"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["approval_status"] == "approved"
    assert approved.json()["approved"] is True
    assert approved.json()["approved_by"] == "tester"
    assert approved.json()["approved_at"]

    plate_bytes = b'{"kind":"plate","entity":"smith","claim":"Fixture metadata only. Not a hop-1 frame."}'
    plate = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={
            "kind": "plate",
            "entity_label": "smith",
            "entity_type": "character",
            "notes": "fixture metadata only — no likeness",
        },
        files={"file": ("smith-plate.fixture.json", plate_bytes, "application/json")},
    )
    assert plate.status_code == 201, plate.text
    plate_id = plate.json()["id"]
    assert plate.json()["approved"] is False

    linked = client.post(
        f"/api/episodes/{episode['id']}/identity/{plate_id}/link",
        headers=auth,
        json={
            "shot_id": shot["id"],
            "lock_keywords": "same face every hop",
        },
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["shot_id"] == shot["id"]
    assert linked.json()["edit_row_id"] == shot["edit_row_id"]

    still_draft = client.get(f"/api/episodes/{episode['id']}/identity", headers=auth).json()
    plate_row = next(row for row in still_draft["plates"] if row["id"] == plate_id)
    assert plate_row["approved"] is False
    assert plate_row["href"].endswith(f"/identity/{plate_id}")

    approve_plate = client.post(
        f"/api/episodes/{episode['id']}/identity/{plate_id}/approve",
        headers=auth,
        json={},
    )
    assert approve_plate.status_code == 200
    assert approve_plate.json()["approved"] is True

    continuity = client.get(f"/api/episodes/{episode['id']}/continuity", headers=auth).json()
    assert continuity["identity"]["approved_sheet_count"] >= 1
    assert continuity["identity"]["approved_plate_count"] >= 1
    assert continuity["identity_href"].endswith("/identity")
    shot_row = next(row for row in continuity["shots"] if row["shot_id"] == shot["id"])
    assert any(plate_id in href for href in shot_row["identity_hrefs"])

    audit = client.get("/api/audit", headers=auth, params={"episode_id": episode["id"]})
    actions = {row["action"] for row in audit.json()}
    assert "identity.approve" in actions
    assert "identity.link" in actions


def test_draft_plate_does_not_count_for_i2va_bind(client, auth):
    project, episode = create_episode(client, auth, "I2VA identity")
    pack = green_pack()
    pack["takes"][0]["hop1Mode"] = "i2va"
    pack["takes"][0]["hop1Plate"] = ""
    imported = client.post(
        f"/api/episodes/{episode['id']}/pack",
        headers=auth,
        files={"file": ("i2va.zip", pack_zip_bytes(pack), "application/zip")},
    )
    assert imported.status_code == 201, imported.text
    shots = client.get(f"/api/episodes/{episode['id']}/shots", headers=auth).json()
    shot = shots[0]
    plate = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "plate", "entity_label": "smith", "entity_type": "character"},
        files={
            "file": (
                "draft-plate.fixture.json",
                b'{"kind":"plate","claim":"fixture only"}',
                "application/json",
            )
        },
    )
    assert plate.status_code == 201
    client.post(
        f"/api/episodes/{episode['id']}/identity/{plate.json()['id']}/link",
        headers=auth,
        json={"shot_id": shot["id"]},
    )
    precheck = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "batch-precheck"},
    )
    # hop-1 enqueue uses plates_bound; draft must not satisfy I2VA
    from app.preview import plates_bound_for_shot
    from app.models import Episode, MediaAsset, Shot
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        ep = session.get(Episode, episode["id"])
        sh = session.get(Shot, shot["id"])
        media = session.query(MediaAsset).filter(MediaAsset.episode_id == episode["id"]).all()
        ok, detail = plates_bound_for_shot(sh, pack, media)
        assert ok is False
        assert "approved" in detail.lower()
    finally:
        session.close()

    client.post(
        f"/api/episodes/{episode['id']}/identity/{plate.json()['id']}/approve",
        headers=auth,
        json={},
    )
    session = SessionLocal()
    try:
        ep = session.get(Episode, episode["id"])
        sh = session.get(Shot, shot["id"])
        media = session.query(MediaAsset).filter(MediaAsset.episode_id == episode["id"]).all()
        ok, detail = plates_bound_for_shot(sh, pack, list(ep.media))
        assert ok is True
        assert "approved" in detail.lower()
    finally:
        session.close()
    assert precheck.status_code in {201, 200, 409}


def _upload_identity(client, auth, episode_id: str, kind: str, label: str, keywords: str = ""):
    uploaded = client.post(
        f"/api/episodes/{episode_id}/media",
        headers=auth,
        data={"kind": kind, "entity_label": label, "entity_type": "character"},
        files={
            "file": (
                f"{label}-{kind}.fixture.json",
                b'{"kind":"fixture","claim":"metadata only, no likeness"}',
                "application/json",
            )
        },
    )
    assert uploaded.status_code == 201, uploaded.text
    body = {"note": "lock keywords"}
    if keywords:
        body["lock_keywords"] = keywords
    approved = client.post(
        f"/api/episodes/{episode_id}/identity/{uploaded.json()['id']}/approve",
        headers=auth,
        json=body,
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


def test_approved_identity_lock_diff_blocks_generate_ok_and_hop1(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Identity lock")
    _upload_identity(client, auth, episode["id"], "sheet", "smith", "brown hair")
    _upload_identity(client, auth, episode["id"], "plate", "smith", "brunette hair")
    blocked = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": shots[0]["id"], "job_type": "clip-hop1"},
    )
    assert blocked.status_code == 409, blocked.text
    assert "identity_lock_diff" in blocked.text
    sign_off(client, auth, episode["id"])
    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    generate = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "identity still rotating"},
    )
    assert generate.status_code == 409, generate.text
    assert generate.json()["detail"]["code"] == "identity_lock_diff"


def test_draft_identity_keywords_do_not_block_generate_ok(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Draft identity")
    plate = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "plate", "entity_label": "smith", "entity_type": "character"},
        files={"file": ("draft.fixture.json", b'{"claim":"fixture only"}', "application/json")},
    )
    assert plate.status_code == 201, plate.text
    linked = client.post(
        f"/api/episodes/{episode['id']}/identity/{plate.json()['id']}/link",
        headers=auth,
        json={"shot_id": shots[0]["id"], "lock_keywords": "brunette hair"},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["approved"] is False
    sheet = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "sheet", "entity_label": "smith", "entity_type": "character"},
        files={"file": ("sheet.fixture.json", b'{"claim":"fixture only"}', "application/json")},
    )
    assert sheet.status_code == 201
    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    sign_off(client, auth, episode["id"])
    generate = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "drafts do not count"},
    )
    assert generate.status_code == 200, generate.text


def test_i2va_plate_match_is_exact_and_blocks_generate_ok(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Exact plate")
    session = SessionLocal()
    try:
        stored = (
            session.query(PackRevision)
            .filter(PackRevision.episode_id == episode["id"])
            .order_by(PackRevision.created_at.desc())
            .first()
        )
        assert stored is not None
        pack = dict(stored.pack_json)
        takes = [dict(row) for row in pack["takes"]]
        takes[0]["hop1Mode"] = "i2va"
        takes[0]["hop1Plate"] = ""
        pack["takes"] = takes
        stored.pack_json = pack
        stored.all_gates_green = True
        flag_modified(stored, "pack_json")
        session.commit()
        ep = session.get(Episode, episode["id"])
        from app.preview import plates_bound_for_shot

        loose = _upload_identity(client, auth, episode["id"], "plate", "blacksmith")
        assert loose["approved"] is True
        session.expire_all()
        ep = session.get(Episode, episode["id"])
        shot = next(row for row in ep.shots if row.id == shots[0]["id"])
        ok, detail = plates_bound_for_shot(shot, pack, list(ep.media))
        assert ok is False, detail
        assert "approved" in detail.lower()
    finally:
        session.close()

    generate = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok"},
    )
    assert generate.status_code == 409
    assert generate.json()["detail"]["code"] == "plates_unbound"

    exact = _upload_identity(client, auth, episode["id"], "plate", "smith")
    assert exact["entity_label"] == "smith"
    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    sign_off(client, auth, episode["id"])
    allowed = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "exact smith plate"},
    )
    assert allowed.status_code == 200, allowed.text


def test_unapprove_and_keyword_edit_drop_out_of_generate_ok(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "Unapprove")
    sheet = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "sheet", "entity_label": "smith", "entity_type": "character"},
        files={"file": ("sheet.fixture.json", b'{"claim":"fixture only"}', "application/json")},
    )
    assert sheet.status_code == 201, sheet.text
    asset_id = sheet.json()["id"]
    approved = client.post(
        f"/api/episodes/{episode['id']}/identity/{asset_id}/approve",
        headers=auth,
        json={"lock_keywords": "brown hair"},
    )
    assert approved.status_code == 200
    plate = client.post(
        f"/api/episodes/{episode['id']}/media",
        headers=auth,
        data={"kind": "plate", "entity_label": "smith", "entity_type": "character"},
        files={"file": ("plate.fixture.json", b'{"claim":"fixture only"}', "application/json")},
    )
    plate_id = plate.json()["id"]
    client.post(
        f"/api/episodes/{episode['id']}/identity/{plate_id}/link",
        headers=auth,
        json={"shot_id": shots[0]["id"]},
    )
    client.post(
        f"/api/episodes/{episode['id']}/identity/{plate_id}/approve",
        headers=auth,
        json={"lock_keywords": "brunette hair"},
    )
    blocked = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "identity_lock_diff"

    edited = client.post(
        f"/api/episodes/{episode['id']}/identity/{asset_id}/keywords",
        headers=auth,
        json={"lock_keywords": "auburn hair", "note": "edit before re-approve"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["approved"] is False
    assert edited.json()["lock_keywords"] == "auburn hair"

    still_blocked = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok"},
    )
    assert still_blocked.status_code == 409

    dropped = client.post(
        f"/api/episodes/{episode['id']}/identity/{plate_id}/unapprove",
        headers=auth,
        json={"note": "plate no longer locked"},
    )
    assert dropped.status_code == 200, dropped.text
    assert dropped.json()["approved"] is False
    again = client.post(
        f"/api/episodes/{episode['id']}/identity/{plate_id}/unapprove",
        headers=auth,
        json={"note": "twice"},
    )
    assert again.status_code == 409

    attach_watched_receipt(client, auth, episode["id"], shots[0]["id"])
    sign_off(client, auth, episode["id"])
    cleared = client.put(
        f"/api/episodes/{episode['id']}/review",
        headers=auth,
        json={"state": "generate-ok", "note": "drafts do not count"},
    )
    assert cleared.status_code == 200, cleared.text

    reapproved = client.post(
        f"/api/episodes/{episode['id']}/identity/{asset_id}/approve",
        headers=auth,
        json={"lock_keywords": "brown hair", "note": "re-approve"},
    )
    assert reapproved.status_code == 200
    assert reapproved.json()["approved"] is True
    audit = client.get(
        "/api/audit",
        headers=auth,
        params={"episode_id": episode["id"]},
    )
    actions = [row["action"] for row in audit.json()]
    assert "identity.unapprove" in actions
    assert "identity.keywords" in actions
    assert "identity.approve" in actions
