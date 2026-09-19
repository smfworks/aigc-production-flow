import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { allGatesGreen, evaluateGates, GATE_DEFS, propGenerateFlags } from "./gate.ts";
import { clonePack, emptyPack, stillOk } from "./pack.ts";
import { sigilsGenerateReady, sigilsSample } from "./sample.ts";
import type { CapturePack } from "../types.ts";

function gate(pack: CapturePack, id: string) {
  const found = evaluateGates(pack).find((row) => row.id === id);
  assert.ok(found, `missing gate ${id}`);
  return found;
}

describe("nine README gates", () => {
  it("exposes nine gates in README order", () => {
    assert.equal(GATE_DEFS.length, 9);
    assert.deepEqual(
      GATE_DEFS.map((row) => row.n),
      [1, 2, 3, 4, 5, 6, 7, 8, 9],
    );
  });

  it("an empty pack is all red, including Look", () => {
    const pack = emptyPack();
    const gates = evaluateGates(pack);
    assert.equal(gates.every((row) => !row.ok), true);
    assert.equal(allGatesGreen(pack), false);
    assert.equal(pack.look.styleLine, "");
    assert.equal(gate(pack, "look").ok, false);
    assert.equal(gate(pack, "log-line").ok, false);
    assert.equal(gate(pack, "map").ok, false);
    assert.equal(gate(pack, "audio").ok, false);
  });

  it("the Sigils lessons sample does not claim generate-ready", () => {
    const pack = sigilsSample();
    const red = evaluateGates(pack).filter((row) => !row.ok);
    assert.equal(allGatesGreen(pack), false);
    assert.equal(red.length, 1);
    assert.equal(red[0].id, "props");
    assert.equal(propGenerateFlags(pack.props[0]).overallHaftUnresolved, true);
  });

  it("a numeric-haft stand-in can clear all nine", () => {
    const pack = sigilsGenerateReady();
    const red = evaluateGates(pack).filter((row) => !row.ok);
    assert.deepEqual(red, []);
    assert.equal(allGatesGreen(pack), true);
  });
});

describe("gate 2 map is clocks not shots", () => {
  it("rejects a shot-list disguised as a map", () => {
    const pack = clonePack(sigilsSample());
    pack.map[0] = { ...pack.map[0], clock: "shot 1", beat: "CU of axe" };
    assert.equal(gate(pack, "map").ok, false);
    assert.match(gate(pack, "map").detail, /not shots/i);
  });
});

describe("gate 3 edit list", () => {
  it("refuses a row with no join", () => {
    const pack = clonePack(sigilsSample());
    pack.editList[0] = { ...pack.editList[0], join: "" };
    assert.equal(gate(pack, "edit-list").ok, false);
  });

  it("refuses multi-verb mush on a row", () => {
    const pack = clonePack(sigilsSample());
    pack.editList[0] = {
      ...pack.editList[0],
      cameraVerb: "pan",
      cameraAmplitude: "zoom",
      cameraSpeed: "circle",
    };
    assert.equal(gate(pack, "edit-list").ok, false);
    assert.match(gate(pack, "edit-list").detail, /one official camera verb/i);
  });

  it("refuses a cut with a hold", () => {
    const pack = clonePack(sigilsSample());
    const cut = pack.editList.find((row) => row.join === "cut");
    assert.ok(cut);
    cut.hold = "yes before fade";
    assert.equal(gate(pack, "edit-list").ok, false);
  });

  it("refuses continue with a hold", () => {
    const pack = clonePack(sigilsSample());
    const cont = pack.editList.find((row) => row.join === "continue");
    assert.ok(cont);
    cont.hold = "yes before fade";
    assert.equal(gate(pack, "edit-list").ok, false);
    assert.match(gate(pack, "edit-list").detail, /continue must hold = no/i);
  });

  it("refuses an empty action", () => {
    const pack = clonePack(sigilsSample());
    pack.editList[0] = { ...pack.editList[0], action: "" };
    assert.equal(gate(pack, "edit-list").ok, false);
    assert.match(gate(pack, "edit-list").detail, /action/i);
  });

  it("refuses stripped songT / take / locationGrade", () => {
    const pack = clonePack(sigilsSample());
    pack.editList[0] = {
      ...pack.editList[0],
      songT: "",
      take: "",
      locationGrade: "",
    };
    assert.equal(gate(pack, "edit-list").ok, false);
    assert.match(gate(pack, "edit-list").detail, /song t/i);
  });

  it("refuses a verb with empty amplitude or speed", () => {
    const pack = clonePack(sigilsSample());
    pack.editList[1] = {
      ...pack.editList[1],
      cameraAmplitude: "",
      cameraSpeed: "",
    };
    assert.equal(gate(pack, "edit-list").ok, false);
    assert.match(gate(pack, "edit-list").detail, /amplitude \+ speed/i);
  });
});

