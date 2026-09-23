"""CLIP_BRIDGE continuity bridge. docs/CLIP_BRIDGE.md is the prompt dialect.

Slots are filled from the story lock and the clip object. Locked continuity
strings are copied with strip() only. This module does not call Comfy or Hermes
and does not invent an MP4.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .config import get_settings
from .models import Episode, Shot

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "CLIP_BRIDGE.md"
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "clip_bridge" / "forge_dawn.json"

DIALECT = "clip-bridge"
CLIP_DURATION = 10.0
TRIM_END_FRAME = 239
HARD_HANDOFF = frozenset({"T-HARD", "T-POSE", "T-CAMERA", "T-LIGHT", "T-PROP", "T-LOOK-OFF"})
SOFT_HANDOFF = frozenset({"T-MATCH", "T-EXIT-ENTER", "T-OCCLUSION"})
KNOWN_TRANSITIONS = HARD_HANDOFF | SOFT_HANDOFF | frozenset({"NONE", ""})
LOCK_FIELDS = ("identity", "wardrobe", "palette", "lighting_bible")
PROMPT_ISSUE_CODES = frozenset(
    {"alignment", "landing_timestamp", "banned_cut", "paraphrase", "qwen_face"}
)
_MOVE = re.compile(r"(?<![a-z])(push|pull|track|arc|tilt|pedestal)", re.IGNORECASE)
_SLOT = re.compile(r"\{([A-Za-z0-9_]+)\}")
_BANNED = ("cut to", "smash cut", "dissolve", "[shot 2]")


class StoryLock(BaseModel):
    """story_lock.json from CLIP_BRIDGE §4."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    aspect: str = "16:9"
    width: int = 2560
    height: int = 1440
    fps: int = 24
    duration_s: float = CLIP_DURATION
    lens: str
    style: str
    identity: str
    wardrobe: str
    palette: str
    lighting_bible: str
    screen_direction: str
    negative: str
    character_sheet: str = ""
    wardrobe_sheet: str = ""
    location_plates: list[str] = Field(default_factory=list)


class ClipItem(BaseModel):
    """One clips.json item from CLIP_BRIDGE §4, plus bridge measurement slots."""

    model_config = ConfigDict(extra="forbid")

    clip_id: str
    purpose: str = ""
    location: str = ""
    time_of_day: str = ""
    start_state: str
    end_state: str
    action: str
    action_beats: list[str] = Field(default_factory=list)
    camera_start: str = ""
    camera_end: str = ""
    camera_move: str
    screen_direction: str = ""
    screen_direction_reversal: bool = False
    prop_state_start: str = ""
    prop_state_end: str = ""
    transition_in: str = ""
    transition_out: str = ""
    start_image: str = ""
    end_designed: str = ""
    end_extracted: str = ""
    video: str = ""
    status: str = "planned"
    soundscape: str = ""
    music: str = "N/A"
    start_frame_prompt: str = ""
    end_frame_prompt: str = ""
    h3_prompt: str = ""
    identity: str = ""
    wardrobe: str = ""
    palette: str = ""
    lighting_bible: str = ""
    start_width: int | None = None
    start_height: int | None = None
    end_width: int | None = None
    end_height: int | None = None
    handoff_action: str = ""
    loc_a: str = ""
    loc_b: str = ""
    new_time: str = ""
    start_shot_type: str = ""
    end_shot_type: str = ""
    target: str = ""
    prop: str = ""
    next_location: str = ""


@dataclass(frozen=True)
class BridgeIssue:
    code: str
    message: str
    clip_id: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "clip_id": self.clip_id}


def handoff_equal(left: str, right: str) -> bool:
    """Continuity editor compare: strip only. No case fold, no fuzzy match."""
    return left.strip() == right.strip()


def copy_handoff_states(clips: list[ClipItem]) -> list[ClipItem]:
    """Copy clip N end_state into clip N+1 start_state. String assignment, not a rewrite."""
    copied: list[ClipItem] = []
    for index, clip in enumerate(clips):
        if index == 0:
            copied.append(clip)
            continue
        copied.append(clip.model_copy(update={"start_state": clips[index - 1].end_state.strip()}))
    return copied


@lru_cache(maxsize=1)
def spec_text() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=32)
def fence_after(heading: str) -> str:
    text = spec_text()
    idx = text.index(heading)
    open_fence = text.index("```", idx)
    start = text.index("\n", open_fence) + 1
    end = text.index("```", start)
    return text[start:end].strip("\n")


def alignment_line() -> str:
    return fence_after("### H0 ").splitlines()[0]


def fill(template: str, **slots: object) -> str:
    """Replace {slot} markers. {identity short} is the locked identity string."""
    text = template.replace("{identity short}", str(slots.get("identity", "")))

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in slots:
            return match.group(0)
        value = slots[key]
        return "" if value is None else str(value)

    return _SLOT.sub(repl, text)


def visual_lock_block(lock: StoryLock) -> str:
    return fill(
        fence_after("## 6. Visual lock text"),
        identity=lock.identity.strip(),
        wardrobe=lock.wardrobe.strip(),
        palette=lock.palette.strip(),
        lighting_bible=lock.lighting_bible.strip(),
        lens=lock.lens.strip(),
        aspect=lock.aspect.strip(),
        width=lock.width,
        height=lock.height,
        fps=lock.fps,
        negative=lock.negative.strip(),
    )


def _direction(lock: StoryLock, clip: ClipItem) -> str:
    written = clip.screen_direction.strip()
    return written or lock.screen_direction.strip()


