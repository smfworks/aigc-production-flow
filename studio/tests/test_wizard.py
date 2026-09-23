"""Phase 12: Create wizard, Hermes drop, agent-run status, stitch plan."""

import json

from app.config import get_settings
from tests.helpers import add_member, as_org, as_user


def _answers(client, auth, wizard_id: str, step: str, **answers):
    response = client.patch(
        f"/api/create/wizard/{wizard_id}",
        headers=auth,
        json={"step": step, "answers": answers},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _finish_hallway(client, auth) -> dict:
    started = client.post(
        "/api/create/wizard",
        headers=auth,
        json={"prompt": "Mara waits in the hall. She turns."},
    )
    assert started.status_code == 201, started.text
    wizard_id = started.json()["id"]
    _answers(client, auth, wizard_id, "format", format="short-drama")
    _answers(client, auth, wizard_id, "length", shot_count=2, target_length_s=20)
    _answers(client, auth, wizard_id, "tone", tone="quiet dusk", look="sodium practicals, no neon")
    _answers(
        client,
        auth,
        wizard_id,
        "scope",
        audience="late-night short drama",
        deliverables="one 20s pilot, two hop-1 windows",
        negative_constraints="none",
    )
    _answers(client, auth, wizard_id, "cast", cast_notes="Mara — lead, tired eyes")
    _answers(client, auth, wizard_id, "audio", audio_notes="room tone, no score")
    saved = client.get(f"/api/create/wizard/{wizard_id}", headers=auth)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["answers"]["format"] == "short-drama"
    assert body["answers"]["cast_notes"].startswith("Mara")
    assert body["answers"]["shot_count"] == 2
    assert body["engines"]["called_comfy"] is False
    assert body["engines"]["still_live"] is False
    finished = client.post(f"/api/create/wizard/{wizard_id}/finish", headers=auth)
    assert finished.status_code == 200, finished.text
    done = finished.json()
    assert done["status"] == "ready"
    assert done["gates_green"] is False
    assert done["generate_ready"] is False
    assert done["episode_id"]
    return done


def test_wizard_creates_draft_pack_and_keeps_answers(client, auth):
    done = _finish_hallway(client, auth)
    episode_id = done["episode_id"]
    episode = client.get(f"/api/episodes/{episode_id}", headers=auth)
    assert episode.status_code == 200, episode.text
    assert episode.json()["review_state"] == "draft"
    full = client.get(
        f"/api/episodes/{episode_id}/revisions/{done['revision_id']}",
        headers=auth,
    )
    assert full.status_code == 200, full.text
    pack = full.json()["pack"]
    names = [row["name"] for row in pack["characters"]]
    assert names == ["Mara"]
    assert all(not row.get("lockParagraph") for row in pack["characters"])
    assert len(pack["editList"]) == 2
    assert pack["studioMeta"]["source"] == "wizard"
    assert pack["studioMeta"]["model_ran"] is False
    assert pack["look"]["styleLine"] == "sodium practicals, no neon"
    identity = client.get(f"/api/episodes/{episode_id}/identity", headers=auth)
    assert identity.status_code == 200, identity.text
    sheets = identity.json()["sheets"]
    mara = next(row for row in sheets if row["entity_label"] == "Mara")
    assert mara["approval_status"] == "draft"
    assert "Not approved" in mara["notes"]
    assert identity.json()["approved_sheet_count"] == 0


def test_handoff_writes_stitch_brief_and_status_is_honest(client, auth):
    done = _finish_hallway(client, auth)
    sent = client.post(
        f"/api/create/wizard/{done['id']}/handoff/hermes",
        headers=auth,
    )
    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert body["deep_link"].startswith("hermes://aigc/brief?run=")
    assert body["run"]["called_comfy"] is False
    assert body["run"]["hermes_ran"] is False
    assert body["payload"]["honesty"]["called_comfy"] is False
    assert body["payload"]["honesty"]["hermes_ran"] is False
    assert body["payload"]["honesty"]["produced_mp4"] is False
    kinds = [step["kind"] for step in body["run"]["steps"]]
    assert kinds[-1] == "stitch"
    assert "still-sheet" in kinds
    assert "still-plate" in kinds
    assert "clip-hop1" in kinds
    last_still = max(index for index, kind in enumerate(kinds) if kind.startswith("still"))
    first_clip = kinds.index("clip-hop1")
    assert last_still < first_clip < kinds.index("stitch")
    stitch = body["run"]["steps"][-1]
    assert stitch["status"] == "awaiting_stitch"
    assert stitch["produced_mp4"] is False
    assert body["run"]["stitch_state"] == "awaiting_stitch"
    assert body["run"]["status"] == "awaiting_stitch"
    stills = [step for step in body["run"]["steps"] if step["kind"] == "still-sheet"]
    assert stills
    assert all(step["status"] == "succeeded" for step in stills)
    assert all(step["called_comfy"] is False for step in body["run"]["steps"])
    assert any("Stub" in step["claim"] or "fixture" in step["claim"].lower() for step in stills)

    drop = get_settings().media_path.parent / "handoff" / body["run"]["id"]
    brief = json.loads((drop / "agent-brief.json").read_text(encoding="utf-8"))
    brief_kinds = [row["kind"] for row in brief["jobs"]]
    assert brief_kinds[-1] == "stitch"
    assert brief["honesty"]["called_comfy"] is False
    assert (drop / "pack.json").is_file()
    assert (drop / "gate-snapshot.json").is_file()
    handoff = json.loads((drop / "hermes-handoff.json").read_text(encoding="utf-8"))
    assert handoff["deep_link"] == body["deep_link"]
    latest = json.loads((drop.parent / "latest.json").read_text(encoding="utf-8"))
    assert latest["agent_run_id"] == body["run"]["id"]
    assert latest["hermes_ran"] is False
    assert latest["called_comfy"] is False
    stitch_file = json.loads((drop / "agent-brief.json").read_text(encoding="utf-8"))
    assert stitch_file["jobs"][-1]["produced_mp4"] is False

    status = client.get(f"/api/agent-runs/{body['run']['id']}", headers=auth)
    assert status.status_code == 200, status.text
    again = status.json()
    assert again["status"] == "awaiting_stitch"
    assert again["hermes_ran"] is False
    assert again["called_comfy"] is False
    assert again["steps"][-1]["kind"] == "stitch"
    assert again["steps"][-1]["produced_mp4"] is False
    assert "No MP4" in again["honesty_note"] or "awaiting" in again["honesty_note"].lower()

    episode = client.get(f"/api/episodes/{done['episode_id']}", headers=auth).json()
    assert episode["review_state"] != "generate-ok"


def test_other_org_cannot_read_wizard_or_run(client, auth):
    done = _finish_hallway(client, auth)
    sent = client.post(f"/api/create/wizard/{done['id']}/handoff/hermes", headers=auth)
    assert sent.status_code == 201, sent.text
    other = client.post("/api/orgs", headers=auth, json={"name": "Other lot"}).json()
    headers = as_org(auth, other["id"])
    hidden = client.get(f"/api/create/wizard/{done['id']}", headers=headers)
    assert hidden.status_code == 404
    hidden_run = client.get(f"/api/agent-runs/{sent.json()['run']['id']}", headers=headers)
    assert hidden_run.status_code == 404


def test_viewer_cannot_start_wizard(client, auth):
    add_member(client, auth, "viewer-12", "viewer")
    denied = client.post(
        "/api/create/wizard",
        headers=as_user(auth, "viewer-12"),
        json={"prompt": "A door."},
    )
    assert denied.status_code == 403


def test_stitch_job_stub_path_does_not_invent_mp4(client, auth):
    done = _finish_hallway(client, auth)
    job = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": done["episode_id"], "job_type": "stitch"},
    )
    assert job.status_code == 201, job.text
    body = job.json()
    assert body["status"] == "succeeded"
    assert body["result"]["produced_mp4"] is False
    assert body["result"]["state"] == "awaiting_stitch"
    assert body["result"]["called_comfy"] is False
    assert "No MP4" in body["result"]["claim"]
    assert body["result"]["hermes_skill"]["name"] == "stitch"
    assert isinstance(body["result"]["concat_plan"], list)
    assert body["result"]["concat_plan"]


