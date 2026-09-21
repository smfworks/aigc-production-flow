/**
 * Entity schedule — who/what must persist across which takes/windows.
 *
 * A filled schedule row pins a named character or prop onto matching edit
 * rows. The window is missing the entity when `entities` does not list it.
 * Identity-hold + `cut`/`fadeblack` also requires a plate still whose entity
 * is that name and whose conditions bind the window (or explicit none + why).
 * `continue` hop 2+ is the motion-context latent — no new plate.
 */

import {
  ENTITY_KINDS,
  type CapturePack,
  type EditRow,
  type EntityKind,
  type EntityScheduleRow,
} from "../types.ts";
import { filled, stillOk } from "./pack.ts";
import {
  cutPlateStills,
  hop1PlateStills,
  isHop1EditRow,
  isPlateRole,
} from "./stills.ts";

export function isEntityKind(value: string): value is EntityKind {
  return (ENTITY_KINDS as readonly string[]).includes(value);
}

export function parseEntityList(raw: string): string[] {
  return raw
    .split(/[,;/]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function rowHasEntity(row: EditRow, name: string): boolean {
  const target = name.trim().toLowerCase();
  if (!target) return false;
  return parseEntityList(row.entities).some((item) => item.toLowerCase() === target);
}

function knownTake(pack: CapturePack, take: string): boolean {
  const t = take.trim();
  if (!t) return false;
  if (t === "*") return true;
  return pack.takes.some((item) => item.take.trim() === t);
}

function namedEntities(pack: CapturePack): { kind: EntityKind; name: string }[] {
  const rows: { kind: EntityKind; name: string }[] = [];
  for (const card of pack.characters) {
    if (filled(card.name)) rows.push({ kind: "character", name: card.name.trim() });
  }
  for (const card of pack.props) {
    if (filled(card.name)) rows.push({ kind: "prop", name: card.name.trim() });
  }
  return rows;
}

export function isFilledSchedule(row: EntityScheduleRow): boolean {
  return filled(row.entityName) || filled(row.take) || (filled(row.windows) && row.windows.trim().toLowerCase() !== "all");
}

function tokenList(windows: string): string[] {
  return windows
    .split(/[,;]+/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
}

function rowNumberMatch(token: string, index: number): boolean {
  const n = index + 1;
  const cleaned = token.replace(/^#/, "").replace(/^row\s+/, "");
  if (/^\d+$/.test(cleaned)) return Number(cleaned) === n;
  const range = cleaned.match(/^(\d+)\s*[-–]\s*(\d+)$/);
  if (!range) return false;
  const start = Number(range[1]);
  const end = Number(range[2]);
  return n >= start && n <= end;
}

export function scheduleAppliesToRow(
  pack: CapturePack,
  schedule: EntityScheduleRow,
  index: number,
): boolean {
  const row = pack.editList[index];
  if (!row) return false;
  const take = schedule.take.trim();
  const rowTake = row.take.trim();
  if (!take || (take !== "*" && take !== rowTake)) return false;
  const windows = schedule.windows.trim().toLowerCase();
  if (!windows || windows === "all") return true;
  for (const token of tokenList(windows)) {
    if (token === "all") return true;
    if (token === "hop-1" && isHop1EditRow(pack, index)) return true;
    if (row.songT.trim().toLowerCase() === token) return true;
    if (rowNumberMatch(token, index)) return true;
  }
  return false;
}

function entityPlateForRow(pack: CapturePack, entityName: string, index: number): string {
  const row = pack.editList[index];
  if (!row) return "";
  const name = entityName.trim().toLowerCase();
  const bound = pack.stills.filter((card) => {
    if (!isPlateRole(card.role)) return false;
    if (card.entity.trim().toLowerCase() !== name) return false;
    if (card.role === "cut plate") {
      return cutPlateStills(pack, index + 1, row.take).some((item) => item.id === card.id);
    }
    if (card.role === "hop-1 plate") {
      return hop1PlateStills(pack, row.take).some((item) => item.id === card.id);
    }
    return false;
  });
  return bound[0]?.file ?? "";
}

export function missingIdentityHoldPlate(
  pack: CapturePack,
  schedule: EntityScheduleRow,
  index: number,
): string | null {
  if (!schedule.identityHold) return null;
  const row = pack.editList[index];
  if (!row) return null;
  if (row.join !== "cut" && row.join !== "fadeblack") return null;
  const file = entityPlateForRow(pack, schedule.entityName, index);
  if (stillOk(file)) return null;
  const n = index + 1;
  const name = schedule.entityName.trim() || "unnamed entity";
  if (row.join === "fadeblack") {
    return `${name} on #${n} fadeblack: identity hold needs a hop-1 plate bound to this entity (or none + why)`;
  }
  return `${name} on #${n} cut: identity hold needs a cut/hop-1 plate bound to this entity (or none + why)`;
}

export function entityScheduleProblems(pack: CapturePack): string[] {
  const problems: string[] = [];
  const filledRows = pack.entitySchedule.filter(isFilledSchedule);
  if (filledRows.length === 0) {
    return ["Entity schedule is empty. Say who persists on which takes/windows."];
  }
  const known = namedEntities(pack);
  for (const row of filledRows) {
    const label = filled(row.entityName) ? row.entityName.trim() : "unnamed entity";
    if (!isEntityKind(row.entityKind)) {
      problems.push(`${label}: kind must be character or prop`);
    }
    if (!filled(row.entityName)) {
      problems.push("Schedule row needs an entity name");
      continue;
    }
    const match = known.find(
      (item) =>
        item.name.toLowerCase() === row.entityName.trim().toLowerCase() &&
        (!row.entityKind || item.kind === row.entityKind),
    );
    if (!match) {
      problems.push(`${label}: not a named character or prop card`);
    }
    if (!filled(row.take) || !knownTake(pack, row.take)) {
      problems.push(`${label}: take must be a take letter or *`);
    }
    const windows = filled(row.windows) ? row.windows.trim() : "all";
    const matching = pack.editList
      .map((_, index) => index)
      .filter((index) => scheduleAppliesToRow(pack, { ...row, windows }, index));
    if (matching.length === 0) {
      problems.push(`${label}: no edit-list window matches take ${row.take.trim() || "?"} / ${windows}`);
      continue;
    }
    for (const index of matching) {
      const edit = pack.editList[index];
      if (!rowHasEntity(edit, row.entityName)) {
        problems.push(
          `${label} scheduled on #${index + 1} (take ${edit.take || "—"}, ${edit.join || "no join"}) but missing from that window's entities`,
        );
      }
      const plateGap = missingIdentityHoldPlate(pack, row, index);
      if (plateGap) problems.push(plateGap);
    }
  }
  for (const entity of known) {
    const scheduled = filledRows.some(
      (row) =>
        row.entityName.trim().toLowerCase() === entity.name.toLowerCase() &&
        (!row.entityKind || row.entityKind === entity.kind),
    );
    if (!scheduled) {
      problems.push(`${entity.name}: named ${entity.kind} is not on the entity schedule`);
    }
  }
  return problems;
}
