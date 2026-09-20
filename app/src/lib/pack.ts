import {
  DEFAULT_CHARACTER_FORBIDDEN,
  DEFAULT_GLOBAL_FORBIDDEN,
  DEFAULT_LOOK_FORBIDDEN,
  DEFAULT_PROP_FORBIDDEN,
  DEFAULT_SMOKE_NOTES,
  DEFAULT_STILL_CANVAS,
  PROP_FIELDS,
  type CapturePack,
  type CharacterCard,
  type ContinuityRow,
  type EditRow,
  type MapRow,
  type PropCard,
  type PropFieldKey,
  type PropMeasurement,
  type StillCard,
  type TakeCard,
} from "../types.ts";

export function uid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `id-${Math.random().toString(16).slice(2)}-${Date.now().toString(16)}`;
}

export function filled(value: string | undefined | null): boolean {
  return typeof value === "string" && value.trim().length > 0;
}

/** Values that look filled but are not pinned measurements. */
const PIN_PLACEHOLDER =
  /^(none|tbd|n\/?a|n\.a\.|na|unknown|unresolved|unset|todo)(\b|$)/i;

export function isPlaceholderPin(value: string): boolean {
  const v = value.trim();
  if (!v) return true;
  return PIN_PLACEHOLDER.test(v.replace(/[*_]/g, "").trim());
}

/** Overall / haft length: a real number, not none / TBD / unknown. */
export function isNumericPin(value: string): boolean {
  if (isPlaceholderPin(value)) return false;
  return /\d/.test(value);
}

export function slugify(raw: string, fallback = "untitled-pack"): string {
  const slug = raw
    .toLowerCase()
    .replace(/['"]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return slug || fallback;
}

export function emptyMeasurement(unit: string): PropMeasurement {
  return { value: "", unit, source: "" };
}

export function emptyPropFields(): Record<PropFieldKey, PropMeasurement> {
  const fields = {} as Record<PropFieldKey, PropMeasurement>;
  for (const field of PROP_FIELDS) {
    fields[field.key] = emptyMeasurement(field.unit);
  }
  return fields;
}

export function emptyMapRow(): MapRow {
  return { id: uid(), clock: "", beat: "", energy: "" };
}

export function emptyTake(letter = "A"): TakeCard {
  return {
    id: uid(),
    take: letter,
    location: "",
    grade: "",
    windows: "",
    prefix: "",
    hop1Seed: "",
    hop1Mode: "",
    hop1Plate: "",
    hop1Planned: false,
    watched: false,
  };
}

export function emptyEditRow(): EditRow {
  return {
    id: uid(),
    songT: "",
    durS: "10.125",
    join: "",
    take: "",
    locationGrade: "",
    cameraVerb: "",
    cameraAmplitude: "",
    cameraSpeed: "",
    action: "",
    hold: "",
    notes: "",
  };
}

export function emptyCharacter(): CharacterCard {
  return {
    id: uid(),
    name: "",
    stillFile: "",
    stillSource: "",
    stillCanvas: DEFAULT_STILL_CANVAS,
    speakerId: "none",
    ageSex: "",
    faceHairBeard: "",
    body: "",
    wardrobe: "",
    footwear: "",
    distinguishingMarks: "",
    eraForbiddenModern: "",
    lockParagraph: "",
    forbidden: DEFAULT_CHARACTER_FORBIDDEN,
    motionNotes: "",
  };
}

export function emptyProp(): PropCard {
  return {
    id: uid(),
    name: "",
    stillFile: "",
    stillSource: "",
    stillCanvas: DEFAULT_STILL_CANVAS,
    fields: emptyPropFields(),
    lockParagraph: "",
    forbidden: DEFAULT_PROP_FORBIDDEN,
  };
}

export function emptyStill(): StillCard {
  return {
    id: uid(),
    entity: "",
    role: "",
    source: "",
    canvas: DEFAULT_STILL_CANVAS,
    file: "",
    conditions: "",
    lookLock: "",
    lockFromStill: "",
    forbidden: "",
    notes: "",
  };
}

export function emptyContinuity(): ContinuityRow {
  return {
    id: uid(),
    take: "",
    hop: "",
    seed: "",
    wallS: "",
    peakC: "",
    ffprobe: "",
    stillVsLock: "",
    circleNg: "",
    why: "",
  };
}

export function nextTakeLetter(takes: TakeCard[]): string {
  const used = new Set(takes.map((row) => row.take.trim().toUpperCase()));
  for (let i = 0; i < 26; i += 1) {
    const letter = String.fromCharCode(65 + i);
    if (!used.has(letter)) return letter;
  }
  return `T${takes.length + 1}`;
}

export function emptyPack(): CapturePack {
  return {
    title: "",
    logLine: "",
    durationTarget: "",
    songNarrativeClock: "",
    audioPath: "",
    speech: "",
    forbiddenGlobal: DEFAULT_GLOBAL_FORBIDDEN,
    map: [emptyMapRow()],
    takes: [emptyTake("A")],
    editList: [emptyEditRow()],
    characters: [emptyCharacter()],
    props: [emptyProp()],
    look: {
      styleLine: "",
      paletteGrade: "",
      era: "",
      lensGrain: "",
      extrasForbidden: DEFAULT_LOOK_FORBIDDEN,
    },
    stills: [emptyStill()],
    smokeNotes: DEFAULT_SMOKE_NOTES,
    continuityRows: [emptyContinuity()],
    polaroidPath: "",
  };
}

export function clonePack(pack: CapturePack): CapturePack {
  return structuredClone(pack);
}

/**
 * Still fields must be a path or `none` plus why.
 * Template: empty still fields must say `none` and why.
 * Wikipedia is not a still. `none.` is not a why.
 */
export function stillOk(value: string): boolean {
  const v = value.trim();
  if (!v) return false;
  if (/\bwikipedia\b/i.test(v)) return false;
  if (/^none\b/i.test(v)) {
    const rest = v.replace(/^none\b/i, "").replace(/^[\s.:;,!—-]+/, "");
    return /[a-zA-Z]/.test(rest);
  }
  return true;
}

export function mentionsResearch(text: string): boolean {
  return /\bresearch\b/i.test(text);
}

export function fileSlug(name: string, fallback: string): string {
  return slugify(name, fallback);
}
