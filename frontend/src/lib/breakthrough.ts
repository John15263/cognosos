import type { FlowSessionStagePayload, FlowSessionStageStatus, FlowSessionStructuredPayload } from "./types";

export type BreakthroughStageId =
  | "mental_dump"
  | "future_reframe"
  | "decision_snapshot"
  | "scaffold_action"
  | "prediction_seal";
export type BreakthroughMode = "free_write" | "future_self" | "decision" | "scaffolding" | "prediction";
export type IdlePressureMode = "hard" | "soft";

export interface BreakthroughStage {
  step: number;
  id: BreakthroughStageId;
  mode: BreakthroughMode;
  label: string;
  title: string;
  subtitle: string;
  ghostStarter: string;
  nudges: string[];
  advanceLabel: string;
  extractorHint: string;
  enforcePastTense?: boolean;
  timePerspective?: string;
  createsTimeCapsule?: boolean;
  optional?: boolean;
}

export type StageDrafts = Record<BreakthroughStageId, string>;
export type StageTimes = Partial<Record<BreakthroughStageId, string>>;

export const PIPELINE_VERSION = "v1.3_prediction_seal";
export const PRESSURE_WINDOW_SECONDS = 300;
export const NOISE_IDLE_TIMEOUT = 8;

export const IDLE_POLICIES: Record<
  BreakthroughStageId,
  { timeoutSeconds: number; dangerWindowSeconds: number; mode: IdlePressureMode }
> = {
  mental_dump: { timeoutSeconds: NOISE_IDLE_TIMEOUT, dangerWindowSeconds: 4, mode: "hard" },
  future_reframe: { timeoutSeconds: 20, dangerWindowSeconds: 8, mode: "soft" },
  decision_snapshot: { timeoutSeconds: 30, dangerWindowSeconds: 10, mode: "soft" },
  scaffold_action: { timeoutSeconds: 30, dangerWindowSeconds: 10, mode: "soft" },
  prediction_seal: { timeoutSeconds: 30, dangerWindowSeconds: 10, mode: "soft" },
};

