import { formatCameraCell } from "./camera.ts";
import { fileSlug, filled } from "./pack.ts";
import { allGatesGreen, propGenerateFlags } from "./gate.ts";
import {
  CHARACTER_LOCK_FIELDS,
  PROP_FIELDS,
  STACK_LINE,
  type CapturePack,
  type CharacterCard,
  type PropCard,
} from "../types.ts";

function cell(value: string): string {
  return value.replace(/\s*\|\s*/g, " / ").replace(/\n+/g, " ").trim();
}

function quote(value: string): string {
  const lines = value.trim() ? value.trim().split(/\n/) : [""];
  return lines.map((line) => `> ${line}`.trimEnd()).join("\n");
}

function box(on: boolean): string {
  return on ? "[x]" : "[ ]";
}

function table(headers: string[], rows: string[][]): string {
  const head = `| ${headers.join(" | ")} |`;
  const sep = `|${headers.map(() => "---").join("|")}|`;
  const body = rows.map((row) => `| ${row.map(cell).join(" | ")} |`).join("\n");
  return `${head}\n${sep}\n${body}`;
}

function joinCell(pack: CapturePack, index: number): string {
  const row = pack.editList[index];
  if (!row.join) return "";
  if (row.join === "fadeblack" && filled(row.take) && row.take !== "—") {
    return `fadeblack→${row.take.trim()}`;
  }
  return row.join;
}

export function renderReadme(pack: CapturePack): string {
  const title = filled(pack.title) ? pack.title.trim() : "{TITLE}";
  const audio = pack.audioPath;
  const speech = pack.speech;
  const map = table(
    ["Clock", "Beat", "Energy (verse/chorus/bridge)"],
    pack.map.map((row) => [row.clock, row.beat, row.energy]),
  );
  const takes = table(
    ["Take", "Location", "Grade", "Windows", "Prefix", "Hop-1 seed"],
    pack.takes.map((row) => [
      row.take,
      row.location,
      row.grade,
      row.windows,
      row.prefix,
      row.hop1Seed,
    ]),
  );
  const smokeTakes = table(
    ["Take", "Prefix", "T2V planned", "Watched"],
    pack.takes.map((row) => [
      row.take,
      row.prefix,
      row.t2vPlanned ? "yes" : "no",
      row.watched ? "yes" : "no",
    ]),
  );
  const stills = table(
    ["Entity", "File", "Conditions hop"],
    pack.stills.map((row) => [row.entity, row.file, row.conditionsHop]),
  );
  const lookLock = filled(pack.look.styleLine) ? pack.look.styleLine : "";
  const draft = allGatesGreen(pack)
    ? ""
    : "> DRAFT — gates red. Do not queue Comfy.\n\n";

  return `${draft}# Capture pack — ${title}

Log line (one sentence):
${quote(pack.logLine)}

Duration target:
${pack.durationTarget.trim()}
Song / narrative clock:
${pack.songNarrativeClock.trim()}
Stack: ${STACK_LINE}
Audio path: ${box(audio === "na-mute")} N/A + mute in NLE   ${box(audio === "prompt-score")} prompt score   ${box(audio === "silence")} silence
Speech: ${box(speech === "none")} none   ${box(speech === "finish-by-8s")} lines finish by 8.0 s

## Map (clock → beat, not shots)

${map}

## Takes

${takes}

## Edit list

See \`edit-list.md\` in this pack. Every row: join ∈ {continue, cut, fadeblack}, **one** camera verb.

## Cards

- Characters: \`character-*.md\`
- Props: \`prop-*.md\`
- Look: \`look.md\`

Look lock:
${quote(lookLock)}

Forbidden (global):
${quote(pack.forbiddenGlobal)}

## Stills

${stills}

Wikipedia is not a still.

## Smoke

${pack.smokeNotes.trim() || "One T2V per take + planned fades. Watch identity at cuts. Do not hop until this join is watchable."}

${smokeTakes}

## Continuity log

Fill \`continuity-log.md\` during generate.
`;
}

export function renderEditList(pack: CapturePack): string {
  const title = filled(pack.title) ? pack.title.trim() : "{TITLE}";
  const rows = pack.editList.map((row, i) => [
    String(i + 1),
    row.songT,
    row.durS,
    joinCell(pack, i),
    row.take,
    row.locationGrade,
    formatCameraCell(row.cameraVerb, row.cameraAmplitude, row.cameraSpeed),
    row.action,
    row.hold,
    row.notes,
  ]);
  return `# Edit list — ${title}

Join: \`continue\` = Motion-Context hop. \`cut\` = new T2V hard cut (no hold). \`fadeblack\` = new take + 8-frame dip.

Camera: one verb, amplitude, speed. Official: push/pull, pan, truck, tilt, pedestal, arc, track, static, shake.

${table(
    ["#", "Song t", "Dur s", "Join", "Take", "Location / grade", "Camera (one)", "Action", "Hold?", "Notes"],
    rows,
  )}
`;
}

