import type { QuickCast, QuickRelation, QuickShot, QuickShotStage, QuickStaging } from "./types.ts";

const WORD_ALIASES: Record<string, string> = {
  screen_left: "screen-left",
  screen_right: "screen-right",
  toward_camera: "toward camera",
  away_from_camera: "away from camera",
};

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : value == null ? "" : String(value).trim();
}

function token(value: unknown): string {
  return text(value).toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
}

function words(value: unknown): string {
  const key = token(value);
  if (!key) return "";
  return WORD_ALIASES[key] ?? key.replaceAll("_", " ");
}

function nameIndex(staging: QuickStaging | null | undefined, cast: QuickCast[] | null | undefined): Record<string, string> {
  const castById: Record<string, string> = {};
  for (const item of cast ?? []) {
    const id = text(item.id);
    const name = text(item.name);
    if (id && name) castById[id] = name;
  }
  const names: Record<string, string> = {};
  for (const scene of staging?.scenes ?? []) {
    for (const entity of scene.entities ?? []) {
      const id = text(entity.id);
      if (!id) continue;
      const castId = text(entity.cast_id);
      const label = text(entity.label);
      if (castId && castById[castId]) names[id] = castById[castId];
      else if (label) names[id] = label.slice(0, 80);
      else names[id] = id;
    }
  }
  for (const [id, name] of Object.entries(castById)) {
    if (!names[id]) names[id] = name;
  }
  return names;
}

function sceneFor(shot: QuickShot, staging: QuickStaging | null | undefined) {
  const scenes = staging?.scenes ?? [];
  const sceneId = text(shot.stage?.scene_id);
  const shotId = text(shot.id);
  const byId = scenes.find((scene) => sceneId && text(scene.id) === sceneId);
  if (byId) return byId;
  const byShot = scenes.find((scene) => shotId && (scene.shot_ids ?? []).some((id) => text(id) === shotId));
  if (byShot) return byShot;
  return scenes.length === 1 ? scenes[0] : undefined;
}

function relationsFor(shot: QuickShot, staging: QuickStaging | null | undefined): QuickRelation[] {
  const own = shot.stage?.relations ?? [];
  if (own.length) return own;
  return sceneFor(shot, staging)?.relations ?? [];
}

function blocksOf(stage: QuickShotStage | null | undefined) {
  if (!stage) return [];
  if (stage.start?.length) return stage.start;
  if (stage.end?.length) return stage.end;
  return [];
}

function placeWords(block: { x?: string; depth?: string; facing?: string; look?: string }): string {
  const bits = [words(block.x), words(block.depth)];
  const facing = token(block.facing);
  const look = token(block.look);
  if (look && look !== facing) bits.push(`looking ${words(look)}`);
  return bits.filter(Boolean).join(", ");
}

function relationPhrase(
  entityId: string,
  relations: QuickRelation[],
  names: Record<string, string>,
  depth: string,
): string {
  for (const rel of relations) {
    if (text(rel.a) !== entityId) continue;
    const otherId = text(rel.b);
    const other = names[otherId] || otherId;
    const word = words(rel.rel);
    if (!word || !other) continue;
    const gap = words(rel.gap);
    if (gap && gap !== depth) return `${gap} ${word} ${other}`;
    return `${word} ${other}`;
  }
  return "";
}

/** Compact read-only "who is where" line. Empty when the shot has no blocking. */
export function whoIsWhere(
  shot: QuickShot,
  staging?: QuickStaging | null,
  cast?: QuickCast[] | null,
): string {
  const blocks = blocksOf(shot.stage);
  if (!blocks.length) return "";
  const names = nameIndex(staging, cast);
  const relations = relationsFor(shot, staging);
  const parts: string[] = [];
  for (const block of blocks) {
    if (block.visible === false) continue;
    const id = text(block.id);
    if (!id) continue;
    const name = names[id] || id;
    const place = placeWords(block);
    const relation = relationPhrase(id, relations, names, words(block.depth));
    if (place && relation) parts.push(`${name}: ${place}, ${relation}`);
    else if (place) parts.push(`${name}: ${place}`);
    else if (relation) parts.push(`${name}: ${relation}`);
    else parts.push(name);
  }
  return parts.join("; ");
}
