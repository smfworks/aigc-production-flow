import {
  DEFAULT_STILL_CANVAS,
  STILL_ROLES,
  STILL_SOURCES,
  type CapturePack,
  type Hop1Mode,
  type StillCard,
  type StillRole,
  type StillSource,
  type TakeCard,
} from "../types.ts";
import { emptyStill, filled, stillOk } from "./pack.ts";

export function isStillRole(value: string): value is StillRole {
  return (STILL_ROLES as readonly string[]).includes(value);
}

export function isStillSource(value: string): value is StillSource {
  return (STILL_SOURCES as readonly string[]).includes(value);
}

export function isPlateRole(role: string): boolean {
  return role === "hop-1 plate" || role === "cut plate" || role === "last-frame";
}

export function isSheetRole(role: string): boolean {
  return role === "sheet";
}

export function isNoneStill(file: string): boolean {
  return /^none\b/i.test(file.trim());
}

/** Path that can condition `MiniMaxH3ImageToVideo.first_frame`. */
export function isRealStillFile(file: string): boolean {
  return stillOk(file) && !isNoneStill(file);
}

export function hop1ModeForPlate(plateFile: string): Hop1Mode | "" {
  if (!filled(plateFile)) return "";
  if (isNoneStill(plateFile)) return stillOk(plateFile) ? "t2v" : "";
  return stillOk(plateFile) ? "i2va" : "";
}

export function hop1ModeLabel(mode: Hop1Mode | ""): string {
  if (mode === "i2va") return "I2VA";
  if (mode === "t2v") return "T2V";
  return "";
}

export function normalizeCanvas(canvas: string): string {
  return canvas.trim().replace(/[xX×✕]/g, "×").replace(/\s+/g, "");
}

export function canvasMatchesHop1(canvas: string): boolean {
  return normalizeCanvas(canvas) === normalizeCanvas(DEFAULT_STILL_CANVAS);
}

export function canvasLooksStretched(canvas: string): boolean {
  return /1024/.test(canvas);
}

export function stillSourceAgrees(file: string, source: string): boolean {
  if (!isStillSource(source)) return false;
  if (!stillOk(file)) return false;
  if (source === "none") return isNoneStill(file);
  return !isNoneStill(file);
}

export function isBlankStill(card: StillCard): boolean {
  return (
    !filled(card.entity) &&
    !filled(card.role) &&
    !filled(card.source) &&
    !filled(card.file) &&
    !filled(card.conditions) &&
    !filled(card.lookLock) &&
    !filled(card.lockFromStill) &&
    !filled(card.forbidden) &&
    !filled(card.notes) &&
    (!filled(card.canvas) || canvasMatchesHop1(card.canvas))
  );
}

export function stillCardProblems(card: StillCard, lookLine = ""): string[] {
  const problems: string[] = [];
  const label = filled(card.entity) ? card.entity : "unnamed still";
  if (!filled(card.entity)) problems.push(`${label}: needs an entity`);
  if (!isStillRole(card.role)) {
    problems.push(`${label}: role must be sheet, hop-1 plate, cut plate, or last-frame`);
  }
  if (!isStillSource(card.source)) {
    problems.push(`${label}: source must be photo, qwen-t2i, qwen-edit, or none`);
  }
  if (!stillOk(card.file)) {
    problems.push(`${label}: file must be a path or none + why`);
  } else if (card.source && !stillSourceAgrees(card.file, card.source)) {
    problems.push(`${label}: source ${card.source} does not match file`);
  }
  if (!canvasMatchesHop1(card.canvas) || canvasLooksStretched(card.canvas)) {
    problems.push(`${label}: canvas must be ${DEFAULT_STILL_CANVAS} (do not stretch 1024²)`);
  }
  if (!filled(card.conditions)) {
    problems.push(`${label}: conditions (hop-1 of take _ / cut row _ / none)`);
  }
  if (isRealStillFile(card.file) && filled(lookLine)) {
    if (card.lookLock.trim() !== lookLine.trim()) {
      problems.push(`${label}: look lock must match look.md verbatim`);
    }
  }
  if (isRealStillFile(card.file) && !filled(card.lockFromStill)) {
    problems.push(`${label}: copy the lock from this still (do not invent after)`);
  }
  return problems;
}

export function takeKey(take: string): string {
  return take.trim().toUpperCase();
}

