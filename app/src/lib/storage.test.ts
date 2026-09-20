import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { emptyPack } from "./pack.ts";
import { sigilsSample } from "./sample.ts";
import { migratePack, STORAGE_KEY } from "./storage.ts";

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

  it("rejects non-packs", () => {
    assert.equal(migratePack(null), null);
    assert.equal(migratePack({ look: {} }), null);
  });
});
