export const JOIN_TYPES = ["continue", "cut", "fadeblack"] as const;
export type JoinType = (typeof JOIN_TYPES)[number];

export const CAMERA_VERBS = [
  "push",
  "pull",
  "pan",
  "truck",
  "tilt",
  "pedestal",
  "arc",
  "track",
  "static",
  "shake",
] as const;
export type CameraVerb = (typeof CAMERA_VERBS)[number];

export const AUDIO_PATHS = ["na-mute", "prompt-score", "silence"] as const;
export type AudioPath = (typeof AUDIO_PATHS)[number];

export const SPEECH_MODES = ["none", "finish-by-8s"] as const;
export type SpeechMode = (typeof SPEECH_MODES)[number];

export const ENERGY_VALUES = ["title", "verse", "chorus", "bridge", "outro"] as const;
export type EnergyValue = (typeof ENERGY_VALUES)[number];

/** Two Sparks, two jobs. Canvas 1344×768 is H3 native — not a serving pin. */
export const STACK_LINE =
  "Still factory: Qwen-Image-2.1 · 1344×768 (do not stretch 1024²) · Clip factory: MiniMax H3 + Motion-Context";

export const DEFAULT_STILL_CANVAS = "1344×768";

export const STILL_ROLES = ["sheet", "hop-1 plate", "cut plate", "last-frame"] as const;
export type StillRole = (typeof STILL_ROLES)[number];

export const STILL_SOURCES = ["photo", "qwen-t2i", "qwen-edit", "none"] as const;
export type StillSource = (typeof STILL_SOURCES)[number];

export const HOP1_MODES = ["i2va", "t2v"] as const;
export type Hop1Mode = (typeof HOP1_MODES)[number];

export const PROP_FIELDS = [
  { key: "overallLength", label: "Overall length", unit: "cm" },
  { key: "haftLength", label: "Haft length", unit: "cm" },
  { key: "headMass", label: "Head mass", unit: "g" },
  { key: "edgeWidth", label: "Edge width", unit: "cm" },
  { key: "headShape", label: "Head shape", unit: "—" },
  { key: "poll", label: "Poll", unit: "—" },
  { key: "eye", label: "Eye", unit: "—" },
  { key: "socket", label: "Socket", unit: "—" },
  { key: "haftWoodColor", label: "Haft wood / color", unit: "—" },
  { key: "bindings", label: "Bindings", unit: "—" },
  { key: "decoration", label: "Decoration", unit: "—" },
  { key: "wearFinish", label: "Wear / finish", unit: "—" },
] as const;

export type PropFieldKey = (typeof PROP_FIELDS)[number]["key"];

export type PropMeasurement = {
  value: string;
  unit: string;
  source: string;
};

export type MapRow = {
  id: string;
  clock: string;
  beat: string;
  energy: string;
};

export type TakeCard = {
  id: string;
  take: string;
  location: string;
  grade: string;
  windows: string;
  prefix: string;
  hop1Seed: string;
  hop1Mode: Hop1Mode | "";
  hop1Plate: string;
  hop1Planned: boolean;
  watched: boolean;
};

export type EditRow = {
  id: string;
  songT: string;
  durS: string;
  join: JoinType | "";
  take: string;
  locationGrade: string;
  cameraVerb: CameraVerb | "";
  cameraAmplitude: string;
  cameraSpeed: string;
  action: string;
  hold: string;
  notes: string;
};

export type CharacterCard = {
  id: string;
  name: string;
  stillFile: string;
  stillSource: StillSource | "";
  stillCanvas: string;
  speakerId: string;
  ageSex: string;
  faceHairBeard: string;
  body: string;
  wardrobe: string;
  footwear: string;
  distinguishingMarks: string;
  eraForbiddenModern: string;
  lockParagraph: string;
  forbidden: string;
  motionNotes: string;
};

export type PropCard = {
  id: string;
  name: string;
  stillFile: string;
  stillSource: StillSource | "";
  stillCanvas: string;
  fields: Record<PropFieldKey, PropMeasurement>;
  lockParagraph: string;
  forbidden: string;
};

export type LookCard = {
  styleLine: string;
  paletteGrade: string;
  era: string;
  lensGrain: string;
  extrasForbidden: string;
};

/** First-class still card — `templates/still-card.md`. */
export type StillCard = {
  id: string;
  entity: string;
  role: StillRole | "";
  source: StillSource | "";
  canvas: string;
  file: string;
  conditions: string;
  lookLock: string;
  lockFromStill: string;
  forbidden: string;
  notes: string;
};

/** @deprecated Use StillCard. Kept as an alias for migrated v1 rows. */
export type StillRow = StillCard;

export type ContinuityRow = {
  id: string;
  take: string;
  hop: string;
  seed: string;
  wallS: string;
  peakC: string;
  ffprobe: string;
  stillVsLock: string;
  circleNg: string;
  why: string;
};

export type CapturePack = {
  title: string;
  logLine: string;
  durationTarget: string;
  songNarrativeClock: string;
  audioPath: AudioPath | "";
  speech: SpeechMode | "";
  forbiddenGlobal: string;
  map: MapRow[];
  takes: TakeCard[];
  editList: EditRow[];
  characters: CharacterCard[];
  props: PropCard[];
  look: LookCard;
  stills: StillCard[];
  smokeNotes: string;
  continuityRows: ContinuityRow[];
  polaroidPath: string;
};

export const CHARACTER_LOCK_FIELDS = [
  { key: "ageSex", label: "Age / sex" },
  { key: "faceHairBeard", label: "Face / hair / beard" },
  { key: "body", label: "Body" },
  { key: "wardrobe", label: "Wardrobe" },
  { key: "footwear", label: "Footwear" },
  { key: "distinguishingMarks", label: "Distinguishing marks" },
  { key: "eraForbiddenModern", label: "Era / forbidden modern" },
] as const;

export type CharacterLockKey = (typeof CHARACTER_LOCK_FIELDS)[number]["key"];

export const DEFAULT_GLOBAL_FORBIDDEN =
  "no plate armor, no horned helms, no on-screen lettering, no modern clothing";

export const DEFAULT_CHARACTER_FORBIDDEN =
  "glasses, plate, horns, logos, on-screen text";

export const DEFAULT_PROP_FORBIDDEN =
  "bearded blade, double bit, horns, chrome, leather wrap unless listed";

export const DEFAULT_LOOK_FORBIDDEN =
  "no cars, no text, no logos, no modern clothing";

export const DEFAULT_LOOK_STYLE =
  "Live-action, photoreal cinematic, crushed blacks, hot ember highlights, 24fps.";

export const DEFAULT_SMOKE_NOTES =
  "One hop-1 per take — I2VA if a plate exists, else T2V — watched before hopping. continue = plate on hop-1 only; hop 2+ is Motion-Context latent (no new Qwen still). cut / fadeblack = new plate → I2VA hop-1. Chorus independent takes = independent plates → I2VA.";

export const STEPS = [
  { id: "pack", n: 1, label: "Log line", stage: "Script analysis" },
  { id: "map", n: 2, label: "Beats", stage: "Script analysis" },
  { id: "cards", n: 3, label: "Assets", stage: "Asset setup" },
  { id: "takes", n: 4, label: "Takes", stage: "Storyboard" },
  { id: "edit", n: 5, label: "Boards", stage: "Storyboard" },
  { id: "smoke", n: 6, label: "Preview", stage: "Video preview" },
] as const;

export type StepId = (typeof STEPS)[number]["id"];
