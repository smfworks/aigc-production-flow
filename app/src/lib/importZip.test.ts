import assert from "node:assert/strict";
import { describe, it } from "node:test";
import JSZip from "jszip";
import { packToZipBlob, zipFilename } from "./exportZip.ts";
import { packFromZipBlob } from "./importZip.ts";
import { clonePack } from "./pack.ts";
import { sigilsSample } from "./sample.ts";

describe("zip round-trip", () => {
  it("round-trips pack.json from an exported zip", async () => {
    const original = sigilsSample();
    const blob = await packToZipBlob(original);
    const imported = await packFromZipBlob(blob);
    assert.equal(imported.title, original.title);
    assert.equal(imported.stills.length, original.stills.length);
    assert.equal(imported.props[0].fields.haftLength.value.startsWith("none"), true);
    assert.equal(imported.takes[0].hop1Mode, "t2v");
  });

  it("rejects a zip without pack.json", async () => {
    const zip = new JSZip();
    zip.file("README.md", "# Capture pack — orphan\n");
    const blob = await zip.generateAsync({ type: "blob" });
    await assert.rejects(() => packFromZipBlob(blob), /pack\.json/);
  });

  it("names empty titles untitled-pack and strips special characters", () => {
    const emptyTitle = clonePack(sigilsSample());
    emptyTitle.title = "";
    assert.equal(zipFilename(emptyTitle, false), "pack-draft-untitled-pack.zip");
    emptyTitle.title = 'Sigils: "Steel"/Axe?';
    assert.equal(zipFilename(emptyTitle, true), "pack-sigils-steel-axe.zip");
  });
});