def test_director_scope_lanes_checkpoints_and_tree_persist(client, auth):
    started = client.post(
        "/api/create/wizard",
        headers=auth,
        json={"prompt": "Mara waits in the hall. She turns."},
    )
    assert started.status_code == 201, started.text
    wizard_id = started.json()["id"]
    assert "scope" in started.json()["steps"]
    assert "tree" in started.json()["steps"]
    assert "checkpoints" in started.json()["steps"]
    _answers(client, auth, wizard_id, "format", format="short-drama")
    _answers(client, auth, wizard_id, "length", shot_count=2, target_length_s=20)
    _answers(client, auth, wizard_id, "tone", tone="quiet dusk", look="sodium practicals, no neon")
    scoped = _answers(
        client,
        auth,
        wizard_id,
        "scope",
        must_nots="no logos",
        platform_formats="9:16 only",
        claim_bans="no medical claims",
        audience="vertical viewers",
        deliverables="one 9:16 cut",
        negative_constraints="no neon",
    )
    assert scoped["answers"]["platform_formats"] == ["9:16"]
    assert scoped["answers"]["must_nots"] == "no logos"
    assert scoped["director"]["agents_ran"] is False
    assert scoped["director"]["called_comfy"] is False
    assert scoped["director"]["executes"] is False
    _answers(client, auth, wizard_id, "cast", cast_notes="Mara — lead, tired eyes")
    _answers(client, auth, wizard_id, "audio", audio_notes="room tone, no score")
    _answers(client, auth, wizard_id, "engines", still_pref="comfy-qwen", clip_pref="comfy-h3")
    finished = client.post(f"/api/create/wizard/{wizard_id}/finish", headers=auth)
    assert finished.status_code == 200, finished.text
    done = finished.json()
    assert done["gates_green"] is False
    assert done["generate_ready"] is False
    lanes = [row["id"] for row in done["director"]["craft_lanes"]]
    assert lanes == ["writer", "art", "picture", "sound"]
    assert all(row["ran"] is False for row in done["director"]["craft_lanes"])
    items = {row["id"]: row for row in done["director"]["checkpoints"]["items"]}
    assert items["identities-draft"]["cleared"] is False
    assert items["plates-missing"]["cleared"] is False
    assert items["gates-red"]["cleared"] is False
    assert items["hop1-unwatched"]["cleared"] is False
    assert items["no-signoff"]["cleared"] is False
    gate_ids = {row["id"] for row in done["director"]["checkpoints"]["gates"]}
    assert {
        "log-line",
        "map",
        "edit-list",
        "takes",
        "characters",
        "props",
        "look",
        "audio",
        "smoke",
        "entity-schedule",
        "lock-diff",
    } <= gate_ids
    assert done["director"]["checkpoints"]["generate_ready"] is False
    tree = done["director"]["task_tree"]
    assert [row["kind"] for row in tree if row["kind"] != "hop-1"] == [
        "script-beats",
        "audio-notes",
        "identity-sheets",
        "plates",
        "stitch",
        "review-gates",
    ]
    assert [row["take"] for row in tree if row["kind"] == "hop-1"] == ["A", "B"]
    assert all(row["executes"] is False for row in tree)
    review = next(row for row in tree if row["kind"] == "review-gates")
    assert review["prunable"] is False

    full = client.get(
        f"/api/episodes/{done['episode_id']}/revisions/{done['revision_id']}",
        headers=auth,
    )
    pack = full.json()["pack"]
    assert "Must not: no logos" in pack["studioMeta"]["notes"]
    assert "9:16" in pack["studioMeta"]["notes"]
    assert "Claim bans: no medical claims" in pack["studioMeta"]["notes"]
    assert pack["studioMeta"]["model_ran"] is False
    project = client.get(f"/api/projects/{done['project_id']}", headers=auth)
    assert project.status_code == 200, project.text
    state = project.json()["director_state"]
    assert state["agents_ran"] is False
    assert state["scope"]["claim_bans"] == "no medical claims"
    assert any(row["kind"] == "stitch" and row["enabled"] for row in state["task_tree"])

    for row in tree:
        if row["kind"] == "plates":
            row["enabled"] = False
        if row["kind"] == "review-gates":
            row["enabled"] = False
            row["deleted"] = True
    pruned = client.patch(
        f"/api/create/wizard/{wizard_id}",
        headers=auth,
        json={"answers": {"task_tree": tree}},
    )
    assert pruned.status_code == 200, pruned.text
    pruned_tree = pruned.json()["director"]["task_tree"]
    assert all(not row["enabled"] for row in pruned_tree if row["kind"] in {"plates", "hop-1"})
    assert all(row["enabled"] and not row["deleted"] for row in pruned_tree if row["kind"] == "review-gates")
    assert any(row["kind"] == "stitch" and row["enabled"] for row in pruned_tree)

    sent = client.post(f"/api/create/wizard/{wizard_id}/handoff/hermes", headers=auth)
    assert sent.status_code == 201, sent.text
    body = sent.json()
    assert body["run"]["called_comfy"] is False
    assert body["run"]["hermes_ran"] is False
    assert body["payload"]["honesty"]["produced_mp4"] is False
    assert body["payload"]["director"]["agents_ran"] is False
    assert body["payload"]["director"]["scope"]["must_nots"] == "no logos"
    kinds = [step["kind"] for step in body["run"]["steps"]]
    assert kinds[-1] == "stitch"
    plates = [step for step in body["run"]["steps"] if step["kind"] == "still-plate"]
    clips = [step for step in body["run"]["steps"] if step["kind"] == "clip-hop1"]
    assert plates and all(step["status"] == "skipped" for step in plates)
    assert clips and all(step["status"] == "skipped" for step in clips)
    assert all(step["called_comfy"] is False for step in body["run"]["steps"])
    assert body["run"]["steps"][-1]["produced_mp4"] is False
    brief = json.loads(
        (get_settings().media_path.parent / "handoff" / body["run"]["id"] / "agent-brief.json").read_text(
            encoding="utf-8"
        )
    )
    assert brief["honesty"]["called_comfy"] is False
    assert brief["director"]["agents_ran"] is False
    assert [row["id"] for row in brief["director"]["craft_lanes"]] == ["writer", "art", "picture", "sound"]
    assert all(row["ran"] is False for row in brief["director"]["craft_lanes"])
    assert brief["director"]["scope"]["platform_formats"] == ["9:16"]
    assert brief["jobs"][-1]["kind"] == "stitch"
    assert brief["jobs"][-1]["produced_mp4"] is False
    assert all(row["enabled"] is False for row in brief["jobs"] if row["kind"] == "still-plate")
    assert all(row["enabled"] is True for row in brief["jobs"] if row["kind"] == "still-sheet")
    locked = client.patch(
        f"/api/create/wizard/{wizard_id}",
        headers=auth,
        json={"answers": {"must_nots": "too late"}},
    )
    assert locked.status_code == 409


