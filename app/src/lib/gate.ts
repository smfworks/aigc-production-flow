import { formatCameraCell, holdOkForJoin, isSingleOfficialCamera } from "./camera.ts";
import { filled, isNumericPin, mentionsResearch, stillOk } from "./pack.ts";
import {
  ENERGY_VALUES,
  JOIN_TYPES,
  PROP_FIELDS,
  type CapturePack,
  type JoinType,
  type PropCard,
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
  { id: "smoke", n: 9, label: "Hop-1 smoke plan (one hop-1 per take)" },
] as const;

export type GateId = (typeof GATE_DEFS)[number]["id"];

export type GateResult = {
  id: GateId;
  n: number;
  label: string;
  ok: boolean;
  detail: string;
};

function looksLikeShot(text: string): boolean {
  return /\bshot\s*\d+\b/i.test(text) || /\b(ecu|cu|ms|ws|wide shot|close[- ]up)\b/i.test(text);
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
    ...PROP_FIELDS.map((field) => {
      const m = prop.fields[field.key];
      return `${m.value} ${m.source}`;
    }),
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
      !filled(row.prefix) ||
      !filled(row.hop1Seed),
  );
  if (incomplete.length) {
    return {
      ...GATE_DEFS[3],
      ok: false,
      detail: `${incomplete.length} take(s) missing location, grade, windows, prefix, or hop-1 seed.`,
    };
  }
  return {
    ...GATE_DEFS[3],
    ok: true,
    detail: `${pack.takes.length} take(s), one location and grade each.`,
  };
}

function evaluateCharacters(pack: CapturePack): GateResult {
  if (pack.characters.length === 0) {
    return { ...GATE_DEFS[4], ok: false, detail: "Need at least one character card." };
  }
  const incomplete = pack.characters.filter(
    (card) =>
      !filled(card.name) ||
      !filled(card.lockParagraph) ||
      !filled(card.forbidden) ||
      !stillOk(card.stillFile),
  );
  if (incomplete.length) {
    return {
      ...GATE_DEFS[4],
      ok: false,
      detail: `${incomplete.length} character(s) need name, lock paragraph, forbidden, and still or none + why.`,
    };
  }
  return {
    ...GATE_DEFS[4],
    ok: true,
    detail: `${pack.characters.length} character card(s) locked.`,
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
  if (!pack.audioPath) {
    return {
      ...GATE_DEFS[7],
      ok: false,
      detail: "Pick exactly one: N/A + mute, prompt score, or silence.",
    };
  }
  if (!pack.speech) {
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
  const unplanned = pack.takes.filter((row) => !row.t2vPlanned || !row.watched);
  if (unplanned.length) {
    return {
      ...GATE_DEFS[8],
      ok: false,
      detail: `${unplanned.length} take(s) missing hop-1 planned + watched.`,
    };
  }
  const prefixes = pack.takes.map((row) => row.prefix.trim().toLowerCase()).filter(Boolean);
  const unique = new Set(prefixes);
  if (prefixes.length !== pack.takes.length || unique.size !== prefixes.length) {
    return {
      ...GATE_DEFS[8],
      ok: false,
      detail: "Each take needs a unique hop-1 prefix.",
    };
  }
  return {
    ...GATE_DEFS[8],
    ok: true,
    detail: `${pack.takes.length} hop-1(s) planned and watched before hopping.`,
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
];

export function evaluateGates(pack: CapturePack): GateResult[] {
  return EVALUATORS.map((fn) => fn(pack));
}

export function allGatesGreen(pack: CapturePack): boolean {
  return evaluateGates(pack).every((gate) => gate.ok);
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
