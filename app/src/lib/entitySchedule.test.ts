import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  entityScheduleProblems,
  missingIdentityHoldPlate,
  parseEntityList,
  rowHasEntity,
  scheduleAppliesToRow,
} from "./entitySchedule.ts";
import { clonePack, emptyEntitySchedule } from "./pack.ts";
import { sigilsGenerateReady, sigilsSample } from "./sample.ts";

describe("entity schedule", () => {
  it("parses comma-separated window casts", () => {
    assert.deepEqual(parseEntityList("smith, francisca; thrower"), ["smith", "francisca", "thrower"]);
  });

  it("the Sigils sample schedules named entities onto their windows", () => {
    assert.deepEqual(entityScheduleProblems(sigilsSample()), []);
    assert.deepEqual(entityScheduleProblems(sigilsGenerateReady()), []);
  });

  it("fails when a scheduled entity is missing from a required window", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.editList[1].entities = "francisca";
    const problems = entityScheduleProblems(pack);
    assert.ok(problems.some((item) => /smith scheduled on #2/.test(item)));
  });

  it("fails when identity hold at cut/fadeblack has no entity-bound plate", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.stills = pack.stills.filter((card) => card.entity !== "smith" || card.role !== "hop-1 plate");
    const smith = pack.entitySchedule.find((row) => row.entityName === "smith");
    assert.ok(smith);
    assert.equal(scheduleAppliesToRow(pack, smith, 0), true);
    assert.match(missingIdentityHoldPlate(pack, smith, 0) ?? "", /identity hold needs a hop-1 plate/i);
    const problems = entityScheduleProblems(pack);
    assert.ok(problems.some((item) => /smith on #1 fadeblack/.test(item)));
  });

  it("does not require a new plate on continue hop 2+", () => {
    const pack = clonePack(sigilsGenerateReady());
    const smith = pack.entitySchedule.find((row) => row.entityName === "smith");
    assert.ok(smith);
    assert.equal(pack.editList[1].join, "continue");
    assert.equal(missingIdentityHoldPlate(pack, smith, 1), null);
    assert.equal(rowHasEntity(pack.editList[1], "smith"), true);
  });

  it("fails an empty schedule", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.entitySchedule = [emptyEntitySchedule()];
    const problems = entityScheduleProblems(pack);
    assert.match(problems[0], /empty/i);
  });

  it("fails a named card that is not scheduled", () => {
    const pack = clonePack(sigilsGenerateReady());
    pack.entitySchedule = pack.entitySchedule.filter((row) => row.entityName !== "thrower");
    assert.ok(entityScheduleProblems(pack).some((item) => /thrower: named character is not on the entity schedule/.test(item)));
  });
});
