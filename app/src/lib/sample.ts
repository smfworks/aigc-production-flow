import {
  DEFAULT_CHARACTER_FORBIDDEN,
  DEFAULT_GLOBAL_FORBIDDEN,
  DEFAULT_LOOK_FORBIDDEN,
  DEFAULT_LOOK_STYLE,
  DEFAULT_PROP_FORBIDDEN,
  DEFAULT_SMOKE_NOTES,
  DEFAULT_STILL_CANVAS,
  type CapturePack,
  type PropCard,
  type PropFieldKey,
  type PropMeasurement,
  type StillCard,
} from "../types.ts";
import { emptyContinuity, emptyPropFields, uid } from "./pack.ts";

const NONE = "none — not in public example";
const NONE_STILL = "none — no public likeness still in this example";
const NONE_PLATE = "none — no public plate; hop-1 stays T2V until a 1344×768 still conditions first_frame";

function still(partial: Partial<StillCard> & Pick<StillCard, "entity" | "role" | "file" | "conditions">): StillCard {
  return {
    id: uid(),
    source: "none",
    canvas: DEFAULT_STILL_CANVAS,
    lookLock: "",
    lockFromStill: "",
    forbidden: "",
    notes: "Public example — not a generate still. Do not publish likeness stills to this tree.",
    ...partial,
  };
}

function m(value: string, unit: string, source: string): PropMeasurement {
  return { value, unit, source };
}

function franciscaFields(): Record<PropFieldKey, PropMeasurement> {
  const fields = emptyPropFields();
  fields.overallLength = m("45", "cm", "lyric");
  fields.haftLength = m(NONE, "cm", "not in public lyric sheet — pin before GPU");
  fields.headMass = m("600", "g", "lyric");
  fields.edgeWidth = m("10", "cm", "lyric (bite)");
  fields.headShape = m(NONE, "—", "not in public example");
  fields.poll = m("square", "—", "lyric");
  fields.eye = m("teardrop", "—", "lyric");
  fields.socket = m(NONE, "—", "not in public example");
  fields.haftWoodColor = m(NONE, "—", "not in public example");
  fields.bindings = m(NONE, "—", "not in public example");
  fields.decoration = m(NONE, "—", "not in public example");
  fields.wearFinish = m(NONE, "—", "not in public example");
  return fields;
}

function francisca(): PropCard {
  return {
    id: uid(),
    name: "francisca",
    stillFile: "none — no public still; lyric numbers pinned before any browser call",
    stillSource: "none",
    stillCanvas: DEFAULT_STILL_CANVAS,
    fields: franciscaFields(),
    lockParagraph:
      "Francisca: overall 45 cm, head 600 g, 10 cm bite, square poll, teardrop eye. Do not invent a bearded blade, double bit, horns, or chrome.",
    forbidden: DEFAULT_PROP_FORBIDDEN,
  };
}

/**
 * Sigils lessons as a loadable pack: documented numbers and clocks,
 * template defaults, explicit `none` fills for unpublished stills/likeness.
 * Haft is unpinned on purpose — public example, not generate-ready.
 */
