# CLIP_BRIDGE.md
## Builder spec for a Hermes application that produces long-form video from 10-second visually consistent clips

Hand this file to the builder bot as the source of truth. Implement the application from this document. Do not invent a competing prompt dialect. Do not paraphrase locked continuity strings.

---

## 0. Mission

Build an application, orchestrated by Hermes AI, that:

1. Plans a long-form video as a sequence of 10.00-second clips.
2. Uses **Qwen Image 2.1** (ComfyUI) to generate a START still and an END still for each clip.
3. Uses **MiniMax H3** first-and-last-frame-to-video (FL2VA) to animate the 10s between those stills.
4. Extracts the **rendered** last frame of clip N and uses it as the first frame of clip N+1.
5. Stitches the clips into one story with hard cuts.
6. Generates beginning and ending prompts for every clip so scenes move seamlessly.

Success is not “nice clips.” Success is: clip N’s last frames and clip N+1’s first frames are visually continuous enough that a hard cut does not pop.

---

## 1. Stack — do not substitute

| Role | Tool | Job |
|---|---|---|
| Orchestrator | Hermes AI | Story beats, lock tokens, prompt fill, continuity enforcement, job graph |
| Keyframe factory | Qwen Image 2.1 in ComfyUI (v0.37+) | START and END stills. Gen + instruction edit. Refs as `<image1>`…`<imageN>` |
| Motion | MiniMax H3 FL2VA | 10.00s clip from first frame + last frame + motion prompt. 2K, 24fps, native stereo |
| Conform | ffmpeg | Extract last frame, drop held tail frame, concat, optional audio acrossfade |

Constraints the builder must encode as validation, not comments:

- Clip duration is **10.00** seconds. Not 8. Not 12. Alignment line must say `10.00`.
- Output canvas: **16:9, 2560×1440, 24fps** unless the story lock overrides aspect. Then every still and every clip uses that same size.
- First frame and last frame of a clip **must be identical pixel size and aspect**. Mismatch stretches the subject.
- H3 image limits: each side 256–5760 px, aspect between 2:5 and 5:2.
- H3 does **not** crossfade. It invents a physical path. Frames must share composition and differ in **one** thing.
- Qwen edit prompts are short imperatives. Never re-describe a face when a reference image is attached.
- One primary action + one camera move per clip. Reject prompts that stack opposing camera moves or more than one transformation.

---

## 2. Architecture

```
STORY_LOCK (once)
    │
    ├─ Qwen Q1: character sheet + optional location plates
    │
    ▼
for clip in clips:
    START_IMAGE
        clip 1: Qwen from lock
        clip N>1: RENDERED last frame of clip N-1
                 (optional Qwen Q2 edit only if the designed start
                  must advance off the extracted frame)
    END_IMAGE
        Qwen Q3 from identity + this clip’s START_IMAGE
    H3 FL2VA
        Picture 1 = START_IMAGE
        Picture 2 = END_IMAGE
        prompt    = H0 wrapper filled from clip object
    EXTRACT
        ffmpeg last frame of the RENDER → clipN_last.png
    HANDOFF
        clipN_last.png becomes clip N+1 START_IMAGE
        END_STATE string of clip N is copied VERBATIM into
        START_STATE string of clip N+1
    │
    ▼
CONFORM: trim held tail frames → concat demuxer → optional audio acrossfade
```

Beat map the cinematographer must write into every H3 prompt:

- 0.00–1.00s  hold Picture 1
- 1.00–8.00s  one action + one camera idea
- 8.00–10.00s settle onto Picture 2 and hold

---

## 3. Agents Hermes must run

Do not collapse these into one mega-prompt. Separate tools / sub-agents.

### Director
Input: user story, duration target, optional style refs.
Output: `story_lock.json` + `clips.json` (list of clip objects with START_STATE / END_STATE / action / camera / transition_type filled).
Rule: each clip has exactly one verb from the verb bank and exactly one camera move.

