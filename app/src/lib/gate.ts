import { formatCameraCell, holdOkForJoin, isSingleOfficialCamera } from "./camera.ts";
import { entityScheduleProblems } from "./entitySchedule.ts";
import { lockDiffProblems } from "./lockDiff.ts";
import { filled, isNumericPin, mentionsResearch, stillOk } from "./pack.ts";
import {
  canvasLooksStretched,
  canvasMatchesHop1,
  hop1ModeForPlate,
  inUseStills,
  isRealStillFile,
  missingIdentityPlate,
  plateFileForTake,
  stillCardProblems,
  stillSourceAgrees,
} from "./stills.ts";
import {
  AUDIO_PATHS,
  DEFAULT_STILL_CANVAS,
  ENERGY_VALUES,
  JOIN_TYPES,
  PROP_FIELDS,
  SPEECH_MODES,
  type CapturePack,
  type CharacterCard,
  type JoinType,
  type PropCard,
  type StepId,
} from "../types.ts";

export const GATE_DEFS = [
  { id: "log-line", n: 1, label: "Log line (one sentence)" },
  { id: "map", n: 2, label: "Map (clock → beat, not shots)" },
  { id: "edit-list", n: 3, label: "Edit list (join + one camera verb)" },
  { id: "takes", n: 4, label: "Take cards (one location + one grade)" },
  { id: "characters", n: 5, label: "Character cards (lock + forbidden)" },
  { id: "props", n: 6, label: "Prop cards (units + still or none)" },
  { id: "look", n: 7, label: "Look card (one style line)" },
  { id: "audio", n: 8, label: "Audio path (exactly one)" },
  { id: "smoke", n: 9, label: "Hop-1 smoke plan (I2VA if a plate exists, else T2V)" },
  { id: "entity-schedule", n: 10, label: "Entity schedule (who persists on which windows)" },
  { id: "lock-diff", n: 11, label: "Lock diff (same keywords every hop)" },
] as const;

export type GateId = (typeof GATE_DEFS)[number]["id"];

export type CardsTab = "characters" | "props" | "look" | "stills" | "schedule";

export const GATE_DESTINATION: Record<GateId, { step: StepId; cardsTab?: CardsTab }> = {
  "log-line": { step: "pack" },
  map: { step: "map" },
  "edit-list": { step: "edit" },
  takes: { step: "takes" },
  characters: { step: "cards", cardsTab: "characters" },
  props: { step: "cards", cardsTab: "props" },
  look: { step: "cards", cardsTab: "look" },
  audio: { step: "pack" },
  smoke: { step: "smoke" },
  "entity-schedule": { step: "cards", cardsTab: "schedule" },
  "lock-diff": { step: "cards", cardsTab: "characters" },
};

export type GateResult = {
  id: GateId;
  n: number;
  label: string;
  ok: boolean;
  detail: string;
};

function looksLikeShot(text: string): boolean {
  if (/\bshot\s*\d+\b/i.test(text)) return true;
  if (/\b(ecu|wide shot|close[- ]up|medium shot|long shot)\b/i.test(text)) return true;
  // CU / MS / WS as camera sizes — not "18 ms" milliseconds on a clock.
  const withoutDurationMs = text.replace(/\d+\s*ms\b/gi, " ");
  return /(^|[\s,/])(cu|ms|ws)([\s,/]|$)/i.test(withoutDurationMs);
}

function energyOk(energy: string): boolean {
  const e = energy.trim().toLowerCase();
  return (ENERGY_VALUES as readonly string[]).includes(e);
}

function joinOk(join: string): join is JoinType {
  return (JOIN_TYPES as readonly string[]).includes(join);
}

function propUnresolved(prop: PropCard): { overallHaft: boolean; still: boolean } {
  return {
    overallHaft:
      !isNumericPin(prop.fields.overallLength.value) ||
      !isNumericPin(prop.fields.haftLength.value),
    still: !stillOk(prop.stillFile),
  };
}

function propResearch(prop: PropCard): boolean {
  const blob = [
    prop.name,
    prop.lockParagraph,
    prop.forbidden,
    ...PROP_FIELDS.map((field) => prop.fields[field.key].value),
  ].join(" ");
  return mentionsResearch(blob);
}