describe("gate 6 prop cards", () => {
  it("fails when overall vs haft is blank", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.props[0].fields.haftLength.value = "";
    assert.equal(gate(pack, "props").ok, false);
    assert.match(gate(pack, "props").detail, /haft/i);
  });

  it("fails TBD / unknown as pinned lengths", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.props[0].fields.overallLength.value = "TBD";
    pack.props[0].fields.haftLength.value = "unknown";
    assert.equal(propGenerateFlags(pack.props[0]).overallHaftUnresolved, true);
    assert.equal(gate(pack, "props").ok, false);
    assert.match(gate(pack, "props").detail, /haft/i);
  });

  it("fails none — … as a haft pin", () => {
    const pack = clonePack(sigilsSample());
    assert.equal(pack.props[0].fields.haftLength.value.startsWith("none"), true);
    assert.equal(propGenerateFlags(pack.props[0]).overallHaftUnresolved, true);
    assert.equal(gate(pack, "props").ok, false);
  });

  it("fails a still of none with no why", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.props[0].stillFile = "none";
    assert.equal(stillOk("none"), false);
    assert.equal(gate(pack, "props").ok, false);
  });

  it("fails none. as a still why", () => {
    assert.equal(stillOk("none."), false);
    const pack = clonePack(sigilsGenerateReady());
    pack.props[0].stillFile = "none.";
    assert.equal(gate(pack, "props").ok, false);
  });

  it("fails Wikipedia as a still", () => {
    assert.equal(stillOk("https://en.wikipedia.org/wiki/Francisca"), false);
    const pack = clonePack(sigilsGenerateReady());
    pack.props[0].stillFile = "https://en.wikipedia.org/wiki/Francisca";
    assert.equal(gate(pack, "props").ok, false);
  });

  it("refuses research-at-generate-time language", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.props[0].lockParagraph = "research the Merovingian axe on Wikipedia";
    assert.equal(gate(pack, "props").ok, false);
    assert.match(gate(pack, "props").detail, /research/i);
  });
});

describe("gate 8 audio path is exclusive", () => {
  it("fails when unset", () => {
    const pack = clonePack(sigilsSample());
    pack.audioPath = "";
    assert.equal(gate(pack, "audio").ok, false);
  });

  it("accepts each of the three paths", () => {
    for (const path of ["na-mute", "prompt-score", "silence"] as const) {
      const pack = clonePack(sigilsSample());
      pack.audioPath = path;
      assert.equal(gate(pack, "audio").ok, true, path);
    }
  });
});

describe("gate 9 smoke", () => {
  it("fails until every take is hop-1 planned and watched", () => {
    const pack = clonePack(sigilsSample());
    pack.takes[0].watched = false;
    assert.equal(gate(pack, "smoke").ok, false);
  });

  it("fails duplicate prefixes", () => {
    const pack = clonePack(sigilsSample());
    pack.takes[1].prefix = pack.takes[0].prefix;
    assert.equal(gate(pack, "smoke").ok, false);
  });
});