def h1(lock: StoryLock, clip: ClipItem) -> str:
    return fill(
        fence_after("### H1 "),
        identity=lock.identity.strip(),
        start_state=clip.start_state.strip(),
        location=clip.location.strip(),
        time_of_day=clip.time_of_day.strip(),
        wardrobe=lock.wardrobe.strip(),
        prop_state_start=clip.prop_state_start.strip(),
        camera_start=clip.camera_start.strip(),
        lighting_bible=lock.lighting_bible.strip(),
    )


def h2(clip: ClipItem) -> str:
    return fill(
        fence_after("### H2 "),
        end_state=clip.end_state.strip(),
        prop_state_end=clip.prop_state_end.strip(),
        camera_end=clip.camera_end.strip(),
    )


def h3_action(lock: StoryLock, clip: ClipItem) -> str:
    beats = [beat.strip() for beat in clip.action_beats if beat and beat.strip()]
    return fill(
        fence_after("### H3 "),
        action=clip.action.strip(),
        beat1=beats[0] if len(beats) > 0 else "",
        beat2=beats[1] if len(beats) > 1 else "",
        beat3=beats[2] if len(beats) > 2 else "",
        screen_direction=_direction(lock, clip),
    )


def assemble_h3_prompt(lock: StoryLock, clip: ClipItem) -> str:
    """§14 recipe. The alignment line is copied from CLIP_BRIDGE.md."""
    alignment = alignment_line()
    body = (
        f"integrated_multimodal_description: [Shot 1] {lock.style}. "
        f"Begin exactly from Picture 1. {visual_lock_block(lock)} "
        f"{h1(lock, clip)} {clip.camera_move.strip()} as {h3_action(lock, clip)}. "
        f"{h2(clip)} "
        "One continuous uncut shot. Keep identity, wardrobe, and lighting recipe locked.\n\n"
        f"overall_soundscape: {clip.soundscape.strip()}\n"
        f"non_diegetic_music: {clip.music.strip()}"
    )
    return alignment + "\n\n" + body + "\n\n" + lock.negative.strip()


def _micro(lock: StoryLock) -> str:
    return fill(fence_after("### Qwen micro-partials"), aspect=lock.aspect.strip())


def _qwen(body: str, lock: StoryLock, *, micro: bool) -> str:
    parts = [body.rstrip()]
    if micro:
        parts.append(_micro(lock))
    parts.append(visual_lock_block(lock))
    return "\n\n".join(parts) + "\n"


def _type_line(heading: str, code: str, **slots: object) -> str:
    if not code.strip():
        return ""
    table: dict[str, str] = {}
    for line in fence_after(heading).splitlines():
        piece = line.strip()
        if not piece:
            continue
        token, _, rest = piece.partition(" ")
        table[token.strip()] = rest.strip()
    template = table.get(code.strip())
    if template is None:
        return ""
    return fill(template, **slots)


def _shot_slots(lock: StoryLock, clip: ClipItem) -> dict[str, object]:
    return {
        "screen_direction": _direction(lock, clip),
        "target": clip.target.strip(),
        "prop": clip.prop.strip(),
        "next_location": clip.next_location.strip(),
        "aspect": lock.aspect.strip(),
        "width": lock.width,
        "height": lock.height,
    }


def assemble_qwen_q1(lock: StoryLock) -> str:
    body = fill(
        fence_after("### Q1 "),
        identity=lock.identity.strip(),
        wardrobe=lock.wardrobe.strip(),
        aspect=lock.aspect.strip(),
    )
    return _qwen(body, lock, micro=False)


def assemble_qwen_start(lock: StoryLock, clip: ClipItem) -> str:
    body = fill(
        fence_after("### Q2 "),
        clip_id=clip.clip_id.strip(),
        start_state=clip.start_state.strip(),
        location=clip.location.strip(),
        camera_start=clip.camera_start.strip(),
        prop_state_start=clip.prop_state_start.strip(),
        screen_direction=_direction(lock, clip),
        width=lock.width,
        height=lock.height,
    )
    extra = _type_line("### Start-frame shot types", clip.start_shot_type, **_shot_slots(lock, clip))
    if extra:
        body = body.rstrip() + "\n" + extra
    return _qwen(body, lock, micro=True)


def assemble_qwen_end(lock: StoryLock, clip: ClipItem) -> str:
    body = fill(
        fence_after("### Q3 "),
        end_state=clip.end_state.strip(),
        prop_state_end=clip.prop_state_end.strip(),
        camera_end=clip.camera_end.strip(),
        width=lock.width,
        height=lock.height,
    )
    extra = _type_line("### End-frame shot types", clip.end_shot_type, **_shot_slots(lock, clip))
    if extra:
        body = body.rstrip() + "\n" + extra
    return _qwen(body, lock, micro=True)


def assemble_qwen_q4(lock: StoryLock, clip: ClipItem) -> str:
    body = fill(
        fence_after("### Q4 "),
        handoff_action=clip.handoff_action.strip(),
        screen_direction=_direction(lock, clip),
        width=lock.width,
        height=lock.height,
    )
    return _qwen(body, lock, micro=True)


def assemble_qwen_q5(lock: StoryLock, clip: ClipItem) -> str:
    body = fill(
        fence_after("### Q5 "),
        loc_a=clip.loc_a.strip(),
        loc_b=clip.loc_b.strip(),
        width=lock.width,
        height=lock.height,
        aspect=lock.aspect.strip(),
    )
    return _qwen(body, lock, micro=True)


def assemble_qwen_q6(lock: StoryLock, clip: ClipItem) -> str:
    body = fill(
        fence_after("### Q6 "),
        new_time=clip.new_time.strip(),
    )
    return _qwen(body, lock, micro=True)


