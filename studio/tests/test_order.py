import io
import json
import zipfile

from tests.helpers import add_member, as_user, create_episode


def test_reorder_episodes_and_backup_keeps_order(client, auth):
    project, first = create_episode(client, auth, "Season order")
    second = client.post(
        f"/api/projects/{project['id']}/episodes",
        headers=auth,
        json={"title": "Middle", "synopsis": "beat two"},
    )
    assert second.status_code == 201, second.text
    third = client.post(
        f"/api/projects/{project['id']}/episodes",
        headers=auth,
        json={"title": "Finale", "log_line": "Last beat."},
    )
    assert third.status_code == 201, third.text
    assert [first["sequence"], second.json()["sequence"], third.json()["sequence"]] == [1, 2, 3]

    add_member(client, auth, "wren", "writer")
    add_member(client, auth, "ada", "art")
    writer = as_user(auth, "wren")
    art = as_user(auth, "ada")

    refused = client.post(
        f"/api/projects/{project['id']}/episodes/reorder",
        headers=art,
        json={
            "items": [
                {"id": third.json()["id"], "season": 1, "sequence": 1},
                {"id": first["id"], "season": 1, "sequence": 2},
                {"id": second.json()["id"], "season": 2, "sequence": 1},
            ]
        },
    )
    assert refused.status_code == 403

    ordered = client.post(
        f"/api/projects/{project['id']}/episodes/reorder",
        headers=writer,
        json={
            "items": [
                {"id": third.json()["id"], "season": 1, "sequence": 1},
                {"id": first["id"], "season": 1, "sequence": 2},
                {"id": second.json()["id"], "season": 2, "sequence": 1},
            ]
        },
    )
    assert ordered.status_code == 200, ordered.text
    titles = [row["title"] for row in ordered.json()]
    assert titles == ["Finale", "Ep 1", "Middle"]
    assert ordered.json()[2]["season"] == 2
    assert ordered.json()[0]["chapter"] == 1

    partial = client.post(
        f"/api/projects/{project['id']}/episodes/reorder",
        headers=writer,
        json={"items": [{"id": first["id"], "season": 1, "sequence": 1}]},
    )
    assert partial.status_code == 400

    exported = client.get("/api/backup", headers=auth)
    assert exported.status_code == 200
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
    rows = {row["title"]: row for row in manifest["episodes"] if row["project_id"] == project["id"]}
    assert rows["Finale"]["season"] == 1
    assert rows["Finale"]["sequence"] == 1
    assert rows["Middle"]["season"] == 2
    assert rows["Middle"]["sequence"] == 1
    assert "order is metadata" in manifest["keep_note"] or "season/sequence" in manifest["keep_note"]

    retention = client.post(
        "/api/retention",
        headers=auth,
        json={"dry_run": True, "project_id": project["id"]},
    )
    assert retention.status_code == 200
    assert "sequence" in retention.json()["keep_note"]

    audit = client.get("/api/audit", headers=auth, params={"action": "episode.reorder"})
    assert audit.status_code == 200
    assert audit.json()