function evaluateLogLine(pack: CapturePack): GateResult {
  const ok = filled(pack.logLine);
  return {
    ...GATE_DEFS[0],
    ok,
    detail: ok ? "One sentence locked." : "Need a one-sentence log line.",
  };
}

function evaluateMap(pack: CapturePack): GateResult {
  if (pack.map.length === 0) {
    return { ...GATE_DEFS[1], ok: false, detail: "Map is empty." };
  }
  const incomplete = pack.map.filter(
    (row) => !filled(row.clock) || !filled(row.beat) || !energyOk(row.energy),
  );
  if (incomplete.length) {
    return {
      ...GATE_DEFS[1],
      ok: false,
      detail: `${incomplete.length} row(s) missing clock, beat, or energy (verse/chorus/bridge).`,
    };
  }
  const shotty = pack.map.filter(
    (row) => looksLikeShot(row.clock) || looksLikeShot(row.beat),
  );
  if (shotty.length) {
    return {
      ...GATE_DEFS[1],
      ok: false,
      detail: "Map is clocks and beats, not shots. Move camera to the edit list.",
    };
  }
  return {
    ...GATE_DEFS[1],
    ok: true,
    detail: `${pack.map.length} clock → beat row(s).`,
  };
}

function takeOk(join: string, take: string): boolean {
  const t = take.trim();
  if (!t) return false;
  if (t === "—" || t === "-") return join === "cut";
  return true;
}

function holdProblem(join: string, n: number): string {
  if (join === "fadeblack") return `#${n} fadeblack hold must be yes before fade`;
  if (join === "continue") return `#${n} continue must hold = no`;
  if (join === "cut") return `#${n} cut must hold = no`;
  return `#${n} needs a Hold? value`;
}

function evaluateEditList(pack: CapturePack): GateResult {
  if (pack.editList.length === 0) {
    return { ...GATE_DEFS[2], ok: false, detail: "Edit list is empty." };
  }
  const problems: string[] = [];
  pack.editList.forEach((row, i) => {
    const n = i + 1;
    if (!joinOk(row.join)) {
      problems.push(`#${n} join must be continue, cut, or fadeblack`);
    }
    if (!filled(row.songT)) {
      problems.push(`#${n} needs song t`);
    }
    if (!takeOk(row.join, row.take)) {
      problems.push(`#${n} needs a take`);
    }
    if (!filled(row.locationGrade)) {
      problems.push(`#${n} needs location / grade`);
    }
    if (!filled(row.action)) {
      problems.push(`#${n} needs action`);
    }
    const camera = formatCameraCell(row.cameraVerb, row.cameraAmplitude, row.cameraSpeed);
    if (
      !row.cameraVerb ||
      !filled(row.cameraAmplitude) ||
      !filled(row.cameraSpeed) ||
      !isSingleOfficialCamera(camera)
    ) {
      problems.push(`#${n} needs exactly one official camera verb (type + amplitude + speed)`);
    }
    if (row.join && !holdOkForJoin(row.join, row.hold)) {
      problems.push(holdProblem(row.join, n));
    }
    const takeName = row.take.trim();
    const knownTakes = new Set(pack.takes.map((item) => item.take.trim()).filter(Boolean));
    if (takeName && takeName !== "—" && takeName !== "-" && !knownTakes.has(takeName)) {
      problems.push(`#${n} take ${takeName} is not on the take cards`);
    }
    if (row.join === "continue") {
      const jumped = continueJumpedLocation(pack, row.locationGrade, takeName);
      if (jumped) {
        problems.push(`#${n} continue jumped to take ${jumped}'s location — that is cut or fadeblack`);
      }
    }
  });
  if (problems.length) {
    return { ...GATE_DEFS[2], ok: false, detail: problems.slice(0, 3).join("; ") };
  }
  return {
    ...GATE_DEFS[2],
    ok: true,
    detail: `${pack.editList.length} row(s), each one join, clock, take, action, and one verb.`,
  };
}

