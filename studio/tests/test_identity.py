from tests.fixtures import pack_zip_bytes, green_pack
from tests.helpers import create_episode, import_green


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
