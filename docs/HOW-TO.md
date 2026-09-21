# How to use this on GitHub

This is the operator path. The why is in [FRAMEWORK.md](FRAMEWORK.md). The four stages are in [PRODUCTION-FLOW.md](PRODUCTION-FLOW.md).

## Create or fork

**Clone (read-only or if you have push):**

```bash
git clone https://github.com/smfworks/aigc-production-flow.git
cd aigc-production-flow
```

**Fork (your packs stay on your account):**

1. Open https://github.com/smfworks/aigc-production-flow
2. Fork
3. `git clone https://github.com/<you>/aigc-production-flow.git`

The previous name `h3-longform-capture` redirects here.

Do not open a PR that contains your unreleased music, likeness stills, or engine MP4s. Packs with private stills belong in a **private** fork or a sibling private repo. This public tree is templates + process.

## One job = one directory

```bash
JOB=packs/2026-09-17-sigils-reshoot
mkdir -p "$JOB"
cp templates/capture-pack.md    "$JOB/README.md"
cp templates/edit-list.md       "$JOB/edit-list.md"
cp templates/look-card.md       "$JOB/look.md"
cp templates/continuity-log.md  "$JOB/continuity-log.md"
cp templates/character-card.md  "$JOB/character-smith.md"
cp templates/character-card.md  "$JOB/character-thrower.md"
cp templates/prop-card.md       "$JOB/prop-francisca.md"
cp templates/still-card.md      "$JOB/still-hop1-a.md"
```

Stills go in `$JOB/stills/` and are referenced by relative path. Name sheets `{entity}-sheet.png` and plates `{take}-hop1-plate.png`. Git LFS is not required for a handful of PNGs. Do not commit likeness stills to the public tree.

## Fill order (do not skip)

**1. Script analysis**

1. `README.md` log line + duration + audio path
2. Map table (clock → verse/chorus) — beats, not cameras

**2. Asset setup**

3. Character + prop cards (units, forbidden, still or `none`)
4. Look card (one style line)
5. Still factory: sheets, then plates at 1344×768 (see [IMAGE-STILLS.md](IMAGE-STILLS.md))

**3. Storyboard**

6. Takes table (location, grade, prefix)
7. Edit list (every row: join + one camera verb)

**4. Video preview**

8. Smoke plan (I2VA hop-1 if a plate exists)
9. Only then: hop-1 on the clip box

Ambiguous prop fields (overall vs haft length) must be resolved or the pack is incomplete.

## Commit a pack (optional)

```bash
git checkout -b pack/my-title
git add packs/my-title
git commit -m "pack: my-title — capture bible only, no MP4s"
git push -u origin pack/my-title
```

Public PRs: templates and redacted examples only.

## Gate checklist (copy into the PR or the job README)

- [ ] Log line
- [ ] Map is clocks, not shots
- [ ] Every edit-list row has join ∈ {continue, cut, fadeblack}
- [ ] Every row has exactly one camera verb
- [ ] Every character/prop has lock paragraph + forbidden + still or `none`
- [ ] Audio path is one of three
- [ ] Hop-1 smoke planned per take (I2VA if a plate exists)
- [ ] Sheet vs plate named; canvas 1344×768 or `none` + why
- [ ] Entity schedule lists who persists on which windows
- [ ] Lock paragraphs keep the same identity keywords (no brown/brunette rotation)
- [ ] No “research X at generate time”

## After generate

Fill `continuity-log.md` from `sigils.jsonl` / Comfy history: seed, peak °C, ffprobe, NG reason. The shot list is intent. The log is what the editor gets.

## Studio spine (optional, local)

The pack builder is enough to fill and zip a bible. If you want projects, review states, a job center, hop-1 preview receipts, and stub engine adapters around that zip, see [STUDIO.md](STUDIO.md). `generate-ok` cannot be stamped while any gate is red or a required hop-1 lacks a watched continuity receipt.