export function sigilsSample(): CapturePack {
  const takeA = uid();
  const takeB = uid();
  return {
    title: "Sigils in the Steel",
    logLine:
      "A lyric-timed reshoot of Sigils in the Steel: verse as take, chorus as cut, francisca numbers pinned before generate.",
    durationTarget: "≥4:12",
    songNarrativeClock: "0:00 title · 0:18 verse · 0:46 chorus",
    audioPath: "na-mute",
    speech: "none",
    forbiddenGlobal: DEFAULT_GLOBAL_FORBIDDEN,
    map: [
      { id: uid(), clock: "0:00", beat: "title overlay", energy: "title" },
      { id: uid(), clock: "0:18", beat: "verse", energy: "verse" },
      { id: uid(), clock: "0:46", beat: "chorus", energy: "chorus" },
    ],
    takes: [
      {
        id: takeA,
        take: "A",
        location: "forge interior",
        grade: "dusk / gold ember",
        windows: "hop-1 + continue hops",
        prefix: "sigils-a",
        hop1Seed: "56",
        hop1Mode: "t2v",
        hop1Plate: NONE_PLATE,
        hop1Planned: true,
        watched: true,
      },
      {
        id: takeB,
        take: "B",
        location: "yard",
        grade: "night — separate take, not mixed with dusk",
        windows: "chorus cuts",
        prefix: "sigils-b",
        hop1Seed: "57",
        hop1Mode: "t2v",
        hop1Plate: NONE_PLATE,
        hop1Planned: true,
        watched: true,
      },
    ],
    editList: [
      {
        id: uid(),
        songT: "0:00",
        durS: "10.125",
        join: "fadeblack",
        take: "A",
        locationGrade: "forge interior / dusk gold ember",
        cameraVerb: "static",
        cameraAmplitude: "none",
        cameraSpeed: "hold",
        action: "title overlay",
        hold: "yes before fade",
        notes: "title overlay 8 s",
        entities: "smith, francisca",
      },
      {
        id: uid(),
        songT: "0:18",
        durS: "9.209",
        join: "continue",
        take: "A",
        locationGrade: "forge interior / dusk gold ember",
        cameraVerb: "push",
        cameraAmplitude: "small",
        cameraSpeed: "slow",
        action: "verse continues in the same room",
        hold: "no",
        notes: "verse",
        entities: "smith, francisca",
      },
      {
        id: uid(),
        songT: "0:46",
        durS: "5",
        join: "cut",
        take: "B",
        locationGrade: "yard / night",
        cameraVerb: "pan",
        cameraAmplitude: "small",
        cameraSpeed: "slow",
        action: "chorus — new angle, independent plate → I2VA (T2V until a plate exists)",
        hold: "no",
        notes: "chorus",
        entities: "thrower, francisca",
      },
    ],
    characters: [
      {
        id: uid(),
        name: "smith",
        stillFile: NONE_STILL,
        stillSource: "none",
        stillCanvas: DEFAULT_STILL_CANVAS,
        speakerId: "none",
        ageSex: NONE,
        faceHairBeard: NONE,
        body: NONE,
        wardrobe: NONE,
        footwear: NONE,
        distinguishingMarks: NONE,
        eraForbiddenModern: "no modern clothing",
        lockParagraph:
          "Same face, hair, and wardrobe every hop. Identity holds inside continue. Expect drift at cut and fadeblack until a plate conditions hop-1.",
        forbidden: DEFAULT_CHARACTER_FORBIDDEN,
        motionNotes: NONE,
      },
      {
        id: uid(),
        name: "thrower",
        stillFile: NONE_STILL,
        stillSource: "none",
        stillCanvas: DEFAULT_STILL_CANVAS,
        speakerId: "none",
        ageSex: NONE,
        faceHairBeard: NONE,
        body: NONE,
        wardrobe: NONE,
        footwear: NONE,
        distinguishingMarks: NONE,
        eraForbiddenModern: "no modern clothing",
        lockParagraph:
          "Same face, hair, and wardrobe every hop. Identity holds inside continue. Expect drift at cut and fadeblack until a plate conditions hop-1.",
        forbidden: DEFAULT_CHARACTER_FORBIDDEN,
        motionNotes: NONE,
      },
    ],
    props: [francisca()],
    look: {
      styleLine: DEFAULT_LOOK_STYLE,
      paletteGrade: "Gold / dusk / amber are three takes, not one prompt.",
      era: "No modern clothing. Do not mix noon and night in one 10 s window.",
      lensGrain: "",
      extrasForbidden: DEFAULT_LOOK_FORBIDDEN,
    },
    stills: [
      still({
        entity: "smith",
        role: "sheet",
        file: NONE_STILL,
        conditions: "none",
        forbidden: DEFAULT_CHARACTER_FORBIDDEN,
        notes: "Sheet is the bible. Plates for hop-1 live on still-hop1-*.md. No public likeness.",
      }),
      still({
        entity: "thrower",
        role: "sheet",
        file: NONE_STILL,
        conditions: "none",
        forbidden: DEFAULT_CHARACTER_FORBIDDEN,
        notes: "Sheet is the bible. Plates for hop-1 live on still-hop1-*.md. No public likeness.",
      }),
      still({
        entity: "francisca",
        role: "sheet",
        file: "none — no public still; lyric numbers pinned before any browser call",
        conditions: "none",
        forbidden: DEFAULT_PROP_FORBIDDEN,
        notes: "Sheet is the bible. Do not use Wikipedia as a still.",
      }),
      still({
        entity: "take A hop-1",
        role: "hop-1 plate",
        file: NONE_PLATE,
        conditions: "hop-1 of take A",
        notes: "continue plate on hop-1 only. Hop 2+ is Motion-Context latent.",
      }),
      still({
        entity: "take B hop-1",
        role: "hop-1 plate",
        file: NONE_PLATE,
        conditions: "hop-1 of take B",
        notes: "fadeblack / new location — new plate, not take A's last frame.",
      }),
      still({
        entity: "chorus cut",
        role: "cut plate",
        file: NONE_PLATE,
        conditions: "cut row 3",
        notes: "Independent chorus take = independent plate → I2VA once a PNG exists.",
      }),
      still({
        entity: "smith",
        role: "hop-1 plate",
        file: NONE_PLATE,
        conditions: "hop-1 of take A",
        notes: "Identity hold for smith at fadeblack hop-1. Public example — none + why until a plate exists.",
      }),
      still({
        entity: "francisca",
        role: "hop-1 plate",
        file: NONE_PLATE,
        conditions: "hop-1 of take A",
        notes: "Identity hold for francisca at take A hop-1.",
      }),
      still({
        entity: "thrower",
        role: "cut plate",
        file: NONE_PLATE,
        conditions: "cut row 3",
        notes: "Identity hold for thrower at the chorus cut.",
      }),
      still({
        entity: "francisca",
        role: "cut plate",
        file: NONE_PLATE,
        conditions: "cut row 3",
        notes: "Identity hold for francisca at the chorus cut.",
      }),
    ],
    entitySchedule: [
      {
        id: uid(),
        entityKind: "character",
        entityName: "smith",
        take: "A",
        windows: "all",
        identityHold: true,
      },
      {
        id: uid(),
        entityKind: "character",
        entityName: "thrower",
        take: "B",
        windows: "all",
        identityHold: true,
      },
      {
        id: uid(),
        entityKind: "prop",
        entityName: "francisca",
        take: "*",
        windows: "all",
        identityHold: true,
      },
    ],
    smokeNotes: DEFAULT_SMOKE_NOTES,
    continuityRows: [emptyContinuity()],
    polaroidPath: "none — fill during generate",
  };
}

/**
 * Same lessons pack with a clearly fake numeric haft so tests can cover a
 * 9/9 path. Not a public still; source says measured stand-in.
 */
export function sigilsGenerateReady(): CapturePack {
  const pack = sigilsSample();
  pack.props[0].fields.haftLength = m("32", "cm", "measured stand-in — demo only");
  return pack;
}
