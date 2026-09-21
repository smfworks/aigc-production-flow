import io
import zipfile

from tests.helpers import create_episode


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
