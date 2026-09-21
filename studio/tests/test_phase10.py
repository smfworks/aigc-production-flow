"""Phase 10: create a pack in Studio, draft a brain dump, export an agent brief."""

import io
import json
import zipfile

import httpx

from app.braindump import draft_from_dump
from app.config import Settings
from tests.helpers import add_member, as_org, as_user


def _jobs(client, auth, episode_id: str) -> list[dict]:
    response = client.get(f"/api/episodes/{episode_id}/export/agent", headers=auth)
    assert response.status_code == 200, response.text
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert {"README.md", "agent-brief.json", "gate-snapshot.json", "pack.json", "pack.zip"} <= names
    brief = json.loads(archive.read("agent-brief.json"))
    assert brief["honesty"]["called_comfy"] is False
    assert brief["honesty"]["generate_ready"] is False
    assert brief["window"]["window_s"] == 10.125
    assert brief["window"]["frames"] == 243
    kinds = [row["kind"] for row in brief["jobs"]]
    assert any(kind.startswith("still") for kind in kinds)
    assert any(kind == "clip-hop1" for kind in kinds)
    last_still = max(index for index, kind in enumerate(kinds) if kind.startswith("still"))
    first_clip = min(index for index, kind in enumerate(kinds) if kind.startswith("clip"))
    assert last_still < first_clip
    pack = json.loads(archive.read("pack.json"))["pack"]
    assert pack["look"]["styleLine"] == "" or brief["honesty"]["all_gates_green"] is False
    return brief["jobs"]