### Keyframe artist
Input: story lock images + clip object + previous last frame.
Output: `clipNN_start.png`, `clipNN_end.png` via Qwen 2.1.
Rule: same pixel size as the project canvas. Frozen stills, no motion blur, no text.

### Cinematographer
Input: clip object + start/end stills.
Output: filled H3 FL2VA prompt (alignment line + four-beat path + soundscape).
Rule: prompt describes MOTION only. Do not re-describe the stills.

### Continuity editor
Input: clip N object + clip N+1 object + extracted last frame.
Output: pass / reject + patched clip N+1 START_STATE.
Hard rules:
- `clips[n+1].start_state == clips[n].end_state` as strings. Byte-identical after trim.
- `clips[n+1].start_image` is the extracted last frame of clip N, not a newly imagined still, unless transition_type is T-MATCH, T-EXIT-ENTER, or T-OCCLUSION and a designed handoff still is required.
- Reject if identity tokens, wardrobe, screen_direction, or lighting_bible changed.
- Paraphrase of the handoff sentence is a fail.

### Conform
Input: rendered clips.
Output: `story.mp4`.
Rule: hard cut. Drop last frame of each clip before concat. Dissolve only when transition_type is T-MATCH and the worlds actually change.

---

## 4. Data schemas

Persist these as JSON next to the media. The builder must validate against this shape.

### story_lock.json

```json
{
  "project_id": "forge_dawn_01",
  "aspect": "16:9",
  "width": 2560,
  "height": 1440,
  "fps": 24,
  "duration_s": 10.00,
  "lens": "spherical 35mm look, eye-level unless noted",
  "style": "photoreal cinematic, live-action",
  "identity": "weathered male bladesmith, late 50s, grey-streaked beard, lined eyes, olive-tan skin, lean forearms",
  "wardrobe": "dark leather apron over rolled natural-linen sleeves, soot-stained canvas trousers, scuffed brown boots",
  "palette": "coal-orange, forge-soot black, warm brass, cool moonlight cyan",
  "lighting_bible": "single warm key from forge-right at 45 degrees, soft cool fill from the open bay door camera-left",
  "screen_direction": "left-to-right",
  "negative": "no face morph, no age drift, no wardrobe change, no extra people, no text, no logos, no watermarks, no jump cuts, no dissolves inside the clip, no lens change, no teleporting, no sudden weather swap, no extra bloom, no handheld shake unless requested, no cut, no shot change",
  "character_sheet": "assets/lock/character_sheet.png",
  "wardrobe_sheet": "assets/lock/wardrobe.png",
  "location_plates": ["assets/lock/forge.png", "assets/lock/yard.png", "assets/lock/ridge.png"]
}
```

### clips.json item

```json
{
  "clip_id": "03",
  "purpose": "threshold",
  "location": "open bay door looking onto gravel yard",
  "time_of_day": "blue hour into first light",
  "start_state": "he is looking toward the open bay door, blade on the anvil cooling, hammer lowered",
  "end_state": "he stands in the open doorway, dawn behind him, clean silhouette, blade sheathed at his hip",
  "action": "crosses-threshold",
  "action_beats": ["walks to the door", "puts his left hand on the edge", "pulls it wider as dawn floods in"],
  "camera_start": "medium-wide, eye-level, 35mm",
  "camera_end": "medium-wide, same height, subject in doorway",
  "camera_move": "The camera follows at constant distance, subject screen-center.",
  "screen_direction": "left-to-right",
  "prop_state_start": "finished blade resting on the anvil, hammer down",
  "prop_state_end": "blade sheathed at the hip",
  "transition_in": "T-LOOK-OFF",
  "transition_out": "T-MATCH",
  "start_image": "clips/03/start.png",
  "end_designed": "clips/03/end_designed.png",
  "end_extracted": "clips/03/end_extracted.png",
  "video": "clips/03/clip.mp4",
  "status": "planned | keyframes_ready | rendered | extracted | rejected",
  "soundscape": "boot on stone, hinge creak, dying forge hiss receding, distant birds",
  "music": "N/A",
  "start_frame_prompt": "",
  "end_frame_prompt": "",
  "h3_prompt": ""
}
```