function takeToken(take: string): string | null {
  const t = takeKey(take);
  if (!t || t === "—" || t === "-") return null;
  return t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function conditionsMentionsTake(conditions: string, take: string): boolean {
  const token = takeToken(take);
  if (!token) return false;
  return new RegExp(`(?:\\btake\\s*${token}\\b|\\bhop-1\\s+of\\s+(?:take\\s*)?${token}\\b)`, "i").test(
    conditions,
  );
}

export function conditionsMentionsCutRow(conditions: string, n: number): boolean {
  return new RegExp(`\\bcut\\s*(?:row|#)?\\s*${n}\\b`, "i").test(conditions);
}

export function takeFromConditions(conditions: string): string {
  const match = conditions.match(/\b(?:take|hop-1 of(?: take)?)\s*([A-Za-z0-9-]+)\b/i);
  return match?.[1]?.toLowerCase() ?? "";
}

export function cutRowFromConditions(conditions: string): string {
  const match = conditions.match(/\bcut\s*(?:row|#)?\s*(\d+)\b/i);
  return match?.[1] ?? "";
}

export function hop1PlateStills(pack: CapturePack, take: string): StillCard[] {
  return pack.stills.filter(
    (card) => card.role === "hop-1 plate" && conditionsMentionsTake(card.conditions, take),
  );
}

export function cutPlateStills(pack: CapturePack, rowNumber: number, take: string): StillCard[] {
  return pack.stills.filter((card) => {
    if (card.role !== "cut plate") return false;
    if (conditionsMentionsCutRow(card.conditions, rowNumber)) return true;
    return filled(take) && conditionsMentionsTake(card.conditions, take);
  });
}

export function sheetStillForEntity(pack: CapturePack, entity: string): StillCard | undefined {
  const name = entity.trim().toLowerCase();
  if (!name) return undefined;
  return pack.stills.find(
    (card) => card.role === "sheet" && card.entity.trim().toLowerCase() === name,
  );
}

export function isHop1EditRow(pack: CapturePack, index: number): boolean {
  const row = pack.editList[index];
  if (!row) return false;
  const take = row.take.trim();
  if (!take || take === "—" || take === "-") return row.join === "cut" || row.join === "fadeblack";
  return pack.editList.findIndex((item) => item.take.trim() === take) === index;
}

/**
 * continue hop 2+ is Motion-Context — no new Qwen still.
 * hop-1 / cut / fadeblack need a plate or explicit none + why.
 */
export function identityPlateNeeded(pack: CapturePack, index: number): boolean {
  const row = pack.editList[index];
  if (!row?.join) return false;
  if (row.join === "continue") return isHop1EditRow(pack, index);
  return row.join === "cut" || row.join === "fadeblack";
}

export function plateFileForTake(pack: CapturePack, take: TakeCard): string {
  if (filled(take.hop1Plate)) return take.hop1Plate;
  const fromStill = hop1PlateStills(pack, take.take)[0];
  return fromStill?.file ?? "";
}

export function applyStillsToTakes(pack: CapturePack): CapturePack {
  return {
    ...pack,
    takes: pack.takes.map((take) => {
      const plate = hop1PlateStills(pack, take.take)[0];
      if (!plate) return take;
      const mode = hop1ModeForPlate(plate.file);
      return {
        ...take,
        hop1Plate: plate.file,
        hop1Mode: mode || take.hop1Mode,
      };
    }),
  };
}

export function inUseStills(pack: CapturePack): StillCard[] {
  return pack.stills.filter((card) => !isBlankStill(card));
}

/** Plate file that conditions this edit row, if any. */
export function identityPlateFile(pack: CapturePack, index: number): string {
  const row = pack.editList[index];
  if (!row) return "";
  const take = pack.takes.find((item) => item.take.trim() === row.take.trim());
  const takePlate = take ? plateFileForTake(pack, take) : "";
  if (row.join === "continue" && isHop1EditRow(pack, index)) return takePlate;
  if (row.join === "fadeblack") return takePlate;
  if (row.join === "cut") {
    const cutStill = cutPlateStills(pack, index + 1, row.take)[0];
    if (cutStill && filled(cutStill.file)) return cutStill.file;
    if (isHop1EditRow(pack, index)) return takePlate;
    return "";
  }
  return "";
}

export function missingIdentityPlate(pack: CapturePack, index: number): string | null {
  if (!identityPlateNeeded(pack, index)) return null;
  const file = identityPlateFile(pack, index);
  if (stillOk(file)) return null;
  const row = pack.editList[index];
  const n = index + 1;
  if (row.join === "continue") return `#${n} continue hop-1 needs a plate (or none + why)`;
  if (row.join === "fadeblack") {
    return `#${n} fadeblack hop-1 needs a plate in the new location/grade (or none + why)`;
  }
  if (row.join === "cut") return `#${n} cut needs a plate → I2VA (or none + why)`;
  return `#${n} needs a plate (or none + why)`;
}

export function ensureSheetStill(
  pack: CapturePack,
  entity: string,
  file: string,
  source: StillSource | "",
  canvas: string,
): CapturePack {
  const name = entity.trim();
  if (!name) return pack;
  if (sheetStillForEntity(pack, name)) return pack;
  const card: StillCard = {
    ...emptyStill(),
    entity: name,
    role: "sheet",
    source: isStillSource(source) ? source : file && !isNoneStill(file) ? "qwen-t2i" : "none",
    canvas: canvas || DEFAULT_STILL_CANVAS,
    file,
    conditions: "none",
    lookLock: pack.look.styleLine,
  };
  const stills = [...pack.stills.filter((row) => !isBlankStill(row)), card];
  return { ...pack, stills };
}

export function ensurePlateStill(pack: CapturePack, index: number): CapturePack {
  const row = pack.editList[index];
  if (!row?.join) return pack;
  if (row.join === "cut") {
    if (cutPlateStills(pack, index + 1, row.take).length) return pack;
    const card: StillCard = {
      ...emptyStill(),
      entity: `cut ${index + 1}`,
      role: "cut plate",
      conditions: `cut row ${index + 1}`,
    };
    return { ...pack, stills: [...pack.stills.filter((item) => !isBlankStill(item)), card] };
  }
  if (row.join === "fadeblack" || (row.join === "continue" && isHop1EditRow(pack, index))) {
    const take = row.take.trim();
    if (!take || hop1PlateStills(pack, take).length) return pack;
    const card: StillCard = {
      ...emptyStill(),
      entity: `take ${take} hop-1`,
      role: "hop-1 plate",
      conditions: `hop-1 of take ${take}`,
    };
    return { ...pack, stills: [...pack.stills.filter((item) => !isBlankStill(item)), card] };
  }
  return pack;
}
