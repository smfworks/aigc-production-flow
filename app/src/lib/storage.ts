import { clonePack, emptyCharacter, emptyPack, emptyProp, emptyStill, emptyTake, uid } from "./pack.ts";
import {
  DEFAULT_GLOBAL_FORBIDDEN,
  DEFAULT_LOOK_FORBIDDEN,
  DEFAULT_SMOKE_NOTES,
  DEFAULT_STILL_CANVAS,
  type CapturePack,
  type CharacterCard,
  type ContinuityRow,
  type EditRow,
  type Hop1Mode,
  type LookCard,
  type MapRow,
  type PropCard,
  type StillCard,
  type StillRole,
  type StillSource,
  type TakeCard,
} from "../types.ts";
import { hop1ModeForPlate, isStillRole, isStillSource } from "./stills.ts";

export const STORAGE_KEY = "smf.h3-longform-capture.pack.v2";
export const LEGACY_STORAGE_KEY = "smf.h3-longform-capture.pack.v1";

type StoredV2 = {
  v: 2;
  pack: CapturePack;
};

type StoredV1 = {
  v: 1;
  pack: Record<string, unknown>;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asBool(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function migrateMap(row: unknown): MapRow {
  const rec = asRecord(row) ?? {};
  return {
    id: asString(rec.id, uid()),
    clock: asString(rec.clock),
    beat: asString(rec.beat),
    energy: asString(rec.energy),
  };
}

function migrateTake(row: unknown): TakeCard {
  const rec = asRecord(row) ?? {};
  const planned = asBool(rec.hop1Planned, asBool(rec.t2vPlanned));
  const plate = asString(rec.hop1Plate);
  let mode = asString(rec.hop1Mode) as Hop1Mode | "";
  if (mode !== "i2va" && mode !== "t2v") {
    mode = hop1ModeForPlate(plate);
    if (!mode && planned) mode = "t2v";
  }
  let hop1Plate = plate;
  if (!hop1Plate && mode === "t2v") {
    hop1Plate = "none — v1 pack recorded T2V hop-1; add a plate still to switch to I2VA";
  }
  const base = emptyTake(asString(rec.take, "A"));
  return {
    ...base,
    id: asString(rec.id, base.id),
    take: asString(rec.take, base.take),
    location: asString(rec.location),
    grade: asString(rec.grade),
    windows: asString(rec.windows),
    prefix: asString(rec.prefix),
    hop1Seed: asString(rec.hop1Seed),
    hop1Mode: mode,
    hop1Plate,
    hop1Planned: planned,
    watched: asBool(rec.watched),
  };
}

function migrateEdit(row: unknown): EditRow {
  const rec = asRecord(row) ?? {};
  return {
    id: asString(rec.id, uid()),
    songT: asString(rec.songT),
    durS: asString(rec.durS),
    join: (asString(rec.join) as EditRow["join"]) || "",
    take: asString(rec.take),
    locationGrade: asString(rec.locationGrade),
    cameraVerb: (asString(rec.cameraVerb) as EditRow["cameraVerb"]) || "",
    cameraAmplitude: asString(rec.cameraAmplitude),
    cameraSpeed: asString(rec.cameraSpeed),
    action: asString(rec.action),
    hold: asString(rec.hold),
    notes: asString(rec.notes),
  };
}

function migrateCharacter(row: unknown): CharacterCard {
  const rec = asRecord(row) ?? {};
  const base = emptyCharacter();
  const source = asString(rec.stillSource);
  return {
    ...base,
    id: asString(rec.id, base.id),
    name: asString(rec.name),
    stillFile: asString(rec.stillFile),
    stillSource: isStillSource(source) ? source : "",
    stillCanvas: asString(rec.stillCanvas, DEFAULT_STILL_CANVAS),
    speakerId: asString(rec.speakerId, "none"),
    ageSex: asString(rec.ageSex),
    faceHairBeard: asString(rec.faceHairBeard),
    body: asString(rec.body),
    wardrobe: asString(rec.wardrobe),
    footwear: asString(rec.footwear),
    distinguishingMarks: asString(rec.distinguishingMarks),
    eraForbiddenModern: asString(rec.eraForbiddenModern),
    lockParagraph: asString(rec.lockParagraph),
    forbidden: asString(rec.forbidden, base.forbidden),
    motionNotes: asString(rec.motionNotes),
  };
}

function migrateProp(row: unknown): PropCard {
  const rec = asRecord(row) ?? {};
  const base = emptyProp();
  const source = asString(rec.stillSource);
  const fields = asRecord(rec.fields) ?? {};
  const next = { ...base.fields };
  for (const key of Object.keys(next) as (keyof typeof next)[]) {
    const m = asRecord(fields[key]);
    if (!m) continue;
    next[key] = {
      value: asString(m.value, next[key].value),
      unit: asString(m.unit, next[key].unit),
      source: asString(m.source, next[key].source),
    };
  }
  return {
    ...base,
    id: asString(rec.id, base.id),
    name: asString(rec.name),
    stillFile: asString(rec.stillFile),
    stillSource: isStillSource(source) ? source : "",
    stillCanvas: asString(rec.stillCanvas, DEFAULT_STILL_CANVAS),
    fields: next,
    lockParagraph: asString(rec.lockParagraph),
    forbidden: asString(rec.forbidden, base.forbidden),
  };
}

function migrateStill(row: unknown): StillCard {
  const rec = asRecord(row) ?? {};
  const base = emptyStill();
  const role = asString(rec.role);
  const source = asString(rec.source);
  return {
    ...base,
    id: asString(rec.id, base.id),
    entity: asString(rec.entity),
    role: isStillRole(role) ? (role as StillRole) : "",
    source: isStillSource(source) ? (source as StillSource) : "",
    canvas: asString(rec.canvas, DEFAULT_STILL_CANVAS),
    file: asString(rec.file),
    conditions: asString(rec.conditions, asString(rec.conditionsHop)),
    lookLock: asString(rec.lookLock),
    lockFromStill: asString(rec.lockFromStill),
    forbidden: asString(rec.forbidden),
    notes: asString(rec.notes),
  };
}

function migrateContinuity(row: unknown): ContinuityRow {
  const rec = asRecord(row) ?? {};
  return {
    id: asString(rec.id, uid()),
    take: asString(rec.take),
    hop: asString(rec.hop),
    seed: asString(rec.seed),
    wallS: asString(rec.wallS),
    peakC: asString(rec.peakC),
    ffprobe: asString(rec.ffprobe),
    stillVsLock: asString(rec.stillVsLock),
    circleNg: asString(rec.circleNg),
    why: asString(rec.why),
  };
}

function migrateLook(row: unknown): LookCard {
  const rec = asRecord(row) ?? {};
  return {
    styleLine: asString(rec.styleLine),
    paletteGrade: asString(rec.paletteGrade),
    era: asString(rec.era),
    lensGrain: asString(rec.lensGrain),
    extrasForbidden: asString(rec.extrasForbidden, DEFAULT_LOOK_FORBIDDEN),
  };
}

export function migratePack(raw: unknown): CapturePack | null {
  const rec = asRecord(raw);
  if (!rec) return null;
  if (typeof rec.title !== "string") return null;
  const look = rec.look;
  if (!look || typeof look !== "object") return null;
  const blank = emptyPack();
  return {
    title: asString(rec.title),
    logLine: asString(rec.logLine),
    durationTarget: asString(rec.durationTarget),
    songNarrativeClock: asString(rec.songNarrativeClock),
    audioPath: (asString(rec.audioPath) as CapturePack["audioPath"]) || "",
    speech: (asString(rec.speech) as CapturePack["speech"]) || "",
    forbiddenGlobal: asString(rec.forbiddenGlobal, DEFAULT_GLOBAL_FORBIDDEN),
    map: asArray(rec.map).map(migrateMap),
    takes: asArray(rec.takes).length ? asArray(rec.takes).map(migrateTake) : blank.takes,
    editList: asArray(rec.editList).length ? asArray(rec.editList).map(migrateEdit) : blank.editList,
    characters: asArray(rec.characters).length
      ? asArray(rec.characters).map(migrateCharacter)
      : blank.characters,
    props: asArray(rec.props).length ? asArray(rec.props).map(migrateProp) : blank.props,
    look: migrateLook(look),
    stills: asArray(rec.stills).length ? asArray(rec.stills).map(migrateStill) : blank.stills,
    smokeNotes: asString(rec.smokeNotes, DEFAULT_SMOKE_NOTES),
    continuityRows: asArray(rec.continuityRows).length
      ? asArray(rec.continuityRows).map(migrateContinuity)
      : blank.continuityRows,
    polaroidPath: asString(rec.polaroidPath),
  };
}

function readRaw(key: string): unknown {
  if (typeof localStorage === "undefined") return null;
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  return JSON.parse(raw);
}

export function loadStoredPack(): CapturePack | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const v2 = readRaw(STORAGE_KEY) as StoredV2 | null;
    if (v2?.v === 2) {
      const pack = migratePack(v2.pack);
      return pack ? clonePack(pack) : null;
    }
    const v1 = readRaw(LEGACY_STORAGE_KEY) as StoredV1 | null;
    if (v1?.v === 1) {
      const pack = migratePack(v1.pack);
      if (!pack) return null;
      const cloned = clonePack(pack);
      saveStoredPack(cloned);
      localStorage.removeItem(LEGACY_STORAGE_KEY);
      return cloned;
    }
    return null;
  } catch {
    return null;
  }
}

export function saveStoredPack(pack: CapturePack): void {
  if (typeof localStorage === "undefined") return;
  try {
    const payload: StoredV2 = { v: 2, pack };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // QuotaExceeded or private mode — keep working in-memory.
  }
}

export function clearStoredPack(): void {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(LEGACY_STORAGE_KEY);
}

export function initialPack(sample: CapturePack): CapturePack {
  return loadStoredPack() ?? clonePack(sample);
}

export { emptyPack };