def test_saved_create_recipe_prefills_and_stays_local(client, auth):
    done = _finish_hallway(client, auth)
    _answers(
        client,
        auth,
        done["id"],
        "checkpoints",
        must_nots="no logos",
        platform_formats=["9:16"],
        claim_bans="no cure claims",
    )
    saved = client.post(
        "/api/create/recipes",
        headers=auth,
        json={"name": "Short drama", "wizard_id": done["id"]},
    )
    assert saved.status_code == 201, saved.text
    recipe = saved.json()
    assert recipe["filename"] == "skill_short_drama_v0.1.json"
    assert recipe["version"] == "0.1"
    assert recipe["kind"] == "aigc-create-recipe"
    assert recipe["honesty"]["called_comfy"] is False
    assert recipe["honesty"]["agents_ran"] is False
    assert recipe["honesty"]["hermes_ran"] is False
    assert recipe["task_tree"]
    assert all(row["executes"] is False for row in recipe["task_tree"])
    again = client.post(
        "/api/create/recipes",
        headers=auth,
        json={"name": "Short drama", "wizard_id": done["id"]},
    )
    assert again.status_code == 201, again.text
    assert again.json()["filename"] == "skill_short_drama_v0.2.json"
    listed = client.get("/api/create/recipes", headers=auth)
    assert listed.status_code == 200, listed.text
    assert {row["filename"] for row in listed.json()} >= {
        "skill_short_drama_v0.1.json",
        "skill_short_drama_v0.2.json",
    }
    other = client.post("/api/orgs", headers=auth, json={"name": "Other lot"}).json()
    hidden = client.get(f"/api/create/recipes/{recipe['id']}", headers=as_org(auth, other["id"]))
    assert hidden.status_code == 404

    loaded = client.post(
        "/api/create/wizard",
        headers=auth,
        json={"recipe_id": recipe["id"], "prompt": ""},
    )
    assert loaded.status_code == 201, loaded.text
    body = loaded.json()
    assert body["status"] == "draft"
    assert body["episode_id"] is None
    assert body["answers"]["format"] == "short-drama"
    assert body["answers"]["must_nots"] == "no logos"
    assert body["answers"]["platform_formats"] == ["9:16"]
    assert body["answers"]["cast_notes"].startswith("Mara")
    assert body["director"]["called_comfy"] is False
    assert body["director"]["agents_ran"] is False
    assert body["generate_ready"] is False
    assert body["gates_green"] is False