function continueJumpedLocation(pack: CapturePack, locationGrade: string, takeName: string): string | null {
  const loc = locationGrade.toLowerCase();
  if (!loc) return null;
  const self = pack.takes.find((item) => item.take.trim() === takeName);
  const selfLoc = self?.location.trim().toLowerCase() ?? "";
  if (selfLoc && loc.includes(selfLoc)) return null;
  for (const take of pack.takes) {
    if (take.take.trim() === takeName) continue;
    const other = take.location.trim().toLowerCase();
    if (other.length < 4) continue;
    if (loc.includes(other)) return take.take.trim();
  }
  return null;
}

function evaluateTakes(pack: CapturePack): GateResult {
  if (pack.takes.length === 0) {
    return { ...GATE_DEFS[3], ok: false, detail: "No takes." };
  }
  const incomplete = pack.takes.filter(
    (row) =>
      !filled(row.take) ||
      !filled(row.location) ||
      !filled(row.grade) ||
      !filled(row.windows) ||
      !filled(row.prefix),
  );
  if (incomplete.length) {
    return {
      ...GATE_DEFS[3],
      ok: false,
      detail: `${incomplete.length} take(s) missing location, grade, windows, or prefix.`,
    };
  }
  return {
    ...GATE_DEFS[3],
    ok: true,
    detail: `${pack.takes.length} take(s), one location and grade each.`,
  };
}

function sheetStillProblems(card: CharacterCard | PropCard, kind: "character" | "prop"): string[] {
  const label = filled(card.name) ? card.name : `unnamed ${kind}`;
  const problems: string[] = [];
  if (!stillOk(card.stillFile)) {
    problems.push(`${label}: sheet path or none + why`);
  }
  if (!stillSourceAgrees(card.stillFile, card.stillSource)) {
    problems.push(`${label}: sheet source (photo / qwen-t2i / qwen-edit / none) must match the file`);
  }
  if (!canvasMatchesHop1(card.stillCanvas) || canvasLooksStretched(card.stillCanvas)) {
    problems.push(`${label}: sheet canvas must be ${DEFAULT_STILL_CANVAS} (do not stretch 1024²)`);
  }
  return problems;
}

function evaluateCharacters(pack: CapturePack): GateResult {
  if (pack.characters.length === 0) {
    return { ...GATE_DEFS[4], ok: false, detail: "Need at least one character card." };
  }
  const problems: string[] = [];
  for (const card of pack.characters) {
    if (!filled(card.name) || !filled(card.lockParagraph) || !filled(card.forbidden)) {
      const label = filled(card.name) ? card.name : "unnamed character";
      problems.push(`${label}: name, lock paragraph, forbidden`);
    }
    problems.push(...sheetStillProblems(card, "character"));
  }
  if (problems.length) {
    return {
      ...GATE_DEFS[4],
      ok: false,
      detail: `${problems.slice(0, 3).join("; ")}. Plates live on still cards.`,
    };
  }
  return {
    ...GATE_DEFS[4],
    ok: true,
    detail: `${pack.characters.length} character card(s) locked. Sheets only — plates live on still cards.`,
  };
}

function evaluateProps(pack: CapturePack): GateResult {
  if (pack.props.length === 0) {
    return { ...GATE_DEFS[5], ok: false, detail: "Need at least one prop card." };
  }
  const problems: string[] = [];
  for (const prop of pack.props) {
    const label = filled(prop.name) ? prop.name : "unnamed prop";
    if (!filled(prop.name) || !filled(prop.lockParagraph) || !filled(prop.forbidden)) {
      problems.push(`${label}: lock paragraph + forbidden required`);
    }
    const flags = propUnresolved(prop);
    if (flags.overallHaft) {
      problems.push(`${label}: overall vs haft length unresolved`);
    }
    if (flags.still) {
      problems.push(`${label}: no still and no reason`);
    } else {
      problems.push(...sheetStillProblems(prop, "prop").filter((item) => !item.includes("sheet path")));
    }
    const missing = PROP_FIELDS.filter((field) => {
      const m = prop.fields[field.key];
      return !filled(m.value) || !filled(m.unit);
    });
    if (missing.length) {
      problems.push(`${label}: ${missing.length} field(s) missing value/unit`);
    }
    if (propResearch(prop)) {
      problems.push(`${label}: “research” is treatment homework, not generate-time`);
    }
  }
  if (problems.length) {
    return { ...GATE_DEFS[5], ok: false, detail: problems.slice(0, 3).join("; ") };
  }
  return {
    ...GATE_DEFS[5],
    ok: true,
    detail: `${pack.props.length} prop card(s) with units and still or none.`,
  };
}