def test_start_blank_project_without_zip(client, auth):
    created = client.post(
        "/api/studio/start",
        headers=auth,
        json={"name": "Hallway", "mode": "blank"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["gates_green"] is False
    assert body["generate_ready"] is False
    assert body["model_ran"] is False
    assert body["source"] == "blank"

    episode = client.get(f"/api/episodes/{body['episode_id']}", headers=auth)
    assert episode.status_code == 200
    revision = episode.json()["latest_revision"]
    assert revision["all_gates_green"] is False

    full = client.get(
        f"/api/episodes/{body['episode_id']}/revisions/{body['revision_id']}",
        headers=auth,
    )
    pack = full.json()["pack"]
    assert pack["look"]["styleLine"] == ""
    assert pack["studioMeta"]["generate_ready"] is False
    assert pack["studioMeta"]["model_ran"] is False

    meta = client.get("/api/meta")
    assert meta.json()["phase"] == 10
    assert meta.json()["llm_configured"] is False
    assert meta.json()["primary_create"] == "studio"
    assert "No model configured" in meta.json()["llm_note"]

    _jobs(client, auth, body["episode_id"])


def test_template_and_brain_dump_stay_drafts(client, auth):
    templated = client.post(
        "/api/studio/start",
        headers=auth,
        json={"name": "Lesson", "mode": "template", "template_id": "education-lesson"},
    )
    assert templated.status_code == 201, templated.text
    assert templated.json()["gates_green"] is False
    assert templated.json()["model_ran"] is False

    dumped = client.post(
        "/api/studio/start",
        headers=auth,
        json={
            "name": "Turn",
            "mode": "brain",
            "brain_dump": "Mara waits in the hall.\nShe turns.\nCharacter: Mara\nProp: token",
        },
    )
    assert dumped.status_code == 201, dumped.text
    body = dumped.json()
    assert body["model_ran"] is False
    assert body["gates_green"] is False
    assert "No model configured" in body["model_note"]
    full = client.get(
        f"/api/episodes/{body['episode_id']}/revisions/{body['revision_id']}",
        headers=auth,
    ).json()
    pack = full["pack"]
    assert pack["look"]["styleLine"] == ""
    assert "Mara" in pack["logLine"] or pack["characters"][0]["name"] == "Mara"
    assert pack["characters"][0]["lockParagraph"] == ""
    assert pack["studioMeta"]["generate_ready"] is False
    assert full["all_gates_green"] is False


def test_episode_blank_save_and_reset(client, auth):
    project = client.post("/api/projects", headers=auth, json={"name": "Existing"}).json()
    episode = client.post(
        f"/api/projects/{project['id']}/episodes",
        headers=auth,
        json={"title": "Ep blank", "pack": "blank"},
    )
    assert episode.status_code == 201, episode.text
    episode_id = episode.json()["id"]
    assert episode.json()["latest_revision"]["all_gates_green"] is False

    refused = client.post(
        f"/api/episodes/{episode_id}/pack/blank",
        headers=auth,
        json={},
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "confirm_reset"

    reset = client.post(
        f"/api/episodes/{episode_id}/pack/blank",
        headers=auth,
        json={"confirm": "reset"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["generate_ready"] is False

    saved = client.post(
        f"/api/episodes/{episode_id}/pack/json",
        headers=auth,
        json={
            "pack": {
                "title": "Ep blank",
                "logLine": "A draft line.",
                "look": {"styleLine": "", "paletteGrade": "", "era": "", "lensGrain": "", "extrasForbidden": ""},
                "map": [],
                "takes": [],
                "editList": [],
                "characters": [],
                "props": [],
            }
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["gates_green"] is False
    assert saved.json()["generate_ready"] is False
    revisions = client.get(f"/api/episodes/{episode_id}/revisions", headers=auth).json()
    assert len(revisions) >= 3


def test_other_org_cannot_export_agent(client, auth):
    created = client.post(
        "/api/studio/start",
        headers=auth,
        json={"name": "Private", "mode": "blank"},
    ).json()
    other = client.post("/api/orgs", headers=auth, json={"name": "Other lot"}).json()
    denied = client.get(
        f"/api/episodes/{created['episode_id']}/export/agent",
        headers=as_org(auth, other["id"]),
    )
    assert denied.status_code == 404


def test_viewer_cannot_start_writer_can_blank_episode(client, auth):
    add_member(client, auth, "viewer-10", "viewer")
    add_member(client, auth, "writer-10", "writer")
    denied = client.post(
        "/api/studio/start",
        headers=as_user(auth, "viewer-10"),
        json={"name": "Nope", "mode": "blank"},
    )
    assert denied.status_code == 403

    project = client.post("/api/projects", headers=auth, json={"name": "Writer show"}).json()
    made = client.post(
        f"/api/projects/{project['id']}/episodes",
        headers=as_user(auth, "writer-10"),
        json={"title": "Writer ep", "pack": "blank"},
    )
    assert made.status_code == 201, made.text
    assert made.json()["latest_revision"]["all_gates_green"] is False


def test_llm_success_and_failure_stay_honest(monkeypatch):
    class OkClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            class Response:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "title": "From model",
                                            "logLine": "A model draft.",
                                            "beats": ["verse", "turn"],
                                            "characters": ["Ada"],
                                            "props": ["key"],
                                            "durationTarget": "2 min",
                                        }
                                    )
                                }
                            }
                        ]
                    }

            return Response()

    monkeypatch.setattr(httpx, "Client", OkClient)
    settings = Settings(llm_base_url="http://llm.test/v1", llm_model="unit-model", llm_api_key="")
    pack, honesty = draft_from_dump("ignored", settings=settings)
    assert honesty["model_ran"] is True
    assert honesty["model"] == "unit-model"
    assert honesty["generate_ready"] is False
    assert pack["look"]["styleLine"] == ""
    assert pack["characters"][0]["name"] == "Ada"
    assert pack["characters"][0]["lockParagraph"] == ""
    assert pack["audioPath"] == ""
    assert honesty["all_gates_green"] is False

    class DownClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "Client", DownClient)
    pack, honesty = draft_from_dump("First sentence.\nSecond beat.", settings=settings)
    assert honesty["model_ran"] is False
    assert "Deterministic" in honesty["note"] or "failed" in honesty["note"].lower()
    assert pack["look"]["styleLine"] == ""
    assert pack["logLine"].startswith("First sentence")
