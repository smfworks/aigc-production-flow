import JSZip from "jszip";
import { packToFiles } from "./markdown.ts";
import { slugify } from "./pack.ts";
import type { CapturePack } from "../types.ts";

export async function packToZipBlob(pack: CapturePack): Promise<Blob> {
  const zip = new JSZip();
  const folder = `packs/${slugify(pack.title)}`;
  const files = packToFiles(pack);
  for (const [name, content] of Object.entries(files)) {
    zip.file(`${folder}/${name}`, content);
  }
  return zip.generateAsync({ type: "blob" });
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function zipFilename(pack: CapturePack, complete: boolean): string {
  const slug = slugify(pack.title);
  return complete ? `pack-${slug}.zip` : `pack-draft-${slug}.zip`;
}