function evaluateLook(pack: CapturePack): GateResult {
  const ok = filled(pack.look.styleLine);
  return {
    ...GATE_DEFS[6],
    ok,
    detail: ok ? "One style line locked." : "Look card needs one style line.",
  };
}

function evaluateAudio(pack: CapturePack): GateResult {
  const audioOk = (AUDIO_PATHS as readonly string[]).includes(pack.audioPath);
  if (!audioOk) {
    return {
      ...GATE_DEFS[7],
      ok: false,
      detail: "Pick exactly one: N/A + mute, prompt score, or silence.",
    };
  }
  if (!(SPEECH_MODES as readonly string[]).includes(pack.speech)) {
    return {
      ...GATE_DEFS[7],
      ok: false,
      detail: "Speech: none, or lines finish by 8.0 s.",
    };
  }
  const labels: Record<string, string> = {
    "na-mute": "N/A + mute in NLE",
    "prompt-score": "prompt score",
    silence: "silence",
  };
  return {
    ...GATE_DEFS[7],
    ok: true,
    detail: `${labels[pack.audioPath]}. Speech: ${pack.speech === "none" ? "none" : "finish by 8.0 s"}.`,
  };
}

function evaluateSmoke(pack: CapturePack): GateResult {
  if (pack.takes.length === 0) {
    return { ...GATE_DEFS[8], ok: false, detail: "No takes to smoke." };
  }
  if (!filled(pack.smokeNotes)) {
    return { ...GATE_DEFS[8], ok: false, detail: "Smoke plan notes are empty." };
  }
  const problems: string[] = [];
  const unplanned = pack.takes.filter((row) => !row.hop1Planned || !row.watched);
  if (unplanned.length) {
    problems.push(`${unplanned.length} take(s) missing hop-1 planned + watched`);
  }
  const prefixes = pack.takes.map((row) => row.prefix.trim().toLowerCase()).filter(Boolean);
  const unique = new Set(prefixes);
  if (prefixes.length !== pack.takes.length || unique.size !== prefixes.length) {
    problems.push("Each take needs a unique hop-1 prefix");
  }

  for (const take of pack.takes) {
    const label = filled(take.take) ? `take ${take.take}` : "unnamed take";
    const plate = plateFileForTake(pack, take);
    const derived = hop1ModeForPlate(plate);
    if (!take.hop1Mode) {
      problems.push(`${label}: hop-1 mode I2VA or T2V`);
      continue;
    }
    if (!stillOk(plate)) {
      problems.push(`${label}: plate file or none + why`);
      continue;
    }
    if (take.hop1Mode === "i2va" && !isRealStillFile(plate)) {
      problems.push(`${label}: I2VA needs a plate file for MiniMaxH3ImageToVideo.first_frame`);
    }
    if (take.hop1Mode === "t2v" && isRealStillFile(plate)) {
      problems.push(`${label}: a plate exists — hop-1 must be I2VA, not T2V`);
    }
    if (derived && take.hop1Mode !== derived) {
      problems.push(`${label}: hop-1 is ${take.hop1Mode.toUpperCase()} but the plate implies ${derived.toUpperCase()}`);
    }
  }

  const lookLine = pack.look.styleLine;
  for (const card of inUseStills(pack)) {
    problems.push(...stillCardProblems(card, lookLine));
  }

  pack.editList.forEach((_, index) => {
    const missing = missingIdentityPlate(pack, index);
    if (missing) problems.push(missing);
  });

  if (problems.length) {
    return { ...GATE_DEFS[8], ok: false, detail: problems.slice(0, 3).join("; ") };
  }
  const i2va = pack.takes.filter((row) => row.hop1Mode === "i2va").length;
  const t2v = pack.takes.filter((row) => row.hop1Mode === "t2v").length;
  return {
    ...GATE_DEFS[8],
    ok: true,
    detail: `${pack.takes.length} hop-1(s) planned and watched (${i2va} I2VA, ${t2v} T2V). continue hop 2+ is the latent.`,
  };
}

