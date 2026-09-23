/** CLIP_BRIDGE types. docs/CLIP_BRIDGE.md is the dialect. The server fills slots. */

export type StoryLock = {
  project_id: string;
  aspect: string;
  width: number;
  height: number;
  fps: number;
  duration_s: number;
  lens: string;
  style: string;
  identity: string;
  wardrobe: string;
  palette: string;
  lighting_bible: string;
  screen_direction: string;
  negative: string;
  character_sheet?: string;
  wardrobe_sheet?: string;
  location_plates?: string[];
};

export type ClipItem = {
  clip_id: string;
  purpose?: string;
  location?: string;
  time_of_day?: string;
  start_state: string;
  end_state: string;
  action: string;
  action_beats?: string[];
  camera_start?: string;
  camera_end?: string;
  camera_move: string;
  screen_direction?: string;
  screen_direction_reversal?: boolean;
  prop_state_start?: string;
  prop_state_end?: string;
  transition_in?: string;
  transition_out?: string;
  start_image?: string;
  end_designed?: string;
  end_extracted?: string;
  video?: string;
  status?: "planned" | "keyframes_ready" | "rendered" | "extracted" | "rejected";
  soundscape?: string;
  music?: string;
  start_frame_prompt?: string;
  end_frame_prompt?: string;
  h3_prompt?: string;
  identity?: string;
  wardrobe?: string;
  palette?: string;
  lighting_bible?: string;
};

export type ClipBridgeIssue = {
  code: string;
  message: string;
  clip_id?: string;
};

export type ClipBridgePreview = {
  dialect: "clip-bridge";
  partial: string;
  h3_prompt: string;
  qwen_q1: string;
  qwen_start: string;
  qwen_end: string;
  qwen_q4: string;
  qwen_q5: string;
  qwen_q6: string;
  visual_lock: string;
  negative_lock: string;
  alignment: string;
  start_state: string;
  end_state: string;
  identity: string;
  issues: ClipBridgeIssue[];
  ok: boolean;
  called_comfy: false;
  produced_mp4: false;
  live_render: false;
  honesty: string;
};