def verb_bank() -> tuple[str, ...]:
    raw = fence_after("### Verb bank").replace("\n", " ")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def camera_bank() -> tuple[str, ...]:
    return tuple(line.strip() for line in fence_after("### Camera bank").splitlines() if line.strip())


def verbs_in(action: str) -> list[str]:
    text = action.strip().lower()
    hits: list[tuple[int, int, str]] = []
    for verb in verb_bank():
        pattern = re.compile(rf"(?<![a-z-]){re.escape(verb)}(?![a-z-])")
        for match in pattern.finditer(text):
            hits.append((match.start(), match.end(), verb))
    hits.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    kept: list[tuple[int, int, str]] = []
    for start, end, verb in hits:
        if any(not (end <= prev_start or start >= prev_end) for prev_start, prev_end, _verb in kept):
            continue
        kept.append((start, end, verb))
    kept.sort()
    return [verb for _start, _end, verb in kept]


def _camera_tokens(camera_move: str) -> list[tuple[str, set[str]]]:
    found: list[tuple[str, set[str]]] = []
    clauses = re.split(r"[.;]|\b(?:and|then|plus)\b", camera_move, flags=re.IGNORECASE)
    for clause in clauses:
        cleaned = re.sub(r"\b(?:no|not|without)\s+[a-z-]+", " ", clause, flags=re.IGNORECASE)
        flags: set[str] = set()
        lowered = cleaned.lower()
        if "left-to-right" in lowered or "camera-left" in lowered:
            flags.add("ltr")
        if "right-to-left" in lowered or "camera-right" in lowered:
            flags.add("rtl")
        if re.search(r"\bup\b", lowered):
            flags.add("up")
        if re.search(r"\bdown\b", lowered):
            flags.add("down")
        for match in _MOVE.finditer(cleaned):
            found.append((match.group(1).lower(), flags))
    return found


def camera_issue(camera_move: str) -> BridgeIssue | None:
    text = camera_move.strip()
    if not text:
        return BridgeIssue("camera_missing", "Each clip needs one camera move from the CLIP_BRIDGE bank.")
    tokens = _camera_tokens(text)
    names = [name for name, _flags in tokens]
    distinct = list(dict.fromkeys(names))
    if len(distinct) >= 2:
        return BridgeIssue(
            "camera_opposing",
            "camera_move stacks more than one camera move (" + " and ".join(distinct) + ").",
        )
    directions: set[str] = set()
    for _name, flags in tokens:
        directions |= flags
    if "ltr" in directions and "rtl" in directions:
        return BridgeIssue("camera_opposing", "camera_move reverses screen direction in one clip.")
    if "up" in directions and "down" in directions:
        return BridgeIssue("camera_opposing", "camera_move stacks opposing up and down moves.")
    if {"push", "pull"} <= set(distinct):
        return BridgeIssue("camera_opposing", "camera_move stacks push and pull.")
    if text not in camera_bank():
        return BridgeIssue(
            "camera_not_in_bank",
            "Pick one camera move from the CLIP_BRIDGE bank. Do not paraphrase it into a second move.",
        )
    return None


def is_clip_duration(value: float) -> bool:
    try:
        return abs(float(value) - CLIP_DURATION) < 0.001
    except (TypeError, ValueError):
        return False


def _canvas_ok(width: int, height: int) -> bool:
    if width < 256 or height < 256 or width > 5760 or height > 5760:
        return False
    ratio = width / height
    return (2 / 5) - 1e-9 <= ratio <= (5 / 2) + 1e-9


def _transition(value: str) -> str:
    return value.strip().upper()


def motion_region(prompt: str, negative: str) -> str:
    text = prompt
    banned = negative.strip()
    if banned:
        text = text.replace(banned, "")
    text = text.replace("[NEGATIVE LOCK]", "")
    return text


def prompt_text_issues(
    prompt: str,
    *,
    partial: str,
    negative: str,
    identity: str,
    start_state: str,
    end_state: str,
    clip_id: str = "",
) -> list[BridgeIssue]:
    issues: list[BridgeIssue] = []
    if partial in {"h3_prompt", "H0"}:
        if alignment_line() not in prompt:
            issues.append(
                BridgeIssue(
                    "alignment",
                    "H3 prompt is missing the CLIP_BRIDGE alignment line.",
                    clip_id,
                )
            )
        elif "10.00-second mark" not in alignment_line():
            issues.append(
                BridgeIssue("landing_timestamp", "H3 landing timestamp must be 10.00.", clip_id)
            )
        region = motion_region(prompt, negative).lower()
        hits = [phrase for phrase in _BANNED if phrase in region]
        if hits:
            issues.append(
                BridgeIssue(
                    "banned_cut",
                    "H3 prompt contains " + ", ".join(hits) + ".",
                    clip_id,
                )
            )
        if start_state.strip() and start_state.strip() not in prompt:
            issues.append(
                BridgeIssue(
                    "paraphrase",
                    "H3 prompt does not contain start_state verbatim.",
                    clip_id,
                )
            )
        if end_state.strip() and end_state.strip() not in prompt:
            issues.append(
                BridgeIssue(
                    "paraphrase",
                    "H3 prompt does not contain end_state verbatim.",
                    clip_id,
                )
            )
    if partial in {"qwen_end", "Q3"}:
        head = prompt.split("[VISUAL LOCK]")[0]
        if "<image1>" not in head:
            issues.append(
                BridgeIssue(
                    "qwen_face",
                    "Qwen end prompt must point at <image1> and must not re-describe the face.",
                    clip_id,
                )
            )
        elif identity.strip() and identity.strip() in head:
            issues.append(
                BridgeIssue(
                    "qwen_face",
                    "Qwen end prompt re-describes the locked identity instead of pointing at <image1>.",
                    clip_id,
                )
            )
        if end_state.strip() and end_state.strip() not in prompt:
            issues.append(
                BridgeIssue(
                    "paraphrase",
                    "Qwen end prompt does not contain end_state verbatim.",
                    clip_id,
                )
            )
    if partial in {"qwen_start", "Q2"} and start_state.strip() and start_state.strip() not in prompt:
        issues.append(
            BridgeIssue(
                "paraphrase",
                "Qwen start prompt does not contain start_state verbatim.",
                clip_id,
            )
        )
    if partial in {"qwen_q1", "Q1"} and identity.strip() and identity.strip() not in prompt:
        issues.append(
            BridgeIssue("paraphrase", "Q1 prompt does not contain the locked identity verbatim.", clip_id)
        )
    return issues


