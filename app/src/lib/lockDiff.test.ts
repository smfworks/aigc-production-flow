import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { clonePack } from "./pack.ts";
import { sigilsGenerateReady, sigilsSample } from "./sample.ts";
import { collectLockTexts, diffLockTexts, lockDiffProblems, tokenizeLock } from "./lockDiff.ts";

describe("lock-diff rule (transparent synonyms)", () => {
  it("tokenizes lock text on letters and digits", () => {
    assert.deepEqual(tokenizeLock("Brown hair, 45 cm"), ["brown", "hair", "45", "cm"]);
  });

  it("passes the Sigils sample — no rotating synonyms", () => {
    assert.deepEqual(lockDiffProblems(sigilsSample()), []);
    assert.deepEqual(lockDiffProblems(sigilsGenerateReady()), []);
  });

  it("fails brown vs brunette on the same entity", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.characters[0].lockParagraph = "Same face, brown hair, and wardrobe every hop.";
    const plate = pack.stills.find((card) => card.entity === "smith" && card.role === "hop-1 plate");
    assert.ok(plate);
    plate.lockFromStill = "Brunette hair, same wardrobe as the sheet.";
    const problems = lockDiffProblems(pack);
    assert.ok(problems.length >= 1);
    assert.match(problems[0].detail, /brown \/ brunette/i);
    assert.equal(problems[0].entityName, "smith");
  });

  it("does not compare different entities against each other", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.characters[0].lockParagraph = "Brown hair locked.";
    pack.characters[1].lockParagraph = "Brunette hair locked.";
    assert.equal(
      lockDiffProblems(pack).some((item) => item.entityName === "smith" && item.rightToken === "brunette"),
      false,
    );
  });

  it("fails cloak vs cape across card fields", () => {
    const problems = diffLockTexts([
      {
        entityName: "smith",
        entityKind: "character",
        source: "character lock paragraph",
        text: "Wool cloak, brown hair.",
      },
      {
        entityName: "smith",
        entityKind: "character",
        source: "character field Wardrobe",
        text: "Heavy cape over tunic.",
      },
    ]);
    assert.ok(problems.some((item) => /cloak \/ cape/.test(item.detail)));
  });

  it("ignores empty still locks on none files", () => {
    const pack = clonePack(sigilsSample());
    assert.ok(collectLockTexts(pack).every((row) => row.source !== "still hop-1 plate · smith"));
  });
});