export function renderLook(pack: CapturePack): string {
  const title = filled(pack.title) ? pack.title.trim() : "{TITLE}";
  return `# Look card — ${title}

One style line (paste into every \`[Shot 1]\`):
${quote(pack.look.styleLine)}

Palette / grade:
${quote(pack.look.paletteGrade)}

Era:
${quote(pack.look.era)}

Lens / grain (optional):
${quote(pack.look.lensGrain)}

Extras forbidden:
${quote(pack.look.extrasForbidden)}

Do not mix noon and night in one 10 s window. Gold / dusk / amber are three takes, not one prompt.
`;
}

export function renderContinuity(pack: CapturePack): string {
  const title = filled(pack.title) ? pack.title.trim() : "{TITLE}";
  const rows = pack.continuityRows.map((row) => [
    row.take,
    row.hop,
    row.seed,
    row.wallS,
    row.peakC,
    row.ffprobe,
    row.stillVsLock,
    row.circleNg,
    row.why,
  ]);
  return `# Continuity log — ${title}

Intent is the edit list. This file is what landed.

${table(
    ["Take", "Hop", "Seed", "Wall s", "Peak °C", "ffprobe (dur / frames)", "Still vs lock", "Circle / NG", "Why"],
    rows,
  )}

NG = no good (thermal abort, identity break, wrong prop). Keep the take if earlier hops passed.

Polaroid / still grab after hop-1 (path):
${quote(pack.polaroidPath)}
`;
}

export function renderCharacter(card: CharacterCard): string {
  const name = filled(card.name) ? card.name.trim() : "{NAME}";
  const lockRows = CHARACTER_LOCK_FIELDS.map((field) => [field.label, card[field.key]]);
  return `# Character card — ${name}

Still file (or \`none\`):
${card.stillFile.trim()}
Speaker ID (if any): ${filled(card.speakerId) ? card.speakerId.trim() : "none"}

${table(["Field", "Lock (same words every hop)"], lockRows)}

Lock paragraph:
${quote(card.lockParagraph)}

Forbidden:
${quote(card.forbidden)}

Motion notes (how they stand / walk) — optional:
${quote(card.motionNotes)}
`;
}

export function renderProp(card: PropCard): string {
  const name = filled(card.name) ? card.name.trim() : "{NAME}";
  const flags = propGenerateFlags(card);
  const rows = PROP_FIELDS.map((field) => {
    const m = card.fields[field.key];
    return [field.label, m.value, m.unit, m.source];
  });
  return `# Prop card — ${name}

Still file (or \`none\`):
${card.stillFile.trim()}

${table(["Field", "Value", "Unit", "Source (lyric / photo / measured)"], rows)}

Lock paragraph (paste verbatim into every hop that shows this prop):
${quote(card.lockParagraph)}

Forbidden (do not invent):
${quote(card.forbidden)}

Before generate these must be empty:

- ${box(flags.overallHaftUnresolved)} overall vs haft length unresolved
- ${box(flags.noStillAndNoReason)} no still and no reason
`;
}

export type PackFiles = Record<string, string>;

function uniqueFilename(used: Set<string>, base: string): string {
  if (!used.has(base)) {
    used.add(base);
    return base;
  }
  let n = 2;
  while (used.has(base.replace(/\.md$/, `-${n}.md`))) n += 1;
  const next = base.replace(/\.md$/, `-${n}.md`);
  used.add(next);
  return next;
}

export function packToFiles(pack: CapturePack): PackFiles {
  const used = new Set<string>();
  const files: PackFiles = {
    "README.md": renderReadme(pack),
    "edit-list.md": renderEditList(pack),
    "look.md": renderLook(pack),
    "continuity-log.md": renderContinuity(pack),
  };
  used.add("README.md");
  used.add("edit-list.md");
  used.add("look.md");
  used.add("continuity-log.md");

  for (const card of pack.characters) {
    const name = uniqueFilename(used, `character-${fileSlug(card.name, "unnamed")}.md`);
    files[name] = renderCharacter(card);
  }
  for (const card of pack.props) {
    const name = uniqueFilename(used, `prop-${fileSlug(card.name, "unnamed")}.md`);
    files[name] = renderProp(card);
  }
  return files;
}
