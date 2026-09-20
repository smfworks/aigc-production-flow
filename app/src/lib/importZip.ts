import JSZip from "jszip";
import { migratePack } from "./storage.ts";
import type { CapturePack } from "../types.ts";

function basename(path: string): string {
  return path.replace(/\\/g, "/").split("/").pop() ?? path;
}

export async function packFromZipBlob(blob: Blob): Promise<CapturePack> {
  const zip = await JSZip.loadAsync(blob);
  const jsonPath = Object.keys(zip.files).find((name) => {
    const file = zip.files[name];
    return !file.dir && basename(name) === "pack.json";
  });
  if (!jsonPath) {
    throw new Error("No pack.json in this zip. Re-export from this app to round-trip.");
  }
  const text = await zip.files[jsonPath].async("string");
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("pack.json is not valid JSON.");
  }
  const rec = parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : null;
  const raw = rec?.pack ?? parsed;
  const pack = migratePack(raw);
  if (!pack) throw new Error("pack.json is not a capture pack.");
  return pack;
}