### Continuity invariant the app must enforce

```
clips[n+1].start_state        == clips[n].end_state
clips[n+1].start_image        == clips[n].end_extracted          (for T-HARD, T-POSE, T-CAMERA, T-LIGHT, T-PROP, T-LOOK-OFF)
clips[n+1].screen_direction   == clips[n].screen_direction       (unless Director marked a reversal)
clips[n+1].wardrobe           inherits story_lock.wardrobe
clips[n+1].identity           inherits story_lock.identity
```

Builder: store `start_state` / `end_state` as canonical strings. Continuity editor compares them with `strip()` only. No fuzzy match. No LLM rewrite of a passing handoff.

---

## 5. File layout the app should write

```
project/
  CLIP_BRIDGE.md
  story_lock.json
  clips.json
  assets/lock/
    character_sheet.png
    wardrobe.png
    location_*.png
  clips/
    01/
      meta.json
      prompt_qwen_start.txt
      prompt_qwen_end.txt
      prompt_h3.txt
      start.png
      end_designed.png
      clip.mp4
      end_extracted.png
      clip_trim.mp4
    02/
      ...
  export/
    concat_list.txt
    story.mp4
```

`end_designed.png` is the Qwen target. `end_extracted.png` is the stitch source. Never use the designed still as the next start if the extract exists.

---

## 6. Visual lock text (inject into every Qwen still and every H3 clip)

```
[VISUAL LOCK]
Same person throughout: {identity}.
Same body proportions. Same wardrobe: {wardrobe}.
Color script: {palette}.
Lighting bible: {lighting_bible}.
Lens: {lens}, {aspect} {width}x{height}, photoreal cinematic, {fps}fps.
No face drift, no wardrobe mutation, no extra people, no text, no logos, no watermark.

[NEGATIVE LOCK]
{negative}
```

---

## 7. Qwen Image 2.1 prompt partials

Use the ComfyUI Image Edit workflow. Address refs as `<image1>` … `<imageN>`.

- `<image1>` = character sheet (identity lock)
- `<image2>` = previous last frame OR this clip’s start frame
- `<image3>` = location plate when the set must hold
- `<image4>` = wardrobe sheet if wardrobe is not already in `<image1>`

### Q1 — character sheet seed (once per project)

```
Photoreal character sheet of {identity}, {wardrobe},
three-quarter portrait plus a three-quarter back view,
even studio key from camera-left, clean background,
identity plate for later reference, {aspect}, native 2K.
```

### Q2 — start frame from identity + previous end

```
Using <image1> as identity lock and <image2> as the previous clip’s last frame:
generate the OPENING still of clip {clip_id}.
Keep face, wardrobe, body, palette, and lighting direction from the lock.
Change only: {start_state}, {location}, {camera_start}, {prop_state_start}.
Same screen direction {screen_direction}.
If transition_in is T-HARD, this frame must match <image2>.
Photoreal cinematic still, not a video. No motion blur. No text.
Same pixel size as <image2>: {width}x{height}.
```

### Q3 — end frame from this clip’s start

```
Using <image1> as identity and <image2> as THIS clip’s start frame:
generate the CLOSING still.
Same person, wardrobe, location, time of day, lighting direction.
Change only pose, prop, and camera to: {end_state}, {prop_state_end}, {camera_end}.
End pose is a stable hold, not mid-blur.
Composition must be reusable as the next clip’s first frame.
Photoreal cinematic still, not a video. No motion blur. No text.
Same pixel size and aspect as <image2>: {width}x{height}.
```

### Q4 — designed handoff end frame

```
From <image2> start frame, create a closing still that {handoff_action}.
Allowed handoff_action values:
walks through a doorway / turns into silhouette / object fills the frame /
looks off-screen {screen_direction} / reaches toward camera.
Hold a clean readable composition for the next scene’s entry.
Keep identity and wardrobe from <image1>. Same pixel size {width}x{height}.
```

### Q5 — match-cut pair