export const BREAKTHROUGH_STAGES: BreakthroughStage[] = [
  {
    step: 1,
    id: "mental_dump",
    mode: "free_write",
    label: "PHASE 1 · THE NOISE",
    title: "What is looping in your head right now?",
    subtitle: "脑子里很多活动不是思考，而是重复循环。先不要解决，先把那个一直萦绕不去的东西倒出来。没有观众，没有结构。",
    ghostStarter: "我现在脑子里最吵、一直绕不出去的状况是：",
    nudges: [
      "继续写。下一句可以很乱，但不要停。",
      "你刚才写的是表层，下面那层是什么？",
      "如果完全诚实，你真正害怕的是什么？",
      "不要急着解决，先把现状交代清楚。",
    ],
    advanceLabel: "Flip Timeline",
    extractorHint: "Extract emotional loops, stuckness, people, topics, urgency, and repeated anxieties.",
  },
  {
    step: 2,
    id: "future_reframe",
    mode: "future_self",
    label: "PHASE 2 · FUTURE-SELF",
    title: "Open the future time capsule.",
    subtitle: "你现在是五年后的自己。先描述你现在的生活、重心和身份，再回信给那个刚刚被恐惧困住的过去的你。",
    ghostStarter: "五年后的我现在过着这样的生活：____。我的生活重心是____。我主要在构建____。我已经是那种会____的人。",
    nudges: [
      "不要写“我想成为”。写“我已经是那种会……的人”。",
      "打开刚才那封来自过去的信：那时的你真正害怕的是什么？",
      "这份恐惧有什么信息价值？又为什么不该占据核心带宽？",
      "五年后的你主要在构建什么？",
      "过去的你现在应该把算力投入到什么地基上？",
      "用一句身份句收尾：我是那种会____的人，所以我现在要____。",
    ],
    advanceLabel: "Decision Trace",
    extractorHint:
      "Create a future_self card. Extract future_life, center_of_gravity, identity_statement, past_fear, fear_signal, misallocated_bandwidth, important_construction, attention_allocation, and implied_next_actions.",
    timePerspective: "future_present_and_past_reply",
  },
  {
    step: 3,
    id: "decision_snapshot",
    mode: "decision",
    label: "PHASE 3 · DECISION TRACE",
    title: "Trace the decision that brought you here.",
    subtitle:
      "结果受运气影响。你真正能复盘的是当时的推理质量。先回看：哪个过去的决定、不决定、拖延或默认选择，把你带到了这里？不要审判过去的自己。回到当时的信息、情绪和约束里，检查判断，然后定格你现在的新决定。",
    ghostStarter:
      "这个局面不是凭空出现的。回头看，最可能把我带到这里的一个过去决定 / 不决定 / 默认选择是：____。当时我之所以那样做，是因为我相信____，害怕____，试图保护____。在当时的信息和处境下，这个判断合理的地方是____。现在看，它真正的偏差是____。其中我无法控制的运气 / 环境因素是____。如果这个决定需要一位见证者，我想到的是____。他 / 她代表的不是审判，而是____。基于这个回溯和这份见证，我现在的判断 / 决定是____。我之所以这样判断，是因为____。我预期现实会____。我会在____回来检查。",
    nudges: [
      "不要写“我真蠢”。写：当时我在优化什么、躲避什么、保护什么？",
      "这可能不是一个主动决定，而是一个“没有决定”形成的默认路径。",
      "不要用现在的上帝视角霸凌过去的自己。回到当时的信息和约束里。",
      "把运气、环境突变、他人反应这些不可控因素先划出来。",
      "剩下那一小块，才是你真正能更新的判断模型。",
      "如果需要见证者，他不是来审判你的。他代表什么价值、勇气或清醒？",
      "基于这个回溯，你现在的新决定是什么？它的推理质量足够高吗？",
      "写下一个可以被未来检查的预期结果。",
    ],
    advanceLabel: "Build Scaffold",
    extractorHint:
      "Create a decision card. Extract prior_decision, prior_non_decision, default_path, causal_chain, then_belief, then_fear, protected_value, then_emotion, reasoning_quality, luck_or_uncontrolled_factors, reasoning_bug, hindsight_update, witness_name, witness_represents, value_anchor, current_decision, expected_outcome, and check_at.",
    createsTimeCapsule: true,
    optional: true,
  },
  {
    step: 4,
    id: "scaffold_action",
    mode: "scaffolding",
    label: "PHASE 4 · THE SCAFFOLD",
    title: "Make it startable and systematic.",
    subtitle: "把刚才的判断落到现实世界。不要写宏大目标，写一个 10 分钟内能证明这个身份的物理动作，以及一个未来检查点。",
    ghostStarter: "为了证明这个身份并让判断落地，我接下来的 10 分钟最小行动是：",
    nudges: [
      "具体到工具、环境、时间和动作。",
      "怎样算初步完成？",
      "你需要先准备什么？",
      "你什么时候回来检查这个行动是否有效？",
    ],
    advanceLabel: "Seal Prediction",
    extractorHint: "Extract problem definition, success criteria, next action, blocker, required preparation, and check_at.",
    createsTimeCapsule: true,
  },
  {
    step: 5,
    id: "prediction_seal",
    mode: "prediction",
    label: "PHASE 5 · PREDICTION SEAL",
    title: "What do you expect reality to do now?",
    subtitle:
      "现在你已经完成了排空、重构、判断和脚手架。在这个清明状态下，不要写目标，不要写愿望，写下你对现实的可验证预测。",
    ghostStarter: "如果我真的按这个身份、判断和行动前进，我预测现实接下来会回应的是：",
    nudges: [
      "这不是目标。写一个会被现实验证的预测。",
      "你预计别人会怎么反应？概率是多少？",
      "你预计自己会在哪一步产生阻力？",
      "未来用什么证据检查这个预测？",
      "如果你错了，说明你的判断模型哪里需要更新？",
    ],
    advanceLabel: "Save & Commit",
    extractorHint:
      "Create a prediction card. Extract predictions, probabilities, reasoning, verification signals, check_at, and links to decision/scaffold cards.",
    createsTimeCapsule: true,
  },
];