def preflight(lock: StoryLock, clips: list[ClipItem]) -> list[BridgeIssue]:
    """§15 checks plus the continuity invariants. Fail closed before a generation."""
    issues: list[BridgeIssue] = []
    if not is_clip_duration(lock.duration_s):
        issues.append(BridgeIssue("duration", "Clip duration must be 10.00 seconds."))
    if int(lock.fps) != 24:
        issues.append(BridgeIssue("fps", "Clip fps must be 24 so the held-tail trim stays on frame 240."))
    if not _canvas_ok(lock.width, lock.height):
        issues.append(
            BridgeIssue(
                "canvas_limits",
                "Lock canvas must keep each side between 256 and 5760 px and aspect between 2:5 and 5:2.",
            )
        )
    for index, clip in enumerate(clips):
        cid = clip.clip_id
        verbs = verbs_in(clip.action)
        if len(verbs) != 1:
            issues.append(
                BridgeIssue(
                    "verb_count",
                    f"Clip {cid} action must contain exactly one verb from the bank (found {verbs or 'none'}).",
                    cid,
                )
            )
        camera = camera_issue(clip.camera_move)
        if camera is not None:
            issues.append(BridgeIssue(camera.code, f"Clip {cid}: {camera.message}", cid))
        if not clip.start_state.strip() or not clip.end_state.strip():
            issues.append(BridgeIssue("state_missing", f"Clip {cid} needs start_state and end_state.", cid))
        for field in LOCK_FIELDS:
            written = getattr(clip, field).strip()
            locked = getattr(lock, field).strip()
            if written and written != locked:
                issues.append(
                    BridgeIssue(
                        "lock_drift",
                        f"Clip {cid} {field} differs from story_lock. The lock is not rewritten to hide drift.",
                        cid,
                    )
                )
        if clip.screen_direction.strip() and clip.screen_direction.strip() != lock.screen_direction.strip():
            if not clip.screen_direction_reversal:
                issues.append(
                    BridgeIssue(
                        "screen_direction",
                        f"Clip {cid} screen_direction differs from the lock without a Director reversal.",
                        cid,
                    )
                )
        if index > 0:
            previous = clips[index - 1]
            if not handoff_equal(clip.start_state, previous.end_state):
                issues.append(
                    BridgeIssue(
                        "handoff_state",
                        (
                            f"Clip {cid} start_state is not clip {previous.clip_id} end_state after strip. "
                            "A paraphrase is a fail."
                        ),
                        cid,
                    )
                )
            incoming = _transition(clip.transition_in)
            outgoing = _transition(previous.transition_out)
            if incoming != outgoing:
                issues.append(
                    BridgeIssue(
                        "transition_mismatch",
                        (
                            f"Clip {cid} transition_in ({clip.transition_in or 'empty'}) "
                            f"does not match clip {previous.clip_id} transition_out "
                            f"({previous.transition_out or 'empty'})."
                        ),
                        cid,
                    )
                )
            if previous.screen_direction.strip() or clip.screen_direction.strip() or lock.screen_direction.strip():
                if _direction(lock, clip) != _direction(lock, previous) and not clip.screen_direction_reversal:
                    issues.append(
                        BridgeIssue(
                            "screen_direction",
                            f"Clip {cid} screen_direction does not inherit clip {previous.clip_id}.",
                            cid,
                        )
                    )
            kind = incoming or outgoing
            if kind in HARD_HANDOFF and previous.end_extracted.strip():
                if clip.start_image.strip() != previous.end_extracted.strip():
                    issues.append(
                        BridgeIssue(
                            "start_image",
                            (
                                f"Clip {cid} start_image must be clip {previous.clip_id} end_extracted "
                                f"for {kind}."
                            ),
                            cid,
                        )
                    )
            if (
                previous.end_extracted.strip()
                and previous.end_designed.strip()
                and clip.start_image.strip() == previous.end_designed.strip()
                and previous.end_designed.strip() != previous.end_extracted.strip()
            ):
                issues.append(
                    BridgeIssue(
                        "designed_as_start",
                        f"Clip {cid} uses the designed end still as the next start while an extract exists.",
                        cid,
                    )
                )
        for label, value in (
            ("transition_in", clip.transition_in),
            ("transition_out", clip.transition_out),
        ):
            token = _transition(value)
            if token not in KNOWN_TRANSITIONS:
                issues.append(
                    BridgeIssue(
                        "transition_unknown",
                        f"Clip {cid} {label} {value} is not in the CLIP_BRIDGE transition library.",
                        cid,
                    )
                )
        start_box = (clip.start_width, clip.start_height)
        end_box = (clip.end_width, clip.end_height)
        if all(part is not None for part in start_box + end_box):
            if start_box != end_box:
                issues.append(
                    BridgeIssue(
                        "still_size",
                        f"Clip {cid} start still size {start_box} does not match end still size {end_box}.",
                        cid,
                    )
                )
            elif start_box != (lock.width, lock.height):
                issues.append(
                    BridgeIssue(
                        "still_size",
                        f"Clip {cid} stills are {start_box[0]}x{start_box[1]}, not the lock canvas.",
                        cid,
                    )
                )
        if clip.start_shot_type.strip() and not _type_line(
            "### Start-frame shot types", clip.start_shot_type, **_shot_slots(lock, clip)
        ):
            issues.append(
                BridgeIssue("shot_type", f"Clip {cid} start_shot_type is not in the CLIP_BRIDGE catalog.", cid)
            )
        if clip.end_shot_type.strip() and not _type_line(
            "### End-frame shot types", clip.end_shot_type, **_shot_slots(lock, clip)
        ):
            issues.append(
                BridgeIssue("shot_type", f"Clip {cid} end_shot_type is not in the CLIP_BRIDGE catalog.", cid)
            )
        h3 = assemble_h3_prompt(lock, clip)
        issues.extend(
            prompt_text_issues(
                h3,
                partial="h3_prompt",
                negative=lock.negative,
                identity=lock.identity,
                start_state=clip.start_state,
                end_state=clip.end_state,
                clip_id=cid,
            )
        )
        end_prompt = assemble_qwen_end(lock, clip)
        issues.extend(
            prompt_text_issues(
                end_prompt,
                partial="qwen_end",
                negative=lock.negative,
                identity=lock.identity,
                start_state=clip.start_state,
                end_state=clip.end_state,
                clip_id=cid,
            )
        )
    return issues