```
Generate two stills that share silhouette, camera axis, and motion vector
but change location from {loc_a} to {loc_b}.
Image A = clip N end. Image B = clip N+1 start.
Same identity, same framing size, same facing direction, same lens height.
Keep face and wardrobe identical. {width}x{height}, {aspect}.
```

### Q6 — lighting / weather shift (time lives INSIDE one clip)

```
Keep identity and location from <image2>.
Shift only time or weather to {new_time}.
Preserve identity, wardrobe, pose, and camera.
This becomes the end frame of a time-lapse clip.
Do not jump time at a stitch point.
```

### Qwen micro-partials (append as needed)

```
Keep everything else unchanged.
Keep facial features identical.
Do not copy the posture of the reference; only keep appearance.
Same {aspect} framing and pixel size.
Photoreal cinematic still, not a video, not an illustration.
```

### Start-frame shot types (Director picks one)

```
S-ESTABLISH     Wide establishing still, subject small, location readable, idle pose ready to move.
S-PORTRAIT      Medium close-up, eyes sharp, wardrobe readable, catchlight matches lighting_bible.
S-OVER-SHOULDER Over-shoulder looking {screen_direction} at {target}. Subject one third, target two thirds.
S-INSERT        Tight insert of {prop} in hands / on anvil / on table.
S-THRESHOLD     Subject paused in a doorway / gate / treeline, half old space half new.
S-MOTION-READY  Weight already shifted into the coming action so H3 does not invent the start of motion.
```

### End-frame shot types (Director picks one)

```
E-HOLD        Stable terminal pose, feet planted, face visible, prop settled. Default next-start.
E-EXIT        Subject crosses out {screen_direction} until mostly gone.
E-REVEAL      Reveal completes; new object or space is open; hold.
E-TURN        45–90 degree turn toward {next_location}, eyeline aimed at next scene.
E-CONTACT     Tool or hand just made contact, then a settle so it is not a blurry stitch frame.
E-SILHOUETTE  Clean silhouette against sky / fire / doorlight. Match-cut candidate.
E-FILL        Foreground object or body fills >80% of frame. Next clip begins as it recedes.
```

---

## 8. MiniMax H3 FL2VA prompt partials

### H0 — wrapper. Use this exact alignment line. Then one blank line.

```
How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the 10.00-second mark of the target video.

integrated_multimodal_description: [Shot 1] {style}. Begin exactly from Picture 1. {VISUAL_LOCK}. {start_state_clause}. The camera {camera_move} as {action_path}. Toward the end of the shot the differences narrow until {end_state_clause}, landing on the exact pose, spacing, and composition established by Picture 2 at the 10.00-second mark. One continuous uncut shot. Keep identity, wardrobe, and lighting recipe locked.

overall_soundscape: {soundscape}
non_diegetic_music: {music}
```

Four-beat path H3 follows. Cinematographer must write in this order:

1. first-frame state
2. observable intermediate changes
3. differences narrow
4. last-frame state

Do not re-describe the two stills. Prompt the motion between them. One shot. No “cut to.”

### H1 — start-state clause

```
Opening: {identity short} is {start_state} in {location}, {time_of_day}.
Wardrobe {wardrobe}. Prop state: {prop_state_start}.
Camera is {camera_start}. Lighting: {lighting_bible}.
Hold this composition for the first second.
```

### H2 — end-state clause

```
Closing hold: subject arrives at {end_state},
prop now {prop_state_end}, camera now {camera_end}.
Settle and freeze on Picture 2 from 8.5s to 10.00s
so the last frames are stitch-clean.
```

### H3 — action path

```
Primary action only: {action}.
Intermediate beats: {beat1}, then {beat2}, then {beat3}.
Physically plausible. No teleport.
Screen direction stays {screen_direction}.
```

### Camera bank — pick ONE per clip

Write motion as English, not tags. Type + amplitude + speed.

