import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  cameraMush,
  defaultHold,
  detectCameraVerbs,
  formatCameraCell,
  holdOkForJoin,
  isSingleOfficialCamera,
} from "./camera.ts";

describe("detectCameraVerbs", () => {
  it("finds one official verb", () => {
    assert.deepEqual(detectCameraVerbs("slow pan, small amplitude"), ["pan"]);
  });

  it("refuses pan and zoom and circle as three verbs", () => {
    const found = cameraMush("Pan and zoom and circle");
    assert.deepEqual(found, ["pan", "zoom", "circle"]);
    assert.equal(isSingleOfficialCamera("Pan and zoom and circle"), false);
  });

  it("treats push and pull as two verbs", () => {
    assert.deepEqual(detectCameraVerbs("push and pull"), ["push", "pull"]);
  });

  it("does not treat 'span' as pan", () => {
    assert.deepEqual(detectCameraVerbs("span of the hall"), []);
  });

  it("accepts a formatted single-verb cell", () => {
    const cell = formatCameraCell("tilt", "small", "slow");
    assert.equal(cell, "tilt, small, slow");
    assert.equal(isSingleOfficialCamera(cell), true);
  });

  it("rejects an empty camera cell", () => {
    assert.equal(isSingleOfficialCamera(""), false);
    assert.equal(isSingleOfficialCamera(formatCameraCell("", "small", "slow")), false);
  });
});

describe("hold vs join", () => {
  it("defaults cut to no hold and fadeblack to yes before fade", () => {
    assert.equal(defaultHold("cut"), "no");
    assert.equal(defaultHold("fadeblack"), "yes before fade");
    assert.equal(defaultHold("continue"), "no");
  });

  it("cut refuses a hold", () => {
    assert.equal(holdOkForJoin("cut", "no"), true);
    assert.equal(holdOkForJoin("cut", "**no**"), true);
    assert.equal(holdOkForJoin("cut", "yes before fade"), false);
    assert.equal(holdOkForJoin("cut", ""), false);
  });
});
