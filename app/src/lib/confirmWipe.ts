import { clonePack, emptyPack } from "./pack.ts";
import { sigilsSample } from "./sample.ts";
import type { CapturePack } from "../types.ts";

/** Destructive pack replacements. Each one must ask before it wipes autosave. */
export type WipeKind = "new-pack" | "load-sample" | "import-zip";

export type WipePrompt = {
  title: string;
  message: string;
  confirmLabel: string;
};

/**
 * In-page copy for wipe confirms.
 * These used to be browser confirm dialogs. A sandboxed iframe without
 * allow-modals (Hermes pane smf-h3-capture) blocks those, so the click
 * looked like a no-op. The ask stays; the dialog is drawn by the app.
 */
export const WIPE_PROMPTS: Record<WipeKind, WipePrompt> = {
  "new-pack": {
    title: "Start a new blank pack?",
    message: "Autosaved work in this browser will be overwritten.",
    confirmLabel: "New pack",
  },
  "load-sample": {
    title: "Replace the current pack with the Sigils lessons sample?",
    message: "Autosaved work in this browser will be overwritten.",
    confirmLabel: "Load sample",
  },
  "import-zip": {
    title: "Replace the current pack with this zip?",
    message: "Autosaved work in this browser will be overwritten.",
    confirmLabel: "Import zip",
  },
};

export function packAfterConfirmedWipe(kind: Exclude<WipeKind, "import-zip">): CapturePack {
  if (kind === "new-pack") return emptyPack();
  return clonePack(sigilsSample());
}