```
The camera holds static.
The camera pushes in with small amplitude at slow speed.
The camera pulls back with small amplitude at slow speed.
The camera tracks left-to-right, holding torso framing.
The camera trucks laterally, matching the walk, constant distance.
The camera arcs 30 degrees camera-right at slow speed.
The camera pedestals up with small amplitude as the subject stands.
The camera tilts up from the hands to the face at slow speed.
The camera follows at constant distance, subject screen-center.
Handheld micro-breathe only, no whip pan.
```

Reject any clip that lists two opposing moves.

### Verb bank — pick ONE per clip

```
walks, turns, raises, lowers, strikes, sheathes, unsheathes,
opens, closes, hands-off, picks-up, looks-up, sits, stands,
crosses-threshold, mounts, dismounts, kindles, quenches,
wipes-brow, exhales
```

---

## 9. Transition library

Director assigns `transition_out` on clip N and `transition_in` on clip N+1. They must agree.

### T-HARD (default)
End frame of clip N **is** the start frame of clip N+1. Do not regenerate.
Next clip H3 opener: `Begin exactly from the previous clip’s final frame. Do not reframe.`

### T-POSE
`Continue from the exact pose, eyeline, and footing of Picture 1. No reset. Motion begins already in progress.`

### T-CAMERA
`Camera inherits the exact lens height, angle, and distance of Picture 1 and continues the same move without a cut.`

### T-LIGHT
`Key light remains {direction_and_color}. If light evolves, it changes continuously rather than jumping. Time jumps belong inside a clip (Q6), not at the stitch.`

### T-MATCH
`Match on action and silhouette. The gesture that completes in clip N begins clip N+1 in a new space. Keep screen direction. Do not change costume. Shared axis, shared facing, shared lens.`

### T-EXIT-ENTER
Clip N end: subject walks `{screen_direction}` out of frame or through a threshold until the frame is empty or occluded.
Clip N+1 start: subject enters from the opposite edge into `{new_location}`, same pace, same facing.

### T-OCCLUSION
Clip N end: `{door | cloak | smoke | hammer | steam}` moves toward lens until it fills the frame.
Clip N+1 start: the same object pulls away to reveal `{new_location}`.

### T-LOOK-OFF
Clip N end: subject looks `{screen_direction}` off-screen, then holds.
Clip N+1 start: camera is already looking at what they saw, or the subject is mid-turn into the new space.

### T-PROP
`The {object} remains in the same hand, at the same height, same orientation. Do not reset grip.`

---

## 10. Negative lock — append to every H3 prompt

```
No face morph, no age drift, no wardrobe change, no extra people,
no text, no logos, no watermarks, no jump cuts, no dissolves inside the clip,
no lens change, no teleporting, no sudden weather swap,
no extra bloom, no handheld shake unless requested,
no cut, no shot change, one continuous shot only.
```

---

## 11. Hermes generation loop (implement this)

```
1. Create project folder + empty clips.json.
2. Director writes story_lock.json and the clip list.
   Validate: one verb each, one camera each, END_N == START_N+1 strings.
3. Keyframe artist runs Q1 once. Save character sheet into assets/lock/.
4. For clip 1:
     Qwen start still from lock (or Q2 if a location plate exists).
     Qwen end still with Q3.
     Cinematographer fills H0.
     H3 FL2VA 10.00s, 2K, first=start, last=end.
     Conform extracts last frame → clips/01/end_extracted.png
5. For clip N>1:
     Continuity editor copies END_STATE of N-1 into START_STATE of N.
     START image = clips/{N-1}/end_extracted.png
     If transition_in in {T-MATCH, T-EXIT-ENTER, T-OCCLUSION}:
         Keyframe artist may Qwen-edit the extracted frame with Q4/Q5.
         Otherwise do not regenerate the start still.
     Qwen end still with Q3.
     Cinematographer fills H0.
     H3 FL2VA.
     Extract last frame.
6. Continuity editor diffs lock tokens + start/end strings. Reject and regenerate
   only the failing clip. Never rewrite the story lock to hide drift.
7. Conform trims + concats. Write story.mp4.
```

---

## 12. ffmpeg conform

Extract the real last frame after each H3 render:

