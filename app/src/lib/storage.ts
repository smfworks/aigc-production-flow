import { clonePack, emptyPack } from "./pack.ts";
import type { CapturePack } from "../types.ts";

export const STORAGE_KEY = "smf.h3-longform-capture.pack.v1";

type Stored = {
  v: 1;
  pack: CapturePack;
};

function isPack(value: unknown): value is CapturePack {
  if (!value || typeof value !== "object") return false;
  const pack = value as CapturePack;
  return (
    typeof pack.title === "string" &&
    Array.isArray(pack.map) &&
    Array.isArray(pack.takes) &&
    Array.isArray(pack.editList) &&
    Array.isArray(pack.characters) &&
    Array.isArray(pack.props) &&
    pack.look !== undefined &&
    typeof pack.look.styleLine === "string"
  );
}

export function loadStoredPack(): CapturePack | null {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Stored;
    if (parsed?.v !== 1 || !isPack(parsed.pack)) return null;
    return clonePack(parsed.pack);
  } catch {
    return null;
  }
}

export function saveStoredPack(pack: CapturePack): void {
  if (typeof localStorage === "undefined") return;
  const payload: Stored = { v: 1, pack };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function clearStoredPack(): void {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}

export function initialPack(sample: CapturePack): CapturePack {
  return loadStoredPack() ?? clonePack(sample);
}

export { emptyPack };
