"""Phase 14: role tags, prompt preview, shot coverage, continue-from-previous."""

import copy
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from app.adapters.role_workflow import fill_workflow, h3_profile_text, h3_sections, parse_workflow
from app.config import get_settings
from app.coverage import plan_clips
from app.workflows import get_workflow


def test_role_tags_follow_titles_not_node_ids():
    loaded = get_workflow("character-sheet")
    graph = loaded["graph"]
    assert "1" not in graph
    assert "3" not in graph
    contract = parse_workflow(graph)
    by_role = {slot["canonical"]: slot["node_id"] for slot in contract["slots"] if slot["direction"] == "input"}
    assert by_role["prompt"] == "c7"
    assert by_role["character"] == "id9"
    assert contract["asks_h3"] is True
    assert contract["has_video_input"] is False
    unknown = {
        "zz": {
            "class_type": "Note",
            "inputs": {"text": ""},
            "_meta": {"title": "Extra (Input:foo)"},
        },
        "aa": {
            "class_type": "LoadImage",
            "inputs": {"image": ""},
            "_meta": {"title": "Lock (Input:identity)"},
        },
    }
    parsed = parse_workflow(unknown)
    roles = {(slot["role"], slot["canonical"], slot["node_id"]) for slot in parsed["slots"]}
    assert ("foo", None, "zz") in roles
    assert ("identity", "character", "aa") in roles
    filled = fill_workflow(
        graph,
        {"prompt": "Mara in the hall", "negative": "no logos", "width": 928, "height": 1664, "seed": 7},
    )
    assert filled["c7"]["inputs"]["text"] == "Mara in the hall"
    assert filled["c8"]["inputs"]["text"] == "no logos"
    assert filled["w4"]["inputs"]["width"] == 928
    assert filled["h4"]["inputs"]["height"] == 1664
    assert filled["seed6"]["inputs"]["seed"] == 7
    assert graph["c7"]["inputs"]["text"] == ""
    assert copy.deepcopy(graph)["w4"]["inputs"]["width"] == 1344


def test_h3_extend_workflow_exposes_video_input():
    contract = parse_workflow(get_workflow("h3-extend")["graph"])
    assert contract["has_video_input"] is True
    assert contract["asks_h3"] is False
    video = next(slot for slot in contract["slots"] if slot["canonical"] == "video" and slot["direction"] == "input")
    assert video["node_id"] == "v30"


def test_h3_profile_is_structured_and_does_not_claim_a_model():
    sections = h3_sections(prompt="She turns.", subjects="Mara", location="hall", audio="room tone")
    text = h3_profile_text(sections)
    assert "Subject definitions:" in text
    assert "Non-diegetic music:" in text
    assert text.index("Subject definitions:") < text.index("Non-diegetic music:")
    assert "Mara" in text
    assert "model" not in text.lower()


def test_shot_break_allocates_time_and_lines():
    plan = plan_clips(
        action="Mara waits. She turns.",
        dialogue="Hello.\nAgain.\nLater.\nEnough.",
        scene_s=30,
        target_s=8,
        min_s=5,
        max_s=10,
    )
    assert plan["rendered"] is False
    assert plan["plan_only"] is True
    assert plan["clip_count"] == 4
    assert abs(sum(clip["duration_s"] for clip in plan["clips"]) - 30) < 0.02
    for clip in plan["clips"]:
        assert 5 <= clip["duration_s"] <= 10
        assert clip["coverage"]["rendered"] is False
    dialogue = [index for clip in plan["clips"] for index in clip["coverage"]["dialogue_indexes"]]
    action = [index for clip in plan["clips"] for index in clip["coverage"]["action_indexes"]]
    assert dialogue == [0, 1, 2, 3]
    assert action == [0, 1]
    short = plan_clips(action="A blink.", dialogue="", scene_s=3, target_s=8, min_s=5, max_s=10)
    assert short["clip_count"] == 1
    assert short["clips"][0]["coverage"]["short"] is True
    assert short["clips"][0]["duration_s"] == 3
    wide = plan_clips(action="One beat.", dialogue="Line.", scene_s=11, target_s=8, min_s=5, max_s=10)
    assert wide["clip_count"] == 2
    assert abs(sum(clip["duration_s"] for clip in wide["clips"]) - 11) < 0.02