```bash
ffmpeg -y -sseof -0.05 -i clips/NN/clip.mp4 -frames:v 1 -update 1 clips/NN/end_extracted.png
```

Drop the held last frame before concat (10s × 24fps = 240 frames; drop frame 240):

```bash
ffmpeg -y -i clips/NN/clip.mp4 -vf "trim=end_frame=239" -an clips/NN/clip_trim.mp4
```

Concat list (`export/concat_list.txt`):

```
file '../clips/01/clip_trim.mp4'
file '../clips/02/clip_trim.mp4'
file '../clips/03/clip_trim.mp4'
```

Hard-cut concat:

```bash
ffmpeg -y -f concat -safe 0 -i export/concat_list.txt -c copy export/story.mp4
```

If a join pops, trim 2–3 more tail frames of clip N. Do not dissolve unless transition_type is T-MATCH or an intentional world change:

```bash
ffmpeg -y -i clips/NN/clip_trim.mp4 -i clips/NNplus1/clip_trim.mp4 \
  -filter_complex "xfade=transition=fade:duration=0.25:offset=9.75" \
  export/join_tmp.mp4
```

Audio: H3 writes native stereo per clip. Room-tone clicks at joins. Either:

```bash
# acrossfade 0.2s on the audio bed after visual concat, or
# replace the per-clip audio with one continuous score
```

Prefer one continuous score under the picture so room tone does not click.

---

## 13. Worked 6-clip sequence (reference implementation of the handoff rule)

Use this as the fixture for tests. Swap nouns later. Do not lose the copy-paste chain.

**story_lock.identity**
weathered male bladesmith, late 50s, grey-streaked beard, lined eyes, olive-tan skin, lean forearms

**wardrobe**
dark leather apron over rolled natural-linen sleeves, soot-stained canvas trousers, scuffed brown boots

**palette / lighting / camera**
coal-orange, forge-soot black, warm brass, cool moonlight cyan.
single warm key from forge-right at 45 degrees, soft cool fill from the open bay door camera-left.
spherical 35mm, eye-level, 16:9 2560×1440, 24fps.
screen_direction: left-to-right.

### Clip 01 — approach the anvil
- purpose: raise
- start_state: `he stands idle at the dark forge mouth, hammer hanging at his right side, eyeline on the cold anvil`
- end_state: `the hammer is at apex above a glowing billet on the anvil, his weight loaded on the back foot, eyeline on the steel`
- action: raises
- camera_move: `The camera pushes in with small amplitude at slow speed.`
- transition_out: T-HARD
- soundscape: `boot on packed earth, faint bellows, coal tick`

### Clip 02 — three strikes and look-off
- start_state: `the hammer is at apex above a glowing billet on the anvil, his weight loaded on the back foot, eyeline on the steel`
- end_state: `the blade rests on the anvil cooling from orange to dull red, hammer lowered, he has turned his head toward the open bay door`
- action: strikes
- camera_move: `The camera holds static.`
- transition_out: T-LOOK-OFF
- soundscape: `three hammer strikes on steel, quench hiss, fire pop`

### Clip 03 — threshold
- start_state: `the blade rests on the anvil cooling from orange to dull red, hammer lowered, he has turned his head toward the open bay door`
- end_state: `he stands in the open doorway, dawn behind him, clean silhouette, blade sheathed at his hip`
- action: crosses-threshold
- camera_move: `The camera follows at constant distance, subject screen-center.`
- transition_out: T-MATCH
- soundscape: `boot on stone, hinge creak, dying forge hiss receding, distant birds`

### Clip 04 — into the yard
- start_state: `he stands in the open doorway, dawn behind him, clean silhouette, blade sheathed at his hip`
- end_state: `he is fully outside, door ajar behind him with warm spill, facing down the gravel path, blade sheathed at his hip`
- action: walks
- camera_move: `The camera pulls back with small amplitude at slow speed.`
- transition_out: T-HARD
- soundscape: `gravel under boots, hinge settling, night insects taking over the fire`