function evaluateEntitySchedule(pack: CapturePack): GateResult {
  const problems = entityScheduleProblems(pack);
  if (problems.length) {
    return { ...GATE_DEFS[9], ok: false, detail: problems.slice(0, 3).join("; ") };
  }
  const n = pack.entitySchedule.filter((row) => row.entityName.trim()).length;
  return {
    ...GATE_DEFS[9],
    ok: true,
    detail: `${n} scheduled entit${n === 1 ? "y" : "ies"}; windows list them; cut/fadeblack identity holds have plates.`,
  };
}

function evaluateLockDiff(pack: CapturePack): GateResult {
  const textsOk = pack.characters.some((card) => filled(card.name) && filled(card.lockParagraph))
    || pack.props.some((card) => filled(card.name) && filled(card.lockParagraph));
  if (!textsOk) {
    return {
      ...GATE_DEFS[10],
      ok: false,
      detail: "Need lock paragraphs on named entities before a lock-diff can pass.",
    };
  }
  const problems = lockDiffProblems(pack);
  if (problems.length) {
    return { ...GATE_DEFS[10], ok: false, detail: problems.slice(0, 3).map((item) => item.detail).join("; ") };
  }
  return {
    ...GATE_DEFS[10],
    ok: true,
    detail: "Lock keywords match across cards and stills. No rotating synonyms.",
  };
}

const EVALUATORS = [
  evaluateLogLine,
  evaluateMap,
  evaluateEditList,
  evaluateTakes,
  evaluateCharacters,
  evaluateProps,
  evaluateLook,
  evaluateAudio,
  evaluateSmoke,
  evaluateEntitySchedule,
  evaluateLockDiff,
];

export function evaluateGates(pack: CapturePack): GateResult[] {
  return EVALUATORS.map((fn) => fn(pack));
}

export function allGatesGreen(pack: CapturePack): boolean {
  return evaluateGates(pack).every((gate) => gate.ok);
}

export function gateChecklistMarkdown(pack: CapturePack): string {
  const gates = evaluateGates(pack);
  const lines = gates.map(
    (gate) => `- [${gate.ok ? "x" : " "}] ${gate.n}. ${gate.label} — ${gate.detail}`,
  );
  const ready = gates.every((gate) => gate.ok);
  return `# Capture pack gate

${lines.join("\n")}

Ready to queue Comfy? ${ready ? "Yes." : "No. Do not queue."}
`;
}

export function packSummaryMarkdown(pack: CapturePack): string {
  const title = filled(pack.title) ? pack.title.trim() : "(untitled)";
  const hops = pack.takes
    .map((row) => {
      const mode = row.hop1Mode === "i2va" ? "I2VA" : row.hop1Mode === "t2v" ? "T2V" : "no hop-1 mode";
      return `- Take ${row.take || "—"} · ${mode} · ${row.hop1Plate || "no plate"}`;
    })
    .join("\n");
  const stills = inUseStills(pack)
    .map((card) => `- ${card.entity || "unnamed"} · ${card.role || "no role"} · ${card.file || "no file"}`)
    .join("\n");
  return `# Pack summary — ${title}

Log line: ${filled(pack.logLine) ? pack.logLine.trim() : "(empty)"}

${gateChecklistMarkdown(pack)}
## Hop-1
${hops || "(no takes)"}

## Still cards
${stills || "(none)"}

## Polaroid / hop-1 grab
${filled(pack.polaroidPath) ? pack.polaroidPath : "(empty)"}
`;
}

export function propGenerateFlags(prop: PropCard): {
  overallHaftUnresolved: boolean;
  noStillAndNoReason: boolean;
} {
  const flags = propUnresolved(prop);
  return {
    overallHaftUnresolved: flags.overallHaft,
    noStillAndNoReason: flags.still,
  };
}
