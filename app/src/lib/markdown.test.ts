import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import {
  packToFiles,
  renderCharacter,
  renderContinuity,
  renderEditList,
  renderLook,
  renderProp,
  renderReadme,
} from "./markdown.ts";
import { emptyPack } from "./pack.ts";
import { sigilsGenerateReady, sigilsSample } from "./sample.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../..");

function template(name: string): string {
  return readFileSync(join(root, "templates", name), "utf8");
}

function headerLine(markdown: string, columns: string): void {
  assert.match(markdown, new RegExp(`^\\| ${columns} \\|$`, "m"));
}

describe("export matches template shapes", () => {
  it("README keeps capture-pack headings and tables", () => {
    const tpl = template("capture-pack.md");
    const out = renderReadme(sigilsSample());
    assert.match(tpl, /^# Capture pack — \{TITLE\}/m);
    assert.match(out, /^# Capture pack — Sigils in the Steel/m);
    assert.match(out, /Log line \(one sentence\):/);
    assert.match(out, /Audio path: \[x\] N\/A \+ mute in NLE/);
    assert.match(out, /\[ \] prompt score/);
    assert.match(out, /\[x\] none/);
    headerLine(tpl, "Clock \\| Beat \\| Energy \\(verse/chorus/bridge\\)");
    headerLine(out, "Clock \\| Beat \\| Energy \\(verse/chorus/bridge\\)");
    headerLine(tpl, "Take \\| Location \\| Grade \\| Windows \\| Prefix \\| Hop-1 seed");
    headerLine(out, "Take \\| Location \\| Grade \\| Windows \\| Prefix \\| Hop-1 seed");
    headerLine(tpl, "Entity \\| File \\| Conditions hop");
    headerLine(out, "Entity \\| File \\| Conditions hop");
    assert.match(out, /## Map \(clock → beat, not shots\)/);
    assert.match(out, /Wikipedia is not a still/);
    assert.match(out, /^> DRAFT — gates red/m);
    headerLine(out, "Take \\| Prefix \\| T2V planned \\| Watched");
    assert.match(out, /\| sigils-a \| yes \| yes \|/);
  });

  it("edit-list keeps join legend and columns", () => {
    const tpl = template("edit-list.md");
    const out = renderEditList(sigilsSample());
    headerLine(
      tpl,
      "# \\| Song t \\| Dur s \\| Join \\| Take \\| Location / grade \\| Camera \\(one\\) \\| Action \\| Hold\\? \\| Notes",
    );
    headerLine(
      out,
      "# \\| Song t \\| Dur s \\| Join \\| Take \\| Location / grade \\| Camera \\(one\\) \\| Action \\| Hold\\? \\| Notes",
    );
    assert.match(out, /Join: `continue` = Motion-Context hop/);
    assert.match(out, /fadeblack→A/);
    assert.match(out, /\| cut \|/);
  });

  it("look card keeps the one-style-line shape", () => {
    const tpl = template("look-card.md");
    const out = renderLook(sigilsSample());
    assert.match(tpl, /^# Look card — \{TITLE\}/m);
    assert.match(out, /^# Look card — Sigils in the Steel/m);
    assert.match(out, /One style line \(paste into every `\[Shot 1\]`\):/);
    assert.match(out, /Gold \/ dusk \/ amber are three takes/);
  });

  it("character card keeps lock table fields", () => {
    const tpl = template("character-card.md");
    const card = sigilsSample().characters[0];
    const out = renderCharacter(card);
    headerLine(tpl, "Field \\| Lock \\(same words every hop\\)");
    headerLine(out, "Field \\| Lock \\(same words every hop\\)");
    for (const field of [
      "Age / sex",
      "Face / hair / beard",
      "Body",
      "Wardrobe",
      "Footwear",
      "Distinguishing marks",
      "Era / forbidden modern",
    ]) {
      assert.match(out, new RegExp(`\\| ${field} \\|`));
    }
    assert.match(out, /^# Character card — smith/m);
  });

  it("prop card keeps measurement columns and the two empty-before-generate flags", () => {
    const tpl = template("prop-card.md");
    const out = renderProp(sigilsSample().props[0]);
    headerLine(tpl, "Field \\| Value \\| Unit \\| Source \\(lyric / photo / measured\\)");
    headerLine(out, "Field \\| Value \\| Unit \\| Source \\(lyric / photo / measured\\)");
    for (const field of [
      "Overall length",
      "Haft length",
      "Head mass",
      "Edge width",
      "Head shape",
      "Poll",
      "Eye",
      "Socket",
      "Haft wood / color",
      "Bindings",
      "Decoration",
      "Wear / finish",
    ]) {
      assert.match(out, new RegExp(`\\| ${field} \\|`));
    }
    assert.match(out, /45/);
    assert.match(out, /600/);
    assert.match(out, /- \[x\] overall vs haft length unresolved/);
    assert.match(out, /- \[ \] no still and no reason/);
  });

  it("pinned numeric haft clears the unresolved checkbox", () => {
    const out = renderProp(sigilsGenerateReady().props[0]);
    assert.match(out, /- \[ \] overall vs haft length unresolved/);
  });

  it("continuity log keeps the landed-vs-intent columns", () => {
    const tpl = template("continuity-log.md");
    const out = renderContinuity(sigilsSample());
    headerLine(
      tpl,
      "Take \\| Hop \\| Seed \\| Wall s \\| Peak °C \\| ffprobe \\(dur / frames\\) \\| Still vs lock \\| Circle / NG \\| Why",
    );
    headerLine(
      out,
      "Take \\| Hop \\| Seed \\| Wall s \\| Peak °C \\| ffprobe \\(dur / frames\\) \\| Still vs lock \\| Circle / NG \\| Why",
    );
    assert.match(out, /Intent is the edit list/);
  });

  it("packToFiles emits the HOW-TO filenames for the Sigils sample", () => {
    const files = packToFiles(sigilsSample());
    assert.deepEqual(Object.keys(files).sort(), [
      "README.md",
      "character-smith.md",
      "character-thrower.md",
      "continuity-log.md",
      "edit-list.md",
      "look.md",
      "prop-francisca.md",
    ]);
  });

  it("empty pack still serializes template filenames", () => {
    const files = packToFiles(emptyPack());
    assert.ok(files["README.md"]);
    assert.match(files["README.md"], /^> DRAFT — gates red/m);
    assert.ok(files["edit-list.md"]);
    assert.ok(files["look.md"]);
    assert.ok(files["continuity-log.md"]);
    assert.ok(Object.keys(files).some((name) => name.startsWith("character-")));
    assert.ok(Object.keys(files).some((name) => name.startsWith("prop-")));
  });

  it("generate-ready zip README is not a DRAFT", () => {
    const out = renderReadme(sigilsGenerateReady());
    assert.equal(out.startsWith("> DRAFT"), false);
    assert.match(out, /^# Capture pack — Sigils in the Steel/m);
  });
});
