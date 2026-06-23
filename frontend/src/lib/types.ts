export type CardModuleType =
  | "free_write"
  | "decision"
  | "gratitude"
  | "reciprocity"
  | "scaffolding"
  | "avsi"
  | "future_self"
  | "check_review"
  | "task"
  | "prediction"
  | "insight"
  | "general";

export interface EntryCreateResponse {
  entry_id: string;
}

export type FlowSessionStatus = "started" | "completed" | "failed" | "aborted";
export type FlowSessionMode = "hard" | "soft" | "training";
export type FlowSessionStageStatus = "completed" | "skipped" | "failed" | "saved_early";

export interface FlowSessionStagePayload {
  stage_id: string;
  stage_order: number;
  module_type: CardModuleType;
  title: string | null;
  prompt_label: string | null;
  ghost_starter: string | null;
  content: string;
  word_count: number;
  status: FlowSessionStageStatus;
  idle_timeout_seconds: number | null;
  interruption_count: number;
  started_at: string | null;
  completed_at: string | null;
  nudges_shown: string[];
  metadata_json: Record<string, unknown>;
}

export interface FlowSessionStructuredPayload {
  writing_mode: "breakthrough_canvas";
  pipeline_version: string;
  decision_stage_enabled: boolean;
  stages: FlowSessionStagePayload[];
}

export interface FlowSessionStage extends FlowSessionStagePayload {
  id: string;
  writing_session_id: string;
  created_card_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface FlowSession {
  id: string;
  prompt_id: string;
  prompt_title: string;
  prompt_cues: string[];
  mode: FlowSessionMode;
  status: FlowSessionStatus;
  duration_seconds: number;
  idle_timeout_seconds: number;
  final_word_count: number;
  interruption_count: number;
  structured_payload: FlowSessionStructuredPayload | Record<string, unknown>;
  pipeline_version: string | null;
  decision_stage_enabled: boolean;
  content_hash: string | null;
  note_path: string | null;
  raw_entry_id: string | null;
  started_at: string;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
  stages: FlowSessionStage[];
}

export interface FlowSessionResponse {
  session: FlowSession;
  entry: EntryCreateResponse | null;
}
