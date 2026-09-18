import {
  DEFAULT_CHARACTER_FORBIDDEN,
  DEFAULT_GLOBAL_FORBIDDEN,
  DEFAULT_LOOK_FORBIDDEN,
  DEFAULT_LOOK_STYLE,
  DEFAULT_PROP_FORBIDDEN,
  type CapturePack,
  type PropCard,
  type PropFieldKey,
  type PropMeasurement,
} from "../types.ts";
import { emptyContinuity, emptyPropFields, uid } from "./pack.ts";

const NONE = "none — not in public example";

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
    fields: franciscaFields(),
    lockParagraph:
      "Francisca: overall 45 cm, head 600 g, 10 cm bite, square poll, teardrop eye. Do not invent a bearded blade, double bit, horns, or chrome.",
    forbidden: DEFAULT_PROP_FORBIDDEN,
  };
}

/**
 * Sigils lessons as a loadable pack: documented numbers and clocks,
 * template defaults, explicit `none` fills for unpublished stills/likeness.
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
      { id: uid(), clock: "0:00", beat: "title overlay", energy: "verse" },
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
        t2vPlanned: true,
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
        t2vPlanned: true,
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
        action: "chorus — new angle, new T2V",
        hold: "no",
        notes: "chorus",
      },
    ],
    characters: [
      {
        id: uid(),
        name: "smith",
        stillFile: "none — no public likeness still in this example",
        speakerId: "none",
        ageSex: NONE,
        faceHairBeard: NONE,
        body: NONE,
        wardrobe: NONE,
        footwear: NONE,
        distinguishingMarks: NONE,
        eraForbiddenModern: "no modern clothing",
        lockParagraph:
          "Same face, hair, and wardrobe every hop. Identity holds inside continue. Expect drift at cut and fadeblack until hop-1 is still-conditioned.",
        forbidden: DEFAULT_CHARACTER_FORBIDDEN,
        motionNotes: NONE,
      },
      {
        id: uid(),
        name: "thrower",
        stillFile: "none — no public likeness still in this example",
        speakerId: "none",
        ageSex: NONE,
        faceHairBeard: NONE,
        body: NONE,
        wardrobe: NONE,
        footwear: NONE,
        distinguishingMarks: NONE,
        eraForbiddenModern: "no modern clothing",
        lockParagraph:
          "Same face, hair, and wardrobe every hop. Identity holds inside continue. Expect drift at cut and fadeblack until hop-1 is still-conditioned.",
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
      {
        id: uid(),
        entity: "smith",
        file: "none — no public likeness still in this example",
        conditionsHop: "hop-1 of take A",
      },
      {
        id: uid(),
        entity: "thrower",
        file: "none — no public likeness still in this example",
        conditionsHop: "hop-1 of take B",
      },
      {
        id: uid(),
        entity: "francisca",
        file: "none — no public still; lyric numbers pinned before any browser call",
        conditionsHop: "hop-1 of take A",
      },
    ],
    smokeNotes:
      "One T2V per take + planned fades. Watch identity at cuts. Chorus rows are cut with no hold. Do not hop until this join is watchable.",
    continuityRows: [emptyContinuity()],
    polaroidPath: "none — fill during generate",
  };
}
