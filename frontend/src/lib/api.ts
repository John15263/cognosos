import type {
  FlowSessionMode,
  FlowSessionResponse,
  FlowSessionStagePayload,
  FlowSessionStructuredPayload,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  createFlowSession: (payload: {
    prompt_id: string;
    prompt_title: string;
    prompt_cues: string[];
    content: string;
    compiled_markdown?: string | null;
    mode: FlowSessionMode;
    status: "completed" | "failed" | "aborted";
    duration_seconds: number;
    idle_timeout_seconds: number;
    final_word_count: number;
    interruption_count: number;
    structured_payload?: FlowSessionStructuredPayload | Record<string, unknown>;
    pipeline_version?: string | null;
    decision_stage_enabled?: boolean;
    stages?: FlowSessionStagePayload[];
  }) =>
    request<FlowSessionResponse>("/flow-sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  shutdown: () =>
    request<{ status: string }>("/shutdown", {
      method: "POST",
      headers: { "X-CognosOS-Shutdown": "1" },
      body: "{}",
    }),
};
