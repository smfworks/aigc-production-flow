from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import MediaAsset
from tests.helpers import green_ready_episode


def test_retention_dry_run_and_apply_keeps_pack_revision(client, auth):
    _, episode, _ = green_ready_episode(client, auth, "Retention")
    episode_id = episode["id"]
    job = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode_id, "job_type": "still-sheet"},
    )
    assert job.status_code == 201
    media_id = job.json()["media_id"]
    assert media_id

    preview = client.get("/api/retention", headers=auth, params={"episode_id": episode_id})
    assert preview.status_code == 200
    body = preview.json()
    assert body["dry_run"] is True
    assert body["keep_pack_revisions"] is True
    assert body["revision_count_kept"] >= 1
    # Fresh stub output is newer than the default 30-day window.
    assert body["candidates"] == []

    db = SessionLocal()
    try:
        asset = db.get(MediaAsset, media_id)
        assert asset is not None
        asset.created_at = datetime.now(timezone.utc) - timedelta(days=40)
        db.commit()
    finally:
        db.close()

    aged = client.get("/api/retention/dry-run", headers=auth, params={"episode_id": episode_id})
    assert aged.status_code == 200
    ids = {row["id"] for row in aged.json()["candidates"]}
    assert media_id in ids

    refused = client.post(
        "/api/retention",
        headers=auth,
        json={"episode_id": episode_id, "dry_run": False, "confirm": "nope"},
    )
    assert refused.status_code == 400

    applied = client.post(
        "/api/retention",
        headers=auth,
        json={"episode_id": episode_id, "dry_run": False, "confirm": "expire"},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["applied"] is True
    assert media_id in applied.json()["deleted_ids"]

    missing = client.get(f"/api/media/{media_id}", headers=auth)
    assert missing.status_code == 404

    pack = client.get(f"/api/episodes/{episode_id}/pack", headers=auth)
    assert pack.status_code == 200
    assert pack.headers.get("content-type", "").startswith("application/zip") or pack.content
