import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { emptyPack } from "./pack.ts";
import { sigilsSample } from "./sample.ts";
import {
  consumeLoadNote,
  LEGACY_STORAGE_KEY,
  loadStoredPack,
  migratePack,
  STORAGE_KEY,
} from "./storage.ts";

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

describe("pack storage v2", () => {
  it("exports a v2 key so v1 blobs are not read as current", () => {
    assert.equal(STORAGE_KEY, "smf.h3-longform-capture.pack.v2");
  });

  it("migrates v1 takes and stills without dropping rows", () => {
    const v1 = sigilsSample() as unknown as Record<string, unknown>;
    const takes = (v1.takes as Record<string, unknown>[]).map((row) => {
      const { hop1Mode: _mode, hop1Plate: _plate, hop1Planned: _planned, ...rest } = row;
      return { ...rest, t2vPlanned: true };
    });
    const stills = (v1.stills as Record<string, unknown>[]).map((row) => {
      const { conditions, ...rest } = row;
      return { ...rest, conditionsHop: conditions };
    });
    const migrated = migratePack({ ...v1, takes, stills });
    assert.ok(migrated);
    assert.equal(migrated.takes[0].hop1Planned, true);
    assert.equal(migrated.takes[0].hop1Mode, "t2v");
    assert.match(migrated.takes[0].hop1Plate, /v1 pack recorded T2V/);
    assert.equal(migrated.stills[0].conditions, "none");
    assert.equal(migrated.stills[0].role, "sheet");
    assert.equal(migrated.characters[0].stillCanvas, "1344×768");
    assert.equal("t2vPlanned" in migrated.takes[0], false);
    assert.equal("conditionsHop" in migrated.stills[0], false);
  });

  it("fills missing arrays from an incomplete v1 object", () => {
    const migrated = migratePack({
      title: "orphan",
      look: { styleLine: "" },
    });
    assert.ok(migrated);
    assert.equal(migrated.takes.length, emptyPack().takes.length);
    assert.equal(migrated.stills.length, emptyPack().stills.length);
    assert.equal(migrated.characters[0].stillSource, "");
  });

  it("keeps explicit empty arrays instead of resurrecting sample rows", () => {
    const migrated = migratePack({
      title: "blank-lists",
      look: { styleLine: "" },
      map: [],
      takes: [],
      editList: [],
      characters: [],
      props: [],
      stills: [],
      continuityRows: [],
    });
    assert.ok(migrated);
    assert.equal(migrated.map.length, 0);
    assert.equal(migrated.takes.length, 0);
    assert.equal(migrated.stills.length, 0);
    assert.equal(migrated.characters.length, 0);
  });

  it("coerces invalid audio and speech instead of false-greening", () => {
    const migrated = migratePack({
      title: "noise",
      look: { styleLine: "" },
      audioPath: "mastered-track-and-prompt-score",
      speech: "whisper",
    });
    assert.ok(migrated);
    assert.equal(migrated.audioPath, "");
    assert.equal(migrated.speech, "");
  });

  it("rejects non-packs", () => {
    assert.equal(migratePack(null), null);
    assert.equal(migratePack({ look: {} }), null);
  });

  it("does not clobber a corrupt v2 blob with the Sigils sample", () => {
    const store = installMemoryStorage();
    store.set(STORAGE_KEY, "{not-json");
    const pack = loadStoredPack();
    assert.ok(pack);
    assert.equal(pack.title, "");
    assert.match(consumeLoadNote() ?? "", /unreadable/);
    assert.equal(store.get(STORAGE_KEY), "{not-json");
  });

  it("migrates a v1 blob onto the v2 key with a note", () => {
    const store = installMemoryStorage();
    store.set(
      LEGACY_STORAGE_KEY,
      JSON.stringify({ v: 1, pack: { title: "old pack", look: { styleLine: "dusk" } } }),
    );
    const pack = loadStoredPack();
    assert.ok(pack);
    assert.equal(pack.title, "old pack");
    assert.equal(pack.look.styleLine, "dusk");
    assert.match(consumeLoadNote() ?? "", /Migrated a v1 pack/);
    assert.equal(store.has(LEGACY_STORAGE_KEY), false);
    assert.ok(store.get(STORAGE_KEY));
  });
});
