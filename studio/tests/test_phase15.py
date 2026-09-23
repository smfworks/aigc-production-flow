"""Phase 15: CLIP_BRIDGE continuity, prompt assembly, and conform honesty."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.clipbridge import (
    SPEC_PATH,
    alignment_line,
    assemble_h3_prompt,
    assemble_qwen_end,
    assemble_qwen_q1,
    assemble_qwen_q4,
    assemble_qwen_q5,
    assemble_qwen_q6,
    assemble_qwen_start,
    conform_execute,
    conform_plan,
    copy_handoff_states,
    extract_last_frame,
    extract_last_frame_cmd,
    handoff_equal,
    load_forge_fixture,
    preflight,
    prompt_text_issues,
    trim_held_tail_cmd,
    write_project,
)
from app.config import get_settings
from tests.helpers import create_episode

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "clip_bridge_conform.sh"


def test_forge_fixture_copies_the_handoff_chain():
    lock, clips = load_forge_fixture()
    assert lock.project_id == "forge_dawn_01"
    assert lock.duration_s == 10
    assert len(clips) == 6
    for index in range(5):
        assert clips[index + 1].start_state == clips[index].end_state
        assert handoff_equal(clips[index + 1].start_state, clips[index].end_state)
    assert clips[1].start_image == clips[0].end_extracted
    assert clips[2].start_image == clips[1].end_extracted
    assert clips[4].start_image == clips[3].end_extracted
    assert clips[5].start_image == clips[4].end_extracted
    assert clips[3].transition_in == "T-MATCH"
    assert clips[3].start_image != clips[2].end_extracted
    assert preflight(lock, clips) == []


def test_paraphrase_and_case_change_are_rejected():
    lock, clips = load_forge_fixture()
    paraphrased = clips[1].model_copy(
        update={
            "start_state": (
                "the hammer rests high over a glowing billet, weight on the rear foot, eyes on the steel"
            )
        }
    )
    issues = preflight(lock, [clips[0], paraphrased, *clips[2:]])
    assert any(issue.code == "handoff_state" for issue in issues)
    shifted = clips[1].model_copy(update={"start_state": clips[0].end_state[:1].upper() + clips[0].end_state[1:]})
    assert not handoff_equal(shifted.start_state, clips[0].end_state)
    assert any(
        issue.code == "handoff_state"
        for issue in preflight(lock, [clips[0], shifted, *clips[2:]])
    )
    padded = clips[1].model_copy(update={"start_state": f"  {clips[0].end_state}\n"})
    assert handoff_equal(padded.start_state, clips[0].end_state)
    assert preflight(lock, [clips[0], padded, *clips[2:]]) == []


def test_copy_handoff_assigns_the_previous_end_state():
    _lock, clips = load_forge_fixture()
    dirty = clips[2].model_copy(update={"start_state": "a paraphrased threshold"})
    copied = copy_handoff_states([clips[0], clips[1], dirty, *clips[3:]])
    assert copied[2].start_state == clips[1].end_state
    assert copied[2].end_state == clips[2].end_state
    assert copied[0].start_state == clips[0].start_state


def test_duration_verb_camera_and_lock_inheritance():
    lock, clips = load_forge_fixture()
    short = lock.model_copy(update={"duration_s": 8})
    assert any(issue.code == "duration" for issue in preflight(short, clips))
    two_verbs = clips[0].model_copy(update={"action": "walks and strikes"})
    assert any(issue.code == "verb_count" for issue in preflight(lock, [two_verbs, *clips[1:]]))
    stacked = clips[0].model_copy(
        update={"camera_move": "The camera pushes in with small amplitude and then pulls back."}
    )
    assert any(issue.code == "camera_opposing" for issue in preflight(lock, [stacked, *clips[1:]]))
    wardrobe = clips[3].model_copy(update={"wardrobe": "red cloak"})
    assert any(issue.code == "lock_drift" for issue in preflight(lock, [*clips[:3], wardrobe, *clips[4:]]))
    reversed_dir = clips[4].model_copy(update={"screen_direction": "right-to-left"})
    assert any(
        issue.code == "screen_direction" for issue in preflight(lock, [*clips[:4], reversed_dir, clips[5]])
    )
    marked = reversed_dir.model_copy(update={"screen_direction_reversal": True})
    marked_next = clips[5].model_copy(update={"screen_direction": "right-to-left", "screen_direction_reversal": True})
    assert not any(
        issue.code == "screen_direction"
        for issue in preflight(lock, [*clips[:4], marked, marked_next])
    )


def test_hard_start_image_uses_extract_and_designed_still_is_rejected():
    lock, clips = load_forge_fixture()
    imagined = clips[1].model_copy(update={"start_image": "clips/02/imagined.png"})
    assert any(issue.code == "start_image" for issue in preflight(lock, [clips[0], imagined, *clips[2:]]))
    designed = clips[3].model_copy(update={"start_image": clips[2].end_designed})
    assert any(
        issue.code == "designed_as_start" for issue in preflight(lock, [*clips[:3], designed, *clips[4:]])
    )
    mismatch = clips[0].model_copy(
        update={"start_width": 2560, "start_height": 1440, "end_width": 1920, "end_height": 1080}
    )
    assert any(issue.code == "still_size" for issue in preflight(lock, [mismatch, *clips[1:]]))


def test_assemble_fills_slots_without_paraphrasing_states():
    lock, clips = load_forge_fixture()
    spec_line = alignment_line()
    assert spec_line in SPEC_PATH.read_text(encoding="utf-8")
    assert "10.00-second mark" in spec_line
    for clip in clips:
        before = (clip.start_state, clip.end_state)
        prompt = assemble_h3_prompt(lock, clip)
        assert prompt.startswith(spec_line + "\n\n")
        assert clip.start_state in prompt
        assert clip.end_state in prompt
        assert lock.identity in prompt
        assert lock.wardrobe in prompt
        assert lock.negative.strip() in prompt
        assert "dissolves" in prompt
        assert (clip.start_state, clip.end_state) == before
        start = assemble_qwen_start(lock, clip)
        end = assemble_qwen_end(lock, clip)
        assert clip.start_state in start
        assert "<image1>" in start
        head, _, _rest = end.partition("[VISUAL LOCK]")
        assert "<image1>" in head
        assert lock.identity not in head
        assert clip.end_state in end
    q1 = assemble_qwen_q1(lock)
    assert lock.identity in q1
    assert lock.wardrobe in q1
    slotted = clips[2].model_copy(
        update={
            "handoff_action": "walks through a doorway",
            "loc_a": "open bay door",
            "loc_b": "gravel yard",
            "new_time": "blue hour",
        }
    )
    assert "walks through a doorway" in assemble_qwen_q4(lock, slotted)
    assert "open bay door" in assemble_qwen_q5(lock, slotted)
    assert "gravel yard" in assemble_qwen_q5(lock, slotted)
    assert "blue hour" in assemble_qwen_q6(lock, slotted)
    assert "<image1>" in assemble_qwen_q4(lock, slotted)
    cut = assemble_h3_prompt(lock, clips[0]).replace("One continuous uncut shot", "then cut to the yard")
    assert any(
        issue.code == "banned_cut"
        for issue in prompt_text_issues(
            cut,
            partial="h3_prompt",
            negative=lock.negative,
            identity=lock.identity,
            start_state=clips[0].start_state,
            end_state=clips[0].end_state,
        )
    )
    dropped = assemble_h3_prompt(lock, clips[0]).replace(spec_line, "Picture 1 aligns at the 8.00-second mark")
    assert any(
        issue.code == "alignment"
        for issue in prompt_text_issues(
            dropped,
            partial="h3_prompt",
            negative=lock.negative,
            identity=lock.identity,
            start_state=clips[0].start_state,
            end_state=clips[0].end_state,
        )
    )
    redescribed = assemble_qwen_end(lock, clips[0]).replace(
        "Using <image1> as identity",
        f"Using {lock.identity} as the face",
        1,
    )
    assert any(
        issue.code == "qwen_face"
        for issue in prompt_text_issues(
            redescribed,
            partial="qwen_end",
            negative=lock.negative,
            identity=lock.identity,
            start_state=clips[0].start_state,
            end_state=clips[0].end_state,
        )
    )


def test_project_files_and_conform_do_not_invent_an_mp4(tmp_path: Path):
    lock, clips = load_forge_fixture()
    root = tmp_path / "project"
    write_project(root, lock, clips)
    saved = (root / "clips" / "03" / "prompt_h3.txt").read_text(encoding="utf-8")
    assert saved == assemble_h3_prompt(lock, clips[2])
    assert clips[2].start_state in (root / "clips" / "03" / "prompt_qwen_start.txt").read_text(encoding="utf-8")
    assert not (root / "export" / "story.mp4").exists()
    plan = conform_plan(clips)
    assert plan["produced_mp4"] is False
    assert plan["called_comfy"] is False
    assert plan["extract"][0] == extract_last_frame_cmd(
        Path("clips/01/clip.mp4"),
        Path("clips/01/end_extracted.png"),
    )
    assert 'trim=end_frame=239' in plan["trim"][0]
    assert plan["concat_list"].startswith("file '../clips/01/clip_trim.mp4'\n")
    executed = conform_execute(root, clips)
    assert executed["produced_mp4"] is False
    assert "No MP4 was invented" in executed["reason"]
    assert not (root / "export" / "story.mp4").exists()
    missing = tmp_path / "missing.mp4"
    ghost = tmp_path / "ghost.png"
    refused = extract_last_frame(missing, ghost)
    assert refused["produced"] is False
    assert refused["produced_mp4"] is False
    assert not ghost.exists()
    assert trim_held_tail_cmd(Path("clips/01/clip.mp4"), Path("clips/01/clip_trim.mp4"))[4:6] == [
        "-vf",
        "trim=end_frame=239",
    ]


def test_ffmpeg_extracts_a_real_frame_and_the_script_refuses_a_missing_file(tmp_path: Path):
    dest = tmp_path / "should-not-exist.png"
    proc = subprocess.run(
        ["sh", str(SCRIPT), "extract", str(tmp_path / "nope.mp4"), str(dest)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
    assert not dest.exists()
    assert "No frame was invented" in proc.stderr
    src = tmp_path / "clip.mp4"
    built = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=256x144:r=24:d=1",
            "-frames:v",
            "24",
            str(src),
        ],
        capture_output=True,
        check=False,
    )
    assert built.returncode == 0, built.stderr[-200:]
    frame = tmp_path / "end_extracted.png"
    extracted = extract_last_frame(src, frame)
    assert extracted["ok"] is True
    assert extracted["called_comfy"] is False
    assert extracted["produced_mp4"] is False
    assert frame.is_file() and frame.stat().st_size > 0


def test_api_preview_shows_exact_strings_and_blocks_a_paraphrase(client, auth, monkeypatch):
    _project, episode = create_episode(client, auth, "Phase 15")
    laid = client.post(
        f"/api/episodes/{episode['id']}/clip-bridge/fixture",
        headers=auth,
        json={"name": "forge_dawn"},
    )
    assert laid.status_code == 200, laid.text
    body = laid.json()
    assert body["ok"] is True
    assert body["called_comfy"] is False
    assert body["hermes_ran"] is False
    assert body["produced_mp4"] is False
    assert body["clips"][1]["start_state"] == body["clips"][0]["end_state"]
    shot = next(row for row in body["shots"] if row["bridge"]["clip_id"] == "03")
    preview = client.post(
        "/api/jobs/preview",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": shot["id"], "job_type": "clip-hop1"},
    )
    assert preview.status_code == 200, preview.text
    shown = preview.json()
    assert shown["called_comfy"] is False
    assert shown["stub"] is True
    assert shown["prompt"] == shown["clip_bridge"]["h3_prompt"]
    assert shown["prompt"].startswith(alignment_line())
    assert shot["bridge"]["start_state"] in shown["prompt"]
    assert shot["bridge"]["end_state"] in shown["prompt"]
    assert shot["bridge"]["start_state"] in shown["clip_bridge"]["qwen_start"]
    qwen_head = shown["clip_bridge"]["qwen_end"].split("[VISUAL LOCK]")[0]
    assert "<image1>" in qwen_head
    assert shown["clip_bridge"]["identity"] not in qwen_head
    assert shown["clip_bridge"]["produced_mp4"] is False
    still = client.post(
        "/api/jobs/preview",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": shot["id"], "job_type": "still-sheet"},
    )
    assert still.status_code == 200, still.text
    still_body = still.json()
    assert still_body["prompt"] == still_body["clip_bridge"]["qwen_start"]
    assert still_body["generate_enabled"] is True
    assert still_body["called_comfy"] is False
    rewrite = client.post(f"/api/jobs/preview/{still_body['id']}/rewrite", headers=auth)
    assert rewrite.status_code == 409
    assert rewrite.json()["detail"]["code"] == "clip_bridge_dialect"
    queued = client.post(
        "/api/jobs",
        headers=auth,
        json={
            "episode_id": episode["id"],
            "shot_id": shot["id"],
            "job_type": "still-sheet",
            "payload": {"preview_id": still_body["id"]},
        },
    )
    assert queued.status_code == 201, queued.text
    job = queued.json()
    assert job["adapter"] == "stub"
    assert job["result"]["called_comfy"] is False
    assert job["result"]["outcome"] == "fixture"
    assert shot["bridge"]["start_state"] in job["payload"]["prompt"]

    raw = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "clip_bridge" / "forge_dawn.json").read_text(
            encoding="utf-8"
        )
    )
    raw["clips"][1]["start_state"] = "the hammer is high above the steel, weight back, eyes down"
    rejected = client.put(
        f"/api/episodes/{episode['id']}/clip-bridge",
        headers=auth,
        json=raw,
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["ok"] is False
    assert any(issue["code"] == "handoff_state" for issue in rejected.json()["issues"])
    bad_shot = next(row for row in rejected.json()["shots"] if row["bridge"]["clip_id"] == "02")
    bad_preview = client.post(
        "/api/jobs/preview",
        headers=auth,
        json={"episode_id": episode["id"], "shot_id": bad_shot["id"], "job_type": "still-sheet"},
    )
    assert bad_preview.json()["generate_enabled"] is False
    blocked = client.post(
        "/api/jobs",
        headers=auth,
        json={
            "episode_id": episode["id"],
            "shot_id": bad_shot["id"],
            "job_type": "still-sheet",
            "payload": {"preview_id": bad_preview.json()["id"]},
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "clip_bridge_rejected"

    monkeypatch.setenv("STUDIO_REQUIRE_PROMPT_PREVIEW", "true")
    get_settings.cache_clear()
    blind = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode["id"], "job_type": "still-sheet", "payload": {"prompt": "blind"}},
    )
    assert blind.status_code == 409
    assert blind.json()["detail"]["code"] == "preview_required"
    get_settings.cache_clear()


def test_retry_does_not_rewrite_the_lock_or_earlier_states(client, auth):
    _project, episode = create_episode(client, auth, "Phase 15 retry")
    laid = client.post(
        f"/api/episodes/{episode['id']}/clip-bridge/fixture",
        headers=auth,
        json={"name": "forge_dawn"},
    ).json()
    retried = client.post(
        f"/api/episodes/{episode['id']}/clip-bridge/retry",
        headers=auth,
        json={"clip_id": "03"},
    )
    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["lock_unchanged"] is True
    assert body["called_comfy"] is False
    assert body["story_lock"] == laid["story_lock"]
    for clip_id in ("01", "02"):
        before = next(clip for clip in laid["clips"] if clip["clip_id"] == clip_id)
        after = next(clip for clip in body["clips"] if clip["clip_id"] == clip_id)
        assert after["start_state"] == before["start_state"]
        assert after["end_state"] == before["end_state"]
    conformed = client.post(
        f"/api/episodes/{episode['id']}/clip-bridge/conform",
        headers=auth,
        json={"execute": True},
    )
    assert conformed.status_code == 200, conformed.text
    assert conformed.json()["produced_mp4"] is False
    assert conformed.json()["called_comfy"] is False
    assert "No MP4 was invented" in conformed.json()["reason"]


def test_copy_handoff_endpoint_repairs_a_paraphrase(client, auth):
    _project, episode = create_episode(client, auth, "Phase 15 copy")
    client.post(
        f"/api/episodes/{episode['id']}/clip-bridge/fixture",
        headers=auth,
        json={"name": "forge_dawn"},
    )
    raw = json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures" / "clip_bridge" / "forge_dawn.json").read_text(
            encoding="utf-8"
        )
    )
    raw["clips"][4]["start_state"] = "he walks outside toward the ridge"
    client.put(f"/api/episodes/{episode['id']}/clip-bridge", headers=auth, json=raw)
    copied = client.post(f"/api/episodes/{episode['id']}/clip-bridge/copy-handoff", headers=auth)
    assert copied.status_code == 200, copied.text
    clips = copied.json()["clips"]
    assert clips[4]["start_state"] == clips[3]["end_state"]
    assert copied.json()["ok"] is True
    assert copied.json()["produced_mp4"] is False
