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

export const STACK_LINE =
  "Comfy native H3 · 1344×768 · 6-step turbo · Motion-Context 22";

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
  t2vPlanned: boolean;
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

export type StillRow = {
  id: string;
  entity: string;
  file: string;
  role: string;
  source: string;
  canvas: string;
  conditionsHop: string;
};

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
  stills: StillRow[];
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
  "One hop-1 per take (I2VA if a plate exists, else T2V) + planned fades. Watch identity at cuts. Do not hop until this join is watchable.";

export const STEPS = [
  { id: "pack", n: 1, label: "New pack" },
  { id: "map", n: 2, label: "Map" },
  { id: "takes", n: 3, label: "Takes" },
  { id: "edit", n: 4, label: "Edit list" },
  { id: "cards", n: 5, label: "Cards" },
  { id: "smoke", n: 6, label: "Smoke + log" },
] as const;

export type StepId = (typeof STEPS)[number]["id"];