def load_forge_fixture() -> tuple[StoryLock, list[ClipItem]]:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    lock = StoryLock.model_validate(raw["story_lock"])
    clips = [ClipItem.model_validate(item) for item in raw["clips"]]
    return lock, clips


def with_prompts(lock: StoryLock, clip: ClipItem) -> ClipItem:
    return clip.model_copy(
        update={
            "start_frame_prompt": assemble_qwen_start(lock, clip),
            "end_frame_prompt": assemble_qwen_end(lock, clip),
            "h3_prompt": assemble_h3_prompt(lock, clip),
        }
    )


def write_project(root: Path, lock: StoryLock, clips: list[ClipItem]) -> Path:
    """Persist JSON and prompt text. Does not write stills or video."""
    root.mkdir(parents=True, exist_ok=True)
    filled = [with_prompts(lock, clip) for clip in clips]
    (root / "story_lock.json").write_text(
        json.dumps(lock.model_dump(), indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "clips.json").write_text(
        json.dumps([clip.model_dump() for clip in filled], indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "CLIP_BRIDGE.md").write_text(spec_text(), encoding="utf-8")
    for clip in filled:
        folder = root / "clips" / clip.clip_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "meta.json").write_text(json.dumps(clip.model_dump(), indent=2) + "\n", encoding="utf-8")
        (folder / "prompt_qwen_start.txt").write_text(clip.start_frame_prompt, encoding="utf-8")
        (folder / "prompt_qwen_end.txt").write_text(clip.end_frame_prompt, encoding="utf-8")
        (folder / "prompt_h3.txt").write_text(clip.h3_prompt, encoding="utf-8")
    export = root / "export"
    export.mkdir(parents=True, exist_ok=True)
    (export / "concat_list.txt").write_text(concat_list_text([clip.clip_id for clip in filled]), encoding="utf-8")
    (export / "CONFORM.txt").write_text(conform_notes(), encoding="utf-8")
    return root


def concat_list_text(clip_ids: list[str]) -> str:
    lines = [f"file '../clips/{clip_id}/clip_trim.mp4'" for clip_id in clip_ids]
    return "\n".join(lines) + ("\n" if lines else "")


def extract_last_frame_cmd(src: Path, dest: Path) -> list[str]:
    return ["ffmpeg", "-y", "-sseof", "-0.05", "-i", str(src), "-frames:v", "1", "-update", "1", str(dest)]


def trim_held_tail_cmd(src: Path, dest: Path, end_frame: int = TRIM_END_FRAME) -> list[str]:
    return ["ffmpeg", "-y", "-i", str(src), "-vf", f"trim=end_frame={end_frame}", "-an", str(dest)]


def hard_cut_concat_cmd(list_file: Path, dest: Path) -> list[str]:
    return ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(dest)]


def match_xfade_cmd(left: Path, right: Path, dest: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        str(left),
        "-i",
        str(right),
        "-filter_complex",
        "xfade=transition=fade:duration=0.25:offset=9.75",
        str(dest),
    ]


def conform_notes() -> str:
    return (
        "CLIP_BRIDGE conform (docs/CLIP_BRIDGE.md §12).\n"
        "Extract the rendered last frame:\n"
        "ffmpeg -y -sseof -0.05 -i clips/NN/clip.mp4 -frames:v 1 -update 1 clips/NN/end_extracted.png\n"
        "Drop the held last frame before concat (10s × 24fps = 240 frames; drop frame 240):\n"
        'ffmpeg -y -i clips/NN/clip.mp4 -vf "trim=end_frame=239" -an clips/NN/clip_trim.mp4\n'
        "Hard-cut concat:\n"
        "ffmpeg -y -f concat -safe 0 -i export/concat_list.txt -c copy export/story.mp4\n"
        "xfade only when transition_type is T-MATCH:\n"
        'ffmpeg -y -i clips/NN/clip_trim.mp4 -i clips/NNplus1/clip_trim.mp4 '
        '-filter_complex "xfade=transition=fade:duration=0.25:offset=9.75" export/join_tmp.mp4\n'
        "Prefer one continuous score under the picture so room tone does not click.\n"
        "produced_mp4 stays false until every input is a real local video and ffmpeg writes export/story.mp4.\n"
        "called_comfy stays false. This does not call Comfy or start Hermes.\n"
    )


