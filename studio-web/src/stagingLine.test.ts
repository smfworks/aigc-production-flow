import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { whoIsWhere } from "./stagingLine.ts";
import type { ImagineShot, ImagineStaging } from "./types.ts";

const staging: ImagineStaging = {
  scenes: [
    {
      id: "sc1",
      shot_ids: ["s01", "s03"],
      travel: "screen_right",
      entities: [
        { id: "jack", label: "Jack on his buckskin horse", kind: "character", cast_id: "jack", count: 1 },
        { id: "bandits", label: "the three bandits on dark horses", kind: "group", cast_id: "bandits", count: 3 },
      ],
      relations: [{ a: "bandits", rel: "behind", b: "jack", gap: "far" }],
    },
  ],
};

const cast = [
  { id: "jack", name: "Jack", role: "character" },
  { id: "bandits", name: "the bandits", role: "character" },
];

describe("whoIsWhere", () => {
  it("reads start blocking and scene relations", () => {
    const shot: ImagineShot = {
      id: "s01",
      prompt_still: "wide",
      prompt_motion: "gallop",
      stage: {
        scene_id: "sc1",
        camera_side: "same",
        start: [
          { id: "jack", x: "right_third", depth: "mid", facing: "screen_right", travel: "screen_right", visible: true },
          { id: "bandits", x: "left_third", depth: "far", facing: "screen_right", travel: "screen_right", visible: true },
        ],
      },
    };
    assert.equal(
      whoIsWhere(shot, staging, cast),
      "Jack: right third, mid; the bandits: left third, far, behind Jack",
    );
  });

  it("shows a look that differs from facing", () => {
    const shot: ImagineShot = {
      id: "s03",
      prompt_still: "close",
      prompt_motion: "twists",
      stage: {
        scene_id: "sc1",
        camera_side: "same",
        start: [
          {
            id: "jack",
            x: "right_third",
            depth: "foreground",
            facing: "screen_right",
            look: "screen_left",
            travel: "screen_right",
            visible: true,
          },
        ],
      },
    };
    assert.equal(whoIsWhere(shot, staging, cast), "Jack: right third, foreground, looking screen-left");
  });

  it("is empty when Imagine returned no stage", () => {
    const shot: ImagineShot = { id: "s01", prompt_still: "wide", prompt_motion: "gallop" };
    assert.equal(whoIsWhere(shot, null, cast), "");
    assert.equal(whoIsWhere(shot, staging, cast), "");
  });
});
