import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { clonePack } from "./pack.ts";
import { sigilsGenerateReady } from "./sample.ts";
import {
  applyStillsToTakes,
  canvasLooksStretched,
  canvasMatchesHop1,
  ensureSheetStill,
  hop1ModeForPlate,
  identityPlateNeeded,
  isHop1EditRow,
  isRealStillFile,
  missingIdentityPlate,
  stillCardProblems,
  stillSourceAgrees,
  takeFromConditions,
} from "./stills.ts";

describe("sheet vs plate helpers", () => {
  it("maps a plate path to I2VA and none+why to T2V", () => {
    assert.equal(hop1ModeForPlate("stills/a-hop1-plate.png"), "i2va");
    assert.equal(hop1ModeForPlate("none — T2V until a plate exists"), "t2v");
    assert.equal(hop1ModeForPlate(""), "");
    assert.equal(isRealStillFile("stills/a-hop1-plate.png"), true);
    assert.equal(isRealStillFile("none — why"), false);
  });

  it("rejects stretched 1024 canvases", () => {
    assert.equal(canvasMatchesHop1("1344×768"), true);
    assert.equal(canvasMatchesHop1("1344x768"), true);
    assert.equal(canvasLooksStretched("1024×1024"), true);
    assert.equal(canvasMatchesHop1("1024×1024"), false);
  });

  it("requires source none to match a none file", () => {
    assert.equal(stillSourceAgrees("none — no public still", "none"), true);
    assert.equal(stillSourceAgrees("stills/smith-sheet.png", "qwen-t2i"), true);
    assert.equal(stillSourceAgrees("stills/smith-sheet.png", "none"), false);
    assert.equal(stillSourceAgrees("none — why", "qwen-t2i"), false);
  });

  it("parses hop-1 take letters from conditions", () => {
    assert.equal(takeFromConditions("hop-1 of take A"), "a");
    assert.equal(takeFromConditions("hop-1 of take B"), "b");
  });

  it("treats continue hop 2+ as no new plate", () => {
    const pack = clonePack(sigilsGenerateReady());
    assert.equal(pack.editList[0].join, "fadeblack");
    assert.equal(isHop1EditRow(pack, 0), true);
    assert.equal(identityPlateNeeded(pack, 0), true);
    assert.equal(pack.editList[1].join, "continue");
    assert.equal(isHop1EditRow(pack, 1), false);
    assert.equal(identityPlateNeeded(pack, 1), false);
    assert.equal(pack.editList[2].join, "cut");
    assert.equal(identityPlateNeeded(pack, 2), true);
  });

  it("flags a 1024 sheet", () => {
    const pack = clonePack(sigilsGenerateReady());
    const sheet = pack.stills.find((card) => card.role === "sheet");
    assert.ok(sheet);
    sheet.canvas = "1024×1024";
    sheet.file = "stills/smith-sheet.png";
    sheet.source = "qwen-t2i";
    const problems = stillCardProblems(sheet, pack.look.styleLine);
    assert.ok(problems.some((item) => /1024/.test(item)));
  });

  it("copies hop-1 plates onto takes", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.takes[0].hop1Plate = "";
    pack.takes[0].hop1Mode = "";
    const next = applyStillsToTakes(pack);
    assert.match(next.takes[0].hop1Plate, /^none/);
    assert.equal(next.takes[0].hop1Mode, "t2v");
  });

  it("adds a matching sheet still from a character card", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.stills = pack.stills.filter((card) => card.entity !== "smith");
    const next = ensureSheetStill(
      pack,
      "smith",
      pack.characters[0].stillFile,
      pack.characters[0].stillSource,
      pack.characters[0].stillCanvas,
    );
    const sheet = next.stills.find((card) => card.role === "sheet" && card.entity === "smith");
    assert.ok(sheet);
    assert.equal(sheet.conditions, "none");
    assert.equal(sheet.lookLock, pack.look.styleLine);
    assert.equal(ensureSheetStill(next, "smith", "stills/other.png", "photo", "1344×768"), next);
  });

  it("reports a missing cut plate with none + why language", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.editList.push({
      ...pack.editList[2],
      id: "extra-cut",
      songT: "0:51",
    });
    assert.match(missingIdentityPlate(pack, pack.editList.length - 1) ?? "", /cut needs a plate/);
    assert.equal(missingIdentityPlate(pack, 1), null);
  });
});