def conform_plan(clips: list[ClipItem]) -> dict[str, Any]:
    extracts = []
    trims = []
    for clip in clips:
        src = clip.video or f"clips/{clip.clip_id}/clip.mp4"
        extracts.append(extract_last_frame_cmd(Path(src), Path(f"clips/{clip.clip_id}/end_extracted.png")))
        trims.append(trim_held_tail_cmd(Path(src), Path(f"clips/{clip.clip_id}/clip_trim.mp4")))
    return {
        "produced_mp4": False,
        "called_comfy": False,
        "hermes_ran": False,
        "episode_completed": False,
        "generate_ok": False,
        "ffmpeg_available": bool(shutil.which("ffmpeg")),
        "extract": extracts,
        "trim": trims,
        "concat_list": concat_list_text([clip.clip_id for clip in clips]),
        "concat": hard_cut_concat_cmd(Path("export/concat_list.txt"), Path("export/story.mp4")),
        "note": conform_notes(),
    }


def _run(cmd: list[str]) -> str | None:
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    if proc.returncode != 0:
        return (proc.stderr or b"").decode("utf-8", errors="replace")[-400:] or "ffmpeg failed"
    return None


def extract_last_frame(src: Path, dest: Path) -> dict[str, Any]:
    """Extract a real last frame. A missing file does not invent a PNG."""
    if not src.is_file():
        return {
            "ok": False,
            "produced": False,
            "produced_mp4": False,
            "called_comfy": False,
            "reason": f"No rendered clip at {src}. Awaiting extract. No frame was invented.",
        }
    if not shutil.which("ffmpeg"):
        return {
            "ok": False,
            "produced": False,
            "produced_mp4": False,
            "called_comfy": False,
            "reason": "ffmpeg is not on PATH. Awaiting extract. No frame was invented.",
        }
    dest.parent.mkdir(parents=True, exist_ok=True)
    error = _run(extract_last_frame_cmd(src, dest))
    if error or not dest.is_file() or dest.stat().st_size <= 0:
        if dest.exists():
            dest.unlink()
        return {
            "ok": False,
            "produced": False,
            "produced_mp4": False,
            "called_comfy": False,
            "reason": error or "ffmpeg did not write a frame. No frame was invented.",
        }
    return {
        "ok": True,
        "produced": True,
        "produced_mp4": False,
        "called_comfy": False,
        "path": str(dest),
    }


def trim_held_tail(src: Path, dest: Path) -> dict[str, Any]:
    if not src.is_file():
        return {
            "ok": False,
            "produced_mp4": False,
            "called_comfy": False,
            "reason": f"No rendered clip at {src}. Awaiting trim. No MP4 was invented.",
        }
    if not shutil.which("ffmpeg"):
        return {
            "ok": False,
            "produced_mp4": False,
            "called_comfy": False,
            "reason": "ffmpeg is not on PATH. Awaiting trim. No MP4 was invented.",
        }
    dest.parent.mkdir(parents=True, exist_ok=True)
    error = _run(trim_held_tail_cmd(src, dest))
    if error or not dest.is_file() or dest.stat().st_size <= 0:
        if dest.exists():
            dest.unlink()
        return {
            "ok": False,
            "produced_mp4": False,
            "called_comfy": False,
            "reason": error or "ffmpeg did not write a trim. No MP4 was invented.",
        }
    return {
        "ok": True,
        "produced_mp4": False,
        "called_comfy": False,
        "path": str(dest),
        "claim": "Trimmed held tail of an existing video. Not a story export and not a Comfy render.",
    }


def conform_execute(root: Path, clips: list[ClipItem]) -> dict[str, Any]:
    """Concat only when every clip video exists. Otherwise leave the run awaiting conform."""
    plan = conform_plan(clips)
    missing = []
    sources: list[Path] = []
    for clip in clips:
        relative = clip.video or f"clips/{clip.clip_id}/clip.mp4"
        path = root / relative
        sources.append(path)
        if not path.is_file():
            missing.append(clip.clip_id)
    if missing:
        plan["reason"] = (
            "Clip inputs are not local video files ("
            + ", ".join(missing)
            + "). Awaiting conform. No MP4 was invented."
        )
        plan["produced_mp4"] = False
        return plan
    if not shutil.which("ffmpeg"):
        plan["reason"] = "ffmpeg is not on PATH. Awaiting conform. No MP4 was invented."
        plan["produced_mp4"] = False
        return plan
    export = root / "export"
    export.mkdir(parents=True, exist_ok=True)
    for clip, src in zip(clips, sources, strict=True):
        extracted = extract_last_frame(src, root / "clips" / clip.clip_id / "end_extracted.png")
        if not extracted["ok"]:
            plan["reason"] = extracted["reason"]
            plan["produced_mp4"] = False
            return plan
        trimmed = trim_held_tail(src, root / "clips" / clip.clip_id / "clip_trim.mp4")
        if not trimmed["ok"]:
            plan["reason"] = trimmed["reason"]
            plan["produced_mp4"] = False
            return plan
    list_file = export / "concat_list.txt"
    list_file.write_text(concat_list_text([clip.clip_id for clip in clips]), encoding="utf-8")
    # The concat list uses paths relative to export/, matching §12.
    story = export / "story.mp4"
    error = _run(hard_cut_concat_cmd(list_file, story))
    if error or not story.is_file() or story.stat().st_size <= 0:
        if story.exists():
            story.unlink()
        plan["produced_mp4"] = False
        plan["reason"] = error or "ffmpeg did not write story.mp4. No MP4 was invented."
        return plan
    plan["produced_mp4"] = True
    plan["path"] = str(story)
    plan["called_comfy"] = False
    plan["episode_completed"] = False
    plan["generate_ok"] = False
    plan["claim"] = "Local ffmpeg hard-cut of existing clip files. Not a Comfy render. Not CapCut."
    return plan


