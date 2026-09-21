import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import { evaluateGates } from "./gate.ts";
import {
  WIPE_PROMPTS,
  packAfterConfirmedWipe,
  type WipeKind,
} from "./confirmWipe.ts";
import { loadStoredPack, saveStoredPack, STORAGE_KEY } from "./storage.ts";

function installMemoryStorage(): Map<string, string> {
  const store = new Map<string, string>();
  const memory = {
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null;
    },
    setItem(key: string, value: string) {
      store.set(key, value);
    },
    removeItem(key: string) {
      store.delete(key);
    },
    clear() {
      store.clear();
    },
    key() {
      return null;
    },
    get length() {
      return store.size;
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: memory,
    configurable: true,
  });
  return store;
}

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      sourceFiles(path, out);
    } else if (/\.(tsx|ts)$/.test(name) && !name.endsWith(".test.ts")) {
      out.push(path);
    }
  }
  return out;
}

describe("in-app wipe confirm", () => {
  it("asks before New pack, Load sample, and Import zip", () => {
    const kinds: WipeKind[] = ["new-pack", "load-sample", "import-zip"];
    for (const kind of kinds) {
      const prompt = WIPE_PROMPTS[kind];
      assert.ok(prompt.title.trim().length > 0);
      assert.match(prompt.message, /overwritten/i);
      assert.ok(prompt.confirmLabel.trim().length > 0);
    }
    assert.match(WIPE_PROMPTS["new-pack"].title, /blank pack/i);
    assert.match(WIPE_PROMPTS["load-sample"].title, /Sigils lessons sample/);
  });

  it("a confirmed New pack is blank, including Look, and persists", () => {
    const store = installMemoryStorage();
    const pack = packAfterConfirmedWipe("new-pack");
    assert.equal(pack.title, "");
    assert.equal(pack.look.styleLine, "");
    assert.equal(pack.look.paletteGrade, "");
    assert.equal(pack.look.era, "");
    assert.equal(pack.look.lensGrain, "");
    assert.equal(evaluateGates(pack).every((row) => !row.ok), true);
    assert.equal(evaluateGates(pack).find((row) => row.id === "look")?.ok, false);

    saveStoredPack(pack);
    const loaded = loadStoredPack();
    assert.ok(loaded);
    assert.equal(loaded.title, "");
    assert.equal(loaded.look.styleLine, "");
    assert.equal(store.has(STORAGE_KEY), true);
    const raw = JSON.parse(store.get(STORAGE_KEY) ?? "{}") as {
      v?: number;
      pack?: { look?: { styleLine?: string } };
    };
    assert.equal(raw.v, 2);
    assert.equal(raw.pack?.look?.styleLine, "");
  });

  it("a confirmed Load sample is the Sigils lessons pack, not a blank", () => {
    const pack = packAfterConfirmedWipe("load-sample");
    assert.equal(pack.title, "Sigils in the Steel");
    assert.notEqual(pack.look.styleLine, "");
  });

  it("the pack builder does not call the browser confirm dialog", () => {
    const src = join(dirname(fileURLToPath(import.meta.url)), "..");
    const hits = sourceFiles(src).filter((file) =>
      readFileSync(file, "utf8").includes("window.confirm"),
    );
    assert.deepEqual(hits, []);
    const app = readFileSync(join(src, "App.tsx"), "utf8");
    assert.match(app, /ConfirmDialog/);
    assert.match(app, /setPendingWipe\(\{ kind: "new-pack" \}\)/);
    assert.match(app, /setPendingWipe\(\{ kind: "load-sample" \}\)/);
    assert.match(app, /setPendingWipe\(\{ kind: "import-zip", file \}\)/);
    assert.match(app, /packAfterConfirmedWipe\(pendingWipe\.kind\)/);
    assert.match(app, /WIPE_PROMPTS\[pendingWipe\.kind\]/);
  });
});