const DECISION_KEYWORDS = [
  "决定",
  "要不要",
  "是否",
  "选择",
  "放弃",
  "开始",
  "停止",
  "拒绝",
  "接受",
  "发邮件",
  "道歉",
  "沟通",
  "commit",
  "decide",
  "choose",
  "stop",
  "start",
];

export function createEmptyDrafts(): StageDrafts {
  return {
    mental_dump: "",
    future_reframe: "",
    decision_snapshot: "",
    scaffold_action: "",
    prediction_seal: "",
  };
}

export function countWords(text: string) {
  const asciiWords = text.match(/[A-Za-z0-9_+#.-]+/g)?.length ?? 0;
  const cjkChars = text.match(/[\u4e00-\u9fff]/g)?.length ?? 0;
  return asciiWords + cjkChars;
}

export function formatTime(seconds: number) {
  const minutes = Math.floor(Math.max(0, seconds) / 60);
  const rest = Math.max(0, seconds) % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

export function shouldSuggestDecisionStage(text: string) {
  const normalized = text.toLowerCase();
  return DECISION_KEYWORDS.some((keyword) => normalized.includes(keyword.toLowerCase()));
}

export function getActiveStages(decisionStageEnabled: boolean) {
  return BREAKTHROUGH_STAGES.filter((stage) => stage.id !== "decision_snapshot" || decisionStageEnabled);
}

function getPayloadStages(decisionStageEnabled: boolean, decisionSkipped: boolean) {
  return BREAKTHROUGH_STAGES.filter((stage) => stage.id !== "decision_snapshot" || decisionStageEnabled || decisionSkipped);
}

export function buildBreakthroughPayload({
  drafts,
  decisionStageEnabled,
  decisionSkipped,
  stageStartedAt,
  stageCompletedAt,
  interruptionCount,
}: {
  drafts: StageDrafts;
  decisionStageEnabled: boolean;
  decisionSkipped: boolean;
  stageStartedAt: StageTimes;
  stageCompletedAt: StageTimes;
  interruptionCount: number;
}): FlowSessionStructuredPayload {
  return {
    writing_mode: "breakthrough_canvas",
    pipeline_version: PIPELINE_VERSION,
    decision_stage_enabled: decisionStageEnabled,
    stages: getPayloadStages(decisionStageEnabled, decisionSkipped).map((stage) => {
      const content = drafts[stage.id].trim();
      const skippedDecision = stage.id === "decision_snapshot" && decisionSkipped && !decisionStageEnabled;
      const status: FlowSessionStageStatus = skippedDecision
        ? "skipped"
        : content
          ? "completed"
          : stageStartedAt[stage.id]
            ? "saved_early"
            : "skipped";
      const idlePolicy = IDLE_POLICIES[stage.id];
      return {
        stage_id: stage.id,
        stage_order: stage.step,
        module_type: stage.mode,
        title: stage.title,
        prompt_label: stage.label,
        ghost_starter: stage.ghostStarter,
        content,
        word_count: countWords(content),
        status,
        idle_timeout_seconds: idlePolicy.timeoutSeconds,
        interruption_count: stage.id === "mental_dump" ? interruptionCount : 0,
        started_at: stageStartedAt[stage.id] ?? null,
        completed_at: stageCompletedAt[stage.id] ?? null,
        nudges_shown: [],
        metadata_json: {
          extractor_hint: stage.extractorHint,
          creates_time_capsule: Boolean(stage.createsTimeCapsule),
          hard_mode: idlePolicy.mode === "hard",
          idle_policy: idlePolicy.mode,
          enforce_past_tense: Boolean(stage.enforcePastTense),
          time_perspective: stage.timePerspective ?? null,
        },
      } satisfies FlowSessionStagePayload;
    }),
  };
}

export function compileBreakthroughMarkdown(payload: FlowSessionStructuredPayload) {
  return payload.stages
    .map((stage) => {
      const content = stage.status === "skipped" ? "_Skipped._" : stage.content || "_No text captured._";
      return `## ${stage.prompt_label ?? stage.stage_id}\n\n${content}`;
    })
    .join("\n\n---\n\n");
}