def clip_from_bridge(data: dict[str, Any]) -> ClipItem:
    payload = {key: value for key, value in data.items() if key != "dialect"}
    return ClipItem.model_validate(payload)


def bridge_payload(clip: ClipItem) -> dict[str, Any]:
    return {"dialect": DIALECT, **clip.model_dump()}


def project_dir(episode_id: str) -> Path:
    return get_settings().media_path / episode_id / "clip-bridge"


def _camera_label(camera_move: str) -> str:
    lowered = camera_move.lower()
    for token in ("push", "pull", "track", "truck", "arc", "tilt", "pedestal", "follow", "hold", "handheld"):
        if token in lowered:
            return token
    return "move"


def bridge_rows(episode: Episode) -> list[Shot]:
    rows = []
    for shot in episode.shots:
        data = shot.bridge if isinstance(shot.bridge, dict) else {}
        if data.get("dialect") == DIALECT:
            rows.append(shot)
    rows.sort(key=lambda shot: (shot.sort_index, str((shot.bridge or {}).get("clip_id") or ""), shot.id))
    return rows


def clips_on(episode: Episode) -> list[ClipItem]:
    return [clip_from_bridge(shot.bridge) for shot in bridge_rows(episode)]


def apply_bridge(
    db: Session,
    episode: Episode,
    lock: StoryLock,
    clips: list[ClipItem],
    *,
    replace: bool = True,
) -> dict[str, Any]:
    """Store the lock and clip rows. Does not call Comfy."""
    issues = preflight(lock, clips)
    episode.story_lock = lock.model_dump()
    flag_modified(episode, "story_lock")
    if replace:
        for shot in list(episode.shots):
            data = shot.bridge if isinstance(shot.bridge, dict) else {}
            if data.get("dialect") == DIALECT:
                db.delete(shot)
        db.flush()
    shots: list[Shot] = []
    filled: list[ClipItem] = []
    for index, clip in enumerate(clips):
        stored = with_prompts(lock, clip)
        filled.append(stored)
        shot = Shot(
            episode_id=episode.id,
            edit_row_id=f"cb-{stored.clip_id}"[:80],
            sort_index=index,
            song_t="10.00",
            join=(stored.transition_out or "")[:20],
            take="A",
            location_grade=(stored.location or "")[:200],
            camera_verb=_camera_label(stored.camera_move)[:40],
            action=stored.action,
            readiness="draft",
            bridge=bridge_payload(stored),
        )
        db.add(shot)
        shots.append(shot)
    db.flush()
    write_project(project_dir(episode.id), lock, filled)
    return {"issues": issues, "shots": shots, "clips": filled}


def retry_clip(db: Session, episode: Episode, clip_id: str) -> dict[str, Any]:
    """Reassemble one clip's prompts. Does not rewrite the lock or any clip's states."""
    if not isinstance(episode.story_lock, dict) or not episode.story_lock.get("project_id"):
        raise KeyError("story_lock")
    lock_before = json.dumps(episode.story_lock, sort_keys=True)
    rows = bridge_rows(episode)
    states_before = {
        str(shot.bridge.get("clip_id")): (
            shot.bridge.get("start_state"),
            shot.bridge.get("end_state"),
        )
        for shot in rows
    }
    target = next((shot for shot in rows if str(shot.bridge.get("clip_id")) == clip_id), None)
    if target is None:
        raise KeyError(clip_id)
    lock = StoryLock.model_validate(episode.story_lock)
    refreshed = with_prompts(lock, clip_from_bridge(target.bridge))
    target.bridge = bridge_payload(refreshed)
    flag_modified(target, "bridge")
    db.flush()
    episode.story_lock = json.loads(lock_before)
    flag_modified(episode, "story_lock")
    write_project(project_dir(episode.id), lock, clips_on(episode))
    return {
        "lock_before": lock_before,
        "states_before": states_before,
        "clip": refreshed,
        "shot": target,
    }


def _partial_for(job_type: str, payload: dict[str, Any]) -> str:
    asked = str(payload.get("qwen_partial") or payload.get("clip_partial") or "").strip().upper()
    mapping = {
        "Q1": "qwen_q1",
        "Q2": "qwen_start",
        "Q3": "qwen_end",
        "Q4": "qwen_q4",
        "Q5": "qwen_q5",
        "Q6": "qwen_q6",
        "H0": "h3_prompt",
    }
    if asked in mapping:
        return mapping[asked]
    if job_type in {"clip-hop1", "clip-extend"}:
        return "h3_prompt"
    if job_type == "still-plate":
        return "qwen_end"
    return "qwen_start"


def _issues_for(issues: list[BridgeIssue], clip_id: str) -> list[BridgeIssue]:
    kept: list[BridgeIssue] = []
    for issue in issues:
        if not issue.clip_id or issue.clip_id == clip_id:
            kept.append(issue)
    return kept


