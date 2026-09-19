import {
  CAMERA_VERBS,
  type CameraVerb,
} from "../types.ts";

/** Informal verbs the lessons treat as extra cameras, not official H3. */
export const INFORMAL_CAMERA_VERBS = [
  "zoom",
  "circle",
  "dolly",
  "crane",
  "roll",
  "handheld",
  "orbit",
] as const;

const ALL_DETECTABLE = [...CAMERA_VERBS, ...INFORMAL_CAMERA_VERBS];

function verbBoundary(verb: string): RegExp {
  return new RegExp(`(^|[^a-z])${verb}([^a-z]|$)`, "i");
}

/** Return every camera verb found in a free-text camera cell. */
export function detectCameraVerbs(text: string): string[] {
  const hay = text.trim();
  if (!hay) return [];
  const found: string[] = [];
  for (const verb of ALL_DETECTABLE) {
    if (verbBoundary(verb).test(hay)) found.push(verb);
  }
  return found;
}

export function isOfficialVerb(verb: string): verb is CameraVerb {
  return (CAMERA_VERBS as readonly string[]).includes(verb);
}

/**
 * Official H3: one verb, amplitude, speed.
 * "Pan and zoom and circle" is three rows or it is refused.
 */
export function cameraMush(text: string): string[] {
  return detectCameraVerbs(text);
}

export function isSingleOfficialCamera(text: string): boolean {
  const found = detectCameraVerbs(text);
  return found.length === 1 && isOfficialVerb(found[0]);
}

export function formatCameraCell(
  verb: CameraVerb | "",
  amplitude: string,
  speed: string,
): string {
  if (!verb) return "";
  const amp = amplitude.trim();
  const spd = speed.trim();
  const parts: string[] = [verb];
  if (amp) parts.push(amp);
  if (spd) parts.push(spd);
  return parts.join(", ");
}

export function defaultHold(join: string): string {
  if (join === "cut") return "no";
  if (join === "fadeblack") return "yes before fade";
  return "no";
}

export function holdOkForJoin(join: string, hold: string): boolean {
  const h = hold.trim().toLowerCase().replace(/\*/g, "").replace(/\s+/g, " ");
  if (!h) return false;
  const noHold = h === "no" || h === "no hold";
  const yesHold = h === "yes" || h === "yes before fade" || h === "yes before fadeblack";
  if (join === "cut" || join === "continue") return noHold;
  if (join === "fadeblack") return yesHold;
  return false;
}