### Clip 05 — the path
- start_state: `he is fully outside, door ajar behind him with warm spill, facing down the gravel path, blade sheathed at his hip`
- end_state: `he has stopped at the ridge, three-quarter back view, looking out over the dark valley, right hand on the pommel, moonlight now the key light`
- action: walks
- camera_move: `The camera tracks left-to-right, holding torso framing.`
- transition_out: T-HARD
- soundscape: `gravel under boots, wind in pines, distant creek`

### Clip 06 — overlook hold
- start_state: `he has stopped at the ridge, three-quarter back view, looking out over the dark valley, right hand on the pommel, moonlight now the key light`
- end_state: `same ridge stance, camera tighter, first sun catching the blade edge, breath visible, frame settled`
- action: exhales
- camera_move: `The camera pushes in with small amplitude at slow speed.`
- transition_out: none
- soundscape: `wind, cloth, one quiet breath`

Fixture assertion: `clips[i+1].start_state == clips[i].end_state` for i in 1..5.

---

## 14. Prompt assembly recipe (builder must implement as a function)

```
assemble_h3_prompt(lock, clip) -> string

alignment = (
  "How the reference pictures align with the target video — "
  "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
  "Picture 2 (from Shot 1) aligns with the 10.00-second mark of the target video."
)

body = (
  f"integrated_multimodal_description: [Shot 1] {lock.style}. "
  f"Begin exactly from Picture 1. {visual_lock_block(lock)} "
  f"{h1(clip, lock)} {clip.camera_move} as {h3_action(clip)}. "
  f"{h2(clip)} "
  f"One continuous uncut shot. Keep identity, wardrobe, and lighting recipe locked.\n\n"
  f"overall_soundscape: {clip.soundscape}\n"
  f"non_diegetic_music: {clip.music}"
)

return alignment + "\n\n" + body + "\n\n" + lock.negative
```

`assemble_qwen_start` and `assemble_qwen_end` fill Q2 / Q3 from the same clip object. Write the filled strings into `prompts/clipNN_*.txt` before calling Comfy / H3 so a failed job can be replayed.

---

## 15. Validation the app must run before spending a generation

Fail the clip (do not call Qwen or H3) if any of these are true:

1. `width`/`height` of start still ≠ end still
2. `duration_s != 10.00`
3. more than one verb in `action`
4. `camera_move` contains two of {push, pull, track, arc, tilt, pedestal} in opposite directions
5. clip N+1 `start_state` !== clip N `end_state`
6. identity / wardrobe / palette / lighting_bible differ from `story_lock`
7. H3 prompt is missing the exact alignment line, or the landing timestamp is not `10.00`
8. H3 prompt contains “cut to”, “smash cut”, “dissolve”, or a second `[Shot 2]`
9. Qwen end prompt re-describes the face instead of pointing at `<image1>`
10. transition_in of clip N+1 does not match transition_out of clip N

---

## 16. Acceptance tests

A build is done when all of these pass on the 6-clip fixture, then on a user story of ≥4 clips.

1. Every clip file is 10.00s ± 1 frame at 24fps.
2. Every still and every clip is 2560×1440 (or the lock canvas).
3. `clips[n+1].start_state` equals `clips[n].end_state` exactly.
4. `clips[n].end_extracted` exists and is used as `clips[n+1].start_image` for T-HARD joins.
5. Hard-cut `export/story.mp4` plays without a one-frame freeze at joins.
6. Face, wardrobe, and lighting direction are recognizably the same person/set across all clips. No extra characters. No text.
7. Prompts for every clip are saved under `clips/NN/` and can rebuild that clip alone.
8. Regenerating clip 03 does not rewrite `story_lock.json` or clip 01–02 states.

---

## 17. Builder do / don’t

Do:

- Treat this file as the prompt dialect. Fill slots. Do not restyle the alignment line.
- Copy END_STATE into the next START_STATE as a string assignment, not an LLM rewrite.
- Extract the rendered last frame. Designed end stills are a target, not the stitch source.
- Keep one change per clip.
- Persist JSON + prompts + stills + videos. The project must be resumable.

Don’t:

- Crossfade every join “to be safe.” Hard cut is correct when poses match.
- Regenerate a start still for T-HARD joins.
- Re-describe faces in Qwen edits when `<image1>` is present.
- Stack camera moves or verbs to “make it cinematic.”
- Change wardrobe, hair, or time of day at a stitch point.
- Invent a second prompt format for MiniMax. H0 is the format.
- Trust prompt-enhancer output that drops the alignment line or adds cuts.

---

## 18. First implementation slice and CLI

If the builder must phase the work:

1. JSON schemas + folder layout + continuity string copy.
2. Prompt assemblers for Q2, Q3, H0. Write files next to each clip.
3. Manual hook: operator drops start/end PNGs, app calls H3, extracts last frame, copies state forward.
4. Qwen Comfy job for Q1/Q2/Q3.
5. Auto H3 FL2VA job.
6. Conform + `export/story.mp4`.
7. Continuity editor reject/retry loop.

Do not start with a UI. Start with a project folder and a CLI or Hermes tool.

```
storyforge init "<brief>" --clips 6 --aspect 16:9 --res 2K
storyforge lock
storyforge plan
storyforge keyframes {clip_id}
storyforge animate {clip_id}
storyforge extract {clip_id}
storyforge audit {clip_id}
storyforge stitch
storyforge build          # full loop
```

Default story when the user gives no brief: the 6-clip bladesmith fixture in section 13.

---

## 19. Hermes system prompt (paste into the builder / Director agent)

```
You build and run CLIP_BRIDGE projects.

You plan long-form video as 10.00-second clips.
Qwen Image 2.1 makes START and END stills.
MiniMax H3 FL2VA animates between them.
ffmpeg extracts the rendered last frame and hard-cuts the story.

Continuity law: the end_state string of clip N is copied verbatim
into the start_state string of clip N+1. You do not paraphrase it.
The rendered last frame of clip N is the start image of clip N+1
unless the transition is T-MATCH, T-EXIT-ENTER, or T-OCCLUSION.

Every H3 prompt starts with the exact alignment line from CLIP_BRIDGE.md
and lands on Picture 2 at the 10.00-second mark.
One action. One camera move. One continuous shot.

You fill the partials in CLIP_BRIDGE.md. You do not invent a new dialect.
You validate the ten preflight checks before spending a generation.
You persist story_lock.json, clips.json, prompts, stills, and renders
so a failed clip can be retried in isolation.
```

---

## 20. ComfyUI workflow stubs

API-format graphs live in `comfy/` next to this file. Hermes POSTs them to `COMFY/prompt`. Do not POST official UI template JSON (those contain subgraphs and positions).

| File | Step |
|---|---|
| `comfy/CLIP_BRIDGE_COMFY.md` | Wiring, injection map, preflight |
| `comfy/qwen_t2i_sheet.json` | Q1 character sheet |
| `comfy/qwen_edit_start.json` | Q2 START still |
| `comfy/qwen_edit_end.json` | Q3 END still |
| `comfy/h3_fl2va_api.json` | Animate 10s 2K (preferred) |
| `comfy/h3_fl2va_native.json` | Local-GPU fallback only |
| `comfy/resize_lock.json` | Force 2560×1440 before H3 |

Gotchas the caller must not miss:

- Edit refs in API format are `images.image_1`, not `image_1`. Prompt text still says `<image1>`.
- `CLIPLoader.type` is `qwen_image`.
- `TextEncodeQwenImage21.resolution = 0` on edit graphs.
- H3 API duration is integer seconds (`10`). Local `MiniMaxH3ImageToVideo.length` is frames on the 17k+5 grid (`243` ≈ 10.125s). Prefer the API node for exact 10.00s 2K.
- Both H3 frames must be the same pixel size. Run `resize_lock.json` first.

Official UI templates if a stub fails to queue:

- https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/image_qwen_image_2_1_t2i.json
- https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/image_qwen_image_2_1_image_edit.json
- https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/api_minimax_h3_flf2v.json

End of spec. Implement from this file.
