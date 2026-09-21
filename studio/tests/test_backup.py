import io
import json
import zipfile

from tests.fixtures import green_pack, pack_zip_bytes
from tests.helpers import as_org, create_episode


def test_backup_zip_and_restore_dry_run(client, auth):
    create_episode(client, auth, "Backup title")
    exported = client.get("/api/backup", headers=auth)
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("application/zip")
    data = exported.content
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        manifest = archive.read("manifest.json").decode("utf-8")
        assert "keep_pack_revisions" in manifest
        assert "media_manifest" in manifest

    dry = client.post(
        "/api/backup/restore",
        headers=auth,
        files={"file": ("backup.zip", data, "application/zip")},
        data={"dry_run": "true", "confirm": ""},
    )
    assert dry.status_code == 200, dry.text
    body = dry.json()
    assert body["dry_run"] is True
    assert body["applied"] is False
    assert body["keep_pack_revisions"] is True
    assert "would_skip_projects" in body or "would_create_projects" in body

    applied = client.post(
        "/api/backup/restore",
        headers=auth,
        files={"file": ("backup.zip", data, "application/zip")},
        data={"dry_run": "false", "confirm": "restore"},
    )
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert result["applied"] is True
    assert result["dry_run"] is False
    assert result["keep_pack_revisions"] is True
    assert result.get("added_revisions", 0) >= 0


def test_restore_refuses_foreign_episode_id(client, auth):
    other = client.post("/api/orgs", headers=auth, json={"name": "Restore lot"}).json()
    switched = as_org(auth, other["id"])
    _, foreign = create_episode(client, switched, "Foreign show")
    before = client.get(f"/api/episodes/{foreign['id']}/revisions", headers=switched)
    assert before.status_code == 200
    assert before.json() == []
    manifest = {
        "v": 1,
        "projects": [{"id": "proj-new", "name": "Planted", "slug": "planted-foreign-probe"}],
        "episodes": [
            {
                "id": foreign["id"],
                "project_id": "proj-new",
                "title": "Should not attach",
            }
        ],
        "pack_revisions": [
            {
                "id": "rev-planted",
                "episode_id": foreign["id"],
                "filename": "planted.zip",
                "pack_json": green_pack(),
                "gate_snapshot": {"all_green": False, "gates": []},
                "all_gates_green": False,
            }
        ],
        "media_manifest": [
            {
                "id": "media-planted",
                "episode_id": foreign["id"],
                "kind": "other",
                "original_name": "note.txt",
                "path": f"{foreign['id']}/assets/secret.txt",
            }
        ],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("revisions/rev-planted.zip", pack_zip_bytes(green_pack()))
    payload = buf.getvalue()
    dry = client.post(
        "/api/backup/restore",
        headers=auth,
        files={"file": ("backup.zip", payload, "application/zip")},
        data={"dry_run": "true"},
    )
    assert dry.status_code == 200, dry.text
    assert dry.json()["cross_org_conflicts"]
    applied = client.post(
        "/api/backup/restore",
        headers=auth,
        files={"file": ("backup.zip", payload, "application/zip")},
        data={"dry_run": "false", "confirm": "restore"},
    )
    assert applied.status_code == 409, applied.text
    after = client.get(f"/api/episodes/{foreign['id']}/revisions", headers=switched)
    assert after.json() == []
    media = client.get(f"/api/episodes/{foreign['id']}/media", headers=switched)
    assert media.json() == []