def preview_bundle(episode: Any, shot: Any, job_type: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Assemble the exact H3/Qwen strings for a shot that carries a clip bridge."""
    body = payload if isinstance(payload, dict) else {}
    lock_raw = body.get("story_lock") if isinstance(body.get("story_lock"), dict) else None
    if lock_raw is None:
        stored = getattr(episode, "story_lock", None)
        if isinstance(stored, dict) and stored.get("project_id"):
            lock_raw = stored
    if not isinstance(lock_raw, dict):
        return None
    clip_raw = body.get("clip") if isinstance(body.get("clip"), dict) else None
    clips_raw = body.get("clips") if isinstance(body.get("clips"), list) else None
    if clip_raw is None and shot is not None:
        bridge = getattr(shot, "bridge", None)
        if isinstance(bridge, dict) and bridge.get("dialect") == DIALECT:
            clip_raw = bridge
    if clip_raw is None:
        return None
    try:
        lock = StoryLock.model_validate(lock_raw)
        clip = clip_from_bridge(clip_raw)
    except Exception:
        return None
    sequence: list[ClipItem]
    if clips_raw is not None:
        try:
            sequence = [clip_from_bridge(item) if isinstance(item, dict) else clip for item in clips_raw]
        except Exception:
            sequence = [clip]
    else:
        rows = []
        for row in getattr(episode, "shots", []) or []:
            data = getattr(row, "bridge", None)
            if isinstance(data, dict) and data.get("dialect") == DIALECT:
                rows.append(row)
        rows.sort(key=lambda row: (row.sort_index, str((row.bridge or {}).get("clip_id") or "")))
        try:
            sequence = [clip_from_bridge(row.bridge) for row in rows] or [clip]
        except Exception:
            sequence = [clip]
        if not any(item.clip_id == clip.clip_id for item in sequence):
            sequence.append(clip)
    issues = _issues_for(preflight(lock, sequence), clip.clip_id)
    prompts = {
        "qwen_q1": assemble_qwen_q1(lock),
        "qwen_start": assemble_qwen_start(lock, clip),
        "qwen_end": assemble_qwen_end(lock, clip),
        "qwen_q4": assemble_qwen_q4(lock, clip),
        "qwen_q5": assemble_qwen_q5(lock, clip),
        "qwen_q6": assemble_qwen_q6(lock, clip),
        "h3_prompt": assemble_h3_prompt(lock, clip),
    }
    partial = _partial_for(job_type, body)
    prompt = prompts[partial]
    text_issues = prompt_text_issues(
        prompt,
        partial=partial,
        negative=lock.negative,
        identity=lock.identity,
        start_state=clip.start_state,
        end_state=clip.end_state,
        clip_id=clip.clip_id,
    )
    # Preflight already checked assembled H3 and Q3. Keep edited-prompt checks for the selected partial
    # when it is not those two, and always surface them if they are new.
    seen = {(issue.code, issue.message) for issue in issues}
    for issue in text_issues:
        if (issue.code, issue.message) not in seen:
            issues.append(issue)
    warning = " ".join(issue.message for issue in issues)
    bundle = {
        "dialect": DIALECT,
        "partial": partial,
        "h3_prompt": prompts["h3_prompt"],
        "qwen_q1": prompts["qwen_q1"],
        "qwen_start": prompts["qwen_start"],
        "qwen_end": prompts["qwen_end"],
        "qwen_q4": prompts["qwen_q4"],
        "qwen_q5": prompts["qwen_q5"],
        "qwen_q6": prompts["qwen_q6"],
        "visual_lock": visual_lock_block(lock),
        "negative_lock": lock.negative.strip(),
        "alignment": alignment_line(),
        "start_state": clip.start_state.strip(),
        "end_state": clip.end_state.strip(),
        "identity": lock.identity.strip(),
        "issues": [issue.as_dict() for issue in issues],
        "ok": not issues,
        "called_comfy": False,
        "produced_mp4": False,
        "live_render": False,
        "honesty": (
            "CLIP_BRIDGE preview. Slots filled from the lock and the clip. "
            "Nothing was queued. Stub stays a fixture. called_comfy stays false "
            "until a live lane accepts a prompt."
        ),
    }
    return {
        "prompt": prompt,
        "negative": lock.negative.strip(),
        "clip_bridge": bundle,
        "issues": [issue.as_dict() for issue in issues],
        "warning": warning,
    }


def recheck_draft(body: dict[str, Any]) -> None:
    """Re-validate an edited preview against the locked strings. Does not paraphrase them back."""
    bridge = body.get("clip_bridge")
    if not isinstance(bridge, dict):
        return
    structural = [
        issue
        for issue in bridge.get("issues") or []
        if isinstance(issue, dict) and issue.get("code") not in PROMPT_ISSUE_CODES
    ]
    partial = str(bridge.get("partial") or "")
    text_issues = prompt_text_issues(
        str(body.get("prompt") or ""),
        partial=partial,
        negative=str(bridge.get("negative_lock") or ""),
        identity=str(bridge.get("identity") or ""),
        start_state=str(bridge.get("start_state") or ""),
        end_state=str(bridge.get("end_state") or ""),
        clip_id="",
    )
    issues = structural + [issue.as_dict() for issue in text_issues]
    bridge = dict(bridge)
    bridge["issues"] = issues
    bridge["ok"] = not issues
    bridge["called_comfy"] = False
    bridge["produced_mp4"] = False
    body["clip_bridge"] = bridge
    if issues:
        body["generate_enabled"] = False
        body["warning"] = " ".join(str(issue.get("message") or "") for issue in issues if issue.get("message"))