def _ready_wizard(client, auth) -> dict:
    started = client.post(
        "/api/create/wizard",
        headers=auth,
        json={"prompt": "Mara waits in the hall. She turns."},
    )
    assert started.status_code == 201, started.text
    wizard_id = started.json()["id"]
    for step, answers in (
        ("format", {"format": "short-drama"}),
        ("length", {"shot_count": 2, "target_length_s": 20}),
        ("tone", {"tone": "quiet", "look": "sodium"}),
        (
            "scope",
            {
                "audience": "late-night viewers",
                "deliverables": "two clips",
                "negative_constraints": "no logos",
            },
        ),
        ("cast", {"cast_notes": "Mara — lead"}),
        ("audio", {"audio_notes": "room tone"}),
    ):
        patched = client.patch(
            f"/api/create/wizard/{wizard_id}",
            headers=auth,
            json={"step": step, "answers": answers},
        )
        assert patched.status_code == 200, patched.text
    finished = client.post(f"/api/create/wizard/{wizard_id}/finish", headers=auth)
    assert finished.status_code == 200, finished.text
    return finished.json()


def test_clarify_blocks_finish_until_the_brief_is_answered(client, auth):
    started = client.post("/api/create/wizard", headers=auth, json={"prompt": "A door opens."})
    wizard_id = started.json()["id"]
    client.patch(
        f"/api/create/wizard/{wizard_id}",
        headers=auth,
        json={"step": "format", "answers": {"format": "custom"}},
    )
    client.patch(
        f"/api/create/wizard/{wizard_id}",
        headers=auth,
        json={"step": "length", "answers": {"shot_count": 1, "target_length_s": 8}},
    )
    blocked = client.post(f"/api/create/wizard/{wizard_id}/finish", headers=auth)
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "clarify_required"
    fields = {row["field"] for row in detail["questions"]}
    assert "audience" in fields
    assert "deliverables" in fields
    paused = client.get(f"/api/create/wizard/{wizard_id}/clarify", headers=auth)
    assert paused.status_code == 200
    assert paused.json()["ready"] is False
    acknowledged = client.post(
        f"/api/create/wizard/{wizard_id}/finish?acknowledge_gaps=true",
        headers=auth,
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["generate_ready"] is False
    assert acknowledged.json()["director"]["called_comfy"] is False


def test_prompt_preview_draft_rewrite_and_no_blind_enqueue(client, auth, monkeypatch):
    done = _ready_wizard(client, auth)
    episode_id = done["episode_id"]
    preview = client.post(
        "/api/jobs/preview",
        headers=auth,
        json={
            "episode_id": episode_id,
            "job_type": "still-sheet",
            "payload": {"workflow_id": "character-sheet", "prompt": "Mara waits."},
        },
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["called_comfy"] is False
    assert body["stub"] is True
    assert body["prompt"] == "Mara waits."
    assert "unset" in body["cause"].lower() or "stub" in body["cause"].lower()
    assert body["prompt_profile"] == "h3"
    draft_id = body["id"]
    edited = client.patch(
        f"/api/jobs/preview/{draft_id}",
        headers=auth,
        json={"prompt": "Mara waits, then turns.", "negative": "no logos"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["prompt"] == "Mara waits, then turns."
    rewritten = client.post(f"/api/jobs/preview/{draft_id}/rewrite", headers=auth)
    assert rewritten.status_code == 200, rewritten.text
    assert rewritten.json()["rewrite_source"] == "structured"
    assert rewritten.json()["model_ran"] is False
    assert "Subject definitions:" in rewritten.json()["prompt"]
    plain = client.post(
        "/api/jobs/preview",
        headers=auth,
        json={"episode_id": episode_id, "job_type": "still-sheet", "payload": {"prompt": "plain"}},
    )
    refused = client.post(f"/api/jobs/preview/{plain.json()['id']}/rewrite", headers=auth)
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "profile_not_requested"
    monkeypatch.setenv("STUDIO_REQUIRE_PROMPT_PREVIEW", "true")
    get_settings.cache_clear()
    blind = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode_id, "job_type": "still-sheet", "payload": {"prompt": "blind"}},
    )
    assert blind.status_code == 409, blind.text
    assert blind.json()["detail"]["code"] == "preview_required"
    queued = client.post(
        "/api/jobs",
        headers=auth,
        json={
            "episode_id": episode_id,
            "job_type": "still-sheet",
            "payload": {"preview_id": draft_id},
        },
    )
    assert queued.status_code == 201, queued.text
    job = queued.json()
    assert job["adapter"] == "stub"
    assert job["result"]["called_comfy"] is False
    assert job["result"]["outcome"] == "fixture"
    assert job["result"]["stub"] is True
    assert "Subject definitions:" in job["payload"]["prompt"]
    cancelled = client.post(
        "/api/jobs/preview",
        headers=auth,
        json={"episode_id": episode_id, "job_type": "still-plate", "payload": {"prompt": "plate"}},
    )
    cancel = client.post(f"/api/jobs/preview/{cancelled.json()['id']}/cancel", headers=auth)
    assert cancel.json()["status"] == "cancelled"
    again = client.post(
        "/api/jobs",
        headers=auth,
        json={
            "episode_id": episode_id,
            "job_type": "still-plate",
            "payload": {"preview_id": cancelled.json()["id"]},
        },
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "preview_cancelled"
    get_settings.cache_clear()


def test_coverage_persists_on_the_board_without_a_render(client, auth):
    done = _ready_wizard(client, auth)
    episode_id = done["episode_id"]
    broken = client.post(
        f"/api/episodes/{episode_id}/coverage",
        headers=auth,
        json={
            "action": "Mara waits. She turns.",
            "dialogue": "Hello.\nAgain.",
            "scene_s": 16,
            "target_s": 8,
            "min_s": 5,
            "max_s": 10,
        },
    )
    assert broken.status_code == 200, broken.text
    body = broken.json()
    assert body["rendered"] is False
    assert body["plan_only"] is True
    assert body["clip_count"] == 2
    shots = body["shots"]
    assert len(shots) == 2
    assert all(shot["readiness"] == "draft" for shot in shots)
    assert all(shot["preview"] is None for shot in shots)
    assert all(shot["coverage"]["plan_only"] is True for shot in shots)
    assert all(shot["coverage"]["rendered"] is False for shot in shots)
    indexes = [index for shot in shots for index in shot["coverage"]["dialogue_indexes"]]
    assert indexes == [0, 1]
    listed = client.get(f"/api/episodes/{episode_id}/shots", headers=auth)
    assert [row["edit_row_id"] for row in listed.json()] == ["cov-1", "cov-2"]


def test_continue_clip_requires_a_video_input_role(client, auth):
    done = _ready_wizard(client, auth)
    episode_id = done["episode_id"]
    broken = client.post(
        f"/api/episodes/{episode_id}/coverage",
        headers=auth,
        json={"action": "Mara waits. She turns.", "dialogue": "Hello.", "scene_s": 16},
    )
    assert broken.status_code == 200, broken.text
    second = broken.json()["shots"][1]
    missing = client.post(
        "/api/jobs/preview",
        headers=auth,
        json={
            "episode_id": episode_id,
            "shot_id": second["id"],
            "job_type": "clip-hop1",
            "payload": {"workflow_id": "character-sheet", "continue_from": "previous", "prompt": "She turns."},
        },
    )
    assert missing.status_code == 200, missing.text
    blocked = missing.json()
    assert blocked["continue"]["allowed"] is False
    assert blocked["continue"]["has_video_input"] is False
    assert blocked["generate_enabled"] is False
    assert "(Input:video)" in blocked["warning"]
    enqueue = client.post(
        "/api/jobs",
        headers=auth,
        json={
            "episode_id": episode_id,
            "shot_id": second["id"],
            "job_type": "clip-hop1",
            "payload": {"preview_id": blocked["id"]},
        },
    )
    assert enqueue.status_code == 409, enqueue.text
    assert enqueue.json()["detail"]["code"] == "continue_blocked"
    allowed = client.post(
        "/api/jobs/preview",
        headers=auth,
        json={
            "episode_id": episode_id,
            "shot_id": second["id"],
            "job_type": "clip-hop1",
            "payload": {"workflow_id": "h3-extend", "continue_from": "previous", "prompt": "She turns."},
        },
    )
    assert allowed.status_code == 200, allowed.text
    body = allowed.json()
    assert body["continue"]["allowed"] is True
    assert body["continue"]["has_video_input"] is True
    assert body["continue"]["video_resolved"] is False
    assert body["continue"]["previous_shot_id"]
    assert "video" in body["warning"].lower()
    assert body["called_comfy"] is False


def test_workflow_import_rejects_untagged_graphs(client, auth):
    bad = client.post(
        "/api/workflows",
        headers=auth,
        json={"name": "bare", "graph": {"3": {"class_type": "Note", "inputs": {}}}},
    )
    assert bad.status_code == 400, bad.text
    assert "Input:role" in bad.json()["detail"]
    listed = client.get("/api/workflows", headers=auth)
    ids = {row["id"] for row in listed.json()}
    assert "character-sheet" in ids
    assert "h3-extend" in ids


def test_ref_role_round_trip(client, auth):
    done = _ready_wizard(client, auth)
    episode_id = done["episode_id"]
    uploaded = client.post(
        f"/api/episodes/{episode_id}/media",
        headers=auth,
        data={"kind": "sheet", "entity_label": "Mara", "ref_role": "identity-lock"},
        files={"file": ("mara.txt", b"lock notes", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["ref_role"] == "identity-lock"
    asset_id = uploaded.json()["id"]
    patched = client.patch(
        f"/api/episodes/{episode_id}/media/{asset_id}",
        headers=auth,
        json={"ref_role": "environment"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["ref_role"] == "environment"
    preview = client.post(
        "/api/jobs/preview",
        headers=auth,
        json={"episode_id": episode_id, "job_type": "still-sheet", "payload": {"prompt": "Mara"}},
    )
    roles = {ref["ref_role"] for ref in preview.json()["refs"] if ref.get("source") == "asset"}
    assert "environment" in roles


def test_stitched_run_does_not_complete_the_episode(monkeypatch):
    monkeypatch.setattr("app.agentrun.flag_modified", lambda *_args, **_kwargs: None)
    from app.agentrun import honesty_note, recompute

    run = SimpleNamespace(
        status="queued",
        called_comfy=False,
        hermes_ran=False,
        stitch_state="",
        plan={},
        updated_at=None,
    )
    recompute(
        run,
        [
            {"kind": "clip-hop1", "status": "succeeded", "called_comfy": False},
            {
                "kind": "stitch",
                "status": "succeeded",
                "stitch_state": "stitched",
                "produced_mp4": True,
                "called_comfy": False,
            },
        ],
    )
    assert run.status == "stitched"
    assert run.hermes_ran is False
    note = honesty_note(run)
    assert "does not mark the episode completed" in note
    assert "generate-ok" in note


def test_ffmpeg_concat_does_not_stamp_generate_ok(tmp_path, monkeypatch):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is not on PATH")
    clips = []
    for name in ("a", "b"):
        dest = tmp_path / f"{name}.mp4"
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=64x64:d=0.2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(dest),
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not dest.is_file():
            pytest.skip("ffmpeg could not write a tiny clip")
        clips.append(dest)
    monkeypatch.setattr(
        "app.stitch.render_playlist",
        lambda _episode: {
            "format": "mp4",
            "fps": 24,
            "shots": [
                {
                    "sort_index": index,
                    "edit_row_id": f"row-{index}",
                    "take": "A",
                    "join": "cut",
                    "duration_s": 0.2,
                    "frames": 5,
                    "rec_in_tc": "00:00:00:00",
                    "rec_out_tc": "00:00:00:05",
                    "media_path": str(path),
                }
                for index, path in enumerate(clips)
            ],
        },
    )
    monkeypatch.setattr("app.stitch.get_settings", lambda: SimpleNamespace(media_path=tmp_path))
    episode = SimpleNamespace(id="ep-stitch", review_state="draft")
    from app.stitch import run_stitch

    result = run_stitch(SimpleNamespace(id="job-stitch"), episode, lambda _progress: None)
    assert result.ok is True
    assert result.receipt["produced_mp4"] is True
    assert result.receipt["episode_completed"] is False
    assert result.receipt["generate_ok"] is False
    assert result.receipt["called_comfy"] is False
    assert episode.review_state == "draft"
