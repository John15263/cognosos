import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Play,
  RefreshCw,
  ShieldAlert,
  Wand2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import cognososAvatar from "./assets/cognosos-avatar.png";
import { api } from "./lib/api";
import {
  IDLE_POLICIES,
  NOISE_IDLE_TIMEOUT,
  PIPELINE_VERSION,
  PRESSURE_WINDOW_SECONDS,
  buildBreakthroughPayload,
  compileBreakthroughMarkdown,
  countWords,
  createEmptyDrafts,
  formatTime,
  getActiveStages,
  shouldSuggestDecisionStage,
} from "./lib/breakthrough";
import type { BreakthroughStageId, StageDrafts, StageTimes } from "./lib/breakthrough";
import type { FlowSessionResponse } from "./lib/types";

type CaptureState = "idle" | "running" | "completed" | "failed" | "submitting";

const DRAFT_BACKUP_KEY = "cognosos.breakthroughDraft.v1";

type DraftBackup = {
  drafts: StageDrafts;
  currentStageId: BreakthroughStageId;
  decisionForced: boolean;
  decisionSkipped: boolean;
  stageStartedAt: StageTimes;
  stageCompletedAt: StageTimes;
  interruptionCount: number;
  savedAt: string;
};

function hasDraftText(drafts: StageDrafts) {
  return Object.values(drafts).some((draft) => draft.trim());
}

function loadDraftBackup(): DraftBackup | null {
  try {
    const raw = window.localStorage.getItem(DRAFT_BACKUP_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<DraftBackup>;
    const drafts = { ...createEmptyDrafts(), ...(parsed.drafts ?? {}) };
    if (!hasDraftText(drafts)) return null;
    return {
      drafts,
      currentStageId: parsed.currentStageId && parsed.currentStageId in drafts ? parsed.currentStageId : "mental_dump",
      decisionForced: Boolean(parsed.decisionForced),
      decisionSkipped: Boolean(parsed.decisionSkipped),
      stageStartedAt: parsed.stageStartedAt ?? {},
      stageCompletedAt: parsed.stageCompletedAt ?? {},
      interruptionCount: parsed.interruptionCount ?? 0,
      savedAt: parsed.savedAt ?? new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

function saveDraftBackup(backup: DraftBackup) {
  if (!hasDraftText(backup.drafts)) return clearDraftBackup();
  window.localStorage.setItem(DRAFT_BACKUP_KEY, JSON.stringify(backup));
}

function clearDraftBackup() {
  window.localStorage.removeItem(DRAFT_BACKUP_KEY);
}

export function App() {
  const [state, setState] = useState<CaptureState>("idle");
  const [pressureRemaining, setPressureRemaining] = useState(PRESSURE_WINDOW_SECONDS);
  const [idleRemaining, setIdleRemaining] = useState(NOISE_IDLE_TIMEOUT);
  const [interruptionCount, setInterruptionCount] = useState(0);
  const [lastResult, setLastResult] = useState<FlowSessionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stageDrafts, setStageDrafts] = useState<StageDrafts>(() => createEmptyDrafts());
  const [currentStageId, setCurrentStageId] = useState<BreakthroughStageId>("mental_dump");
  const [decisionForced, setDecisionForced] = useState(false);
  const [decisionSkipped, setDecisionSkipped] = useState(false);
  const [hasProtectedDraft, setHasProtectedDraft] = useState(() => Boolean(loadDraftBackup()));
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const stageDraftsRef = useRef(stageDrafts);
  const currentStageIdRef = useRef(currentStageId);
  const decisionStageEnabledRef = useRef(false);
  const decisionSkippedRef = useRef(decisionSkipped);
  const stateRef = useRef(state);
  const lastInputAtRef = useRef<number | null>(null);
  const isComposingRef = useRef(false);
  const interruptionCountRef = useRef(interruptionCount);
  const stageStartedAtRef = useRef<StageTimes>({});
  const stageCompletedAtRef = useRef<StageTimes>({});
  const dangerWasActiveRef = useRef(false);
  const submissionInFlightRef = useRef(false);
  const sessionStartedAtRef = useRef<number | null>(null);
  const pressureEndsAtRef = useRef<number | null>(null);

  const decisionSuggested = shouldSuggestDecisionStage(`${stageDrafts.mental_dump}\n${stageDrafts.future_reframe}`);
  const decisionStageEnabled = (decisionForced || decisionSuggested) && !decisionSkipped;
  const activeStages = useMemo(() => getActiveStages(decisionStageEnabled), [decisionStageEnabled]);
  const currentStage = activeStages.find((stage) => stage.id === currentStageId) ?? activeStages[activeStages.length - 1];
  const currentStageIndex = Math.max(0, activeStages.findIndex((stage) => stage.id === currentStage.id));
  const currentDraft = stageDrafts[currentStage.id];
  const currentWordCount = useMemo(() => countWords(currentDraft), [currentDraft]);
  const totalWordCount = useMemo(() => Object.values(stageDrafts).reduce((sum, text) => sum + countWords(text), 0), [stageDrafts]);
  const currentIdlePolicy = IDLE_POLICIES[currentStage.id];
  const idleRatio = Math.max(0, Math.min(1, idleRemaining / currentIdlePolicy.timeoutSeconds));
  const dangerRatio = 1 - idleRatio;
  const pressureActive = state === "running" && pressureRemaining > 0;
  const pressureUnlocked = state === "running" && pressureRemaining === 0;
  const visualDangerRatio = pressureActive ? (currentIdlePolicy.mode === "hard" ? dangerRatio : dangerRatio * 0.48) : 0;
  const isWriting = state === "running" || state === "submitting";
  const currentNudge =
    pressureActive && idleRemaining <= currentIdlePolicy.dangerWindowSeconds
      ? currentStage.nudges[Math.min(interruptionCount, currentStage.nudges.length - 1)]
      : null;
  const canGoBack = currentStageIndex > 0 && state === "running";
  const suggestedDecisionAvailable = currentStage.id === "future_reframe" && !decisionStageEnabled;

  useEffect(() => {
    stageDraftsRef.current = stageDrafts;
  }, [stageDrafts]);

  useEffect(() => {
    currentStageIdRef.current = currentStageId;
  }, [currentStageId]);

  useEffect(() => {
    decisionStageEnabledRef.current = decisionStageEnabled;
  }, [decisionStageEnabled]);

  useEffect(() => {
    decisionSkippedRef.current = decisionSkipped;
  }, [decisionSkipped]);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    interruptionCountRef.current = interruptionCount;
  }, [interruptionCount]);

  useEffect(() => {
    if (state !== "running") return;
    saveDraftBackup({
      drafts: stageDrafts,
      currentStageId,
      decisionForced,
      decisionSkipped,
      stageStartedAt: stageStartedAtRef.current,
      stageCompletedAt: stageCompletedAtRef.current,
      interruptionCount,
      savedAt: new Date().toISOString(),
    });
    setHasProtectedDraft(hasDraftText(stageDrafts));
  }, [state, stageDrafts, currentStageId, decisionForced, decisionSkipped, interruptionCount]);

  useEffect(() => {
    if (state !== "running") return;
    const interval = window.setInterval(() => {
      const pressureEndsAt = pressureEndsAtRef.current;
      const pressureLeft = pressureEndsAt ? Math.max(0, Math.ceil((pressureEndsAt - Date.now()) / 1000)) : 0;
      setPressureRemaining(pressureLeft);

      if (pressureLeft === 0) {
        dangerWasActiveRef.current = false;
        setIdleRemaining(IDLE_POLICIES[currentStageIdRef.current].timeoutSeconds);
        return;
      }

      if (isComposingRef.current) {
        lastInputAtRef.current = Date.now();
        setIdleRemaining(IDLE_POLICIES[currentStageIdRef.current].timeoutSeconds);
        return;
      }

      const lastInput = lastInputAtRef.current;
      if (lastInput === null) return;
      const idlePolicy = IDLE_POLICIES[currentStageIdRef.current];
      const elapsed = Math.floor((Date.now() - lastInput) / 1000);
      const nextIdle = Math.max(0, idlePolicy.timeoutSeconds - elapsed);
      setIdleRemaining(nextIdle);

      if (nextIdle <= idlePolicy.dangerWindowSeconds && !dangerWasActiveRef.current) {
        dangerWasActiveRef.current = true;
        setInterruptionCount((value) => value + 1);
      }

      if (nextIdle <= 0 && idlePolicy.mode === "hard") {
        window.clearInterval(interval);
        void failSession();
      }
    }, 1000);

    return () => window.clearInterval(interval);
  }, [state]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (stateRef.current !== "running") return;
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        void advanceStage();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  function markInputActivity(stageId = currentStageIdRef.current) {
    const now = Date.now();
    dangerWasActiveRef.current = false;
    lastInputAtRef.current = now;
    setIdleRemaining(IDLE_POLICIES[stageId].timeoutSeconds);
  }

  function startSession() {
    const now = new Date().toISOString();
    const nowMs = Date.now();
    const backup = loadDraftBackup();
    const nextDrafts = backup?.drafts ?? createEmptyDrafts();
    const nextDecisionForced = backup?.decisionForced ?? false;
    const nextDecisionSkipped = backup?.decisionSkipped ?? false;
    const nextDecisionEnabled =
      (nextDecisionForced || shouldSuggestDecisionStage(`${nextDrafts.mental_dump}\n${nextDrafts.future_reframe}`)) && !nextDecisionSkipped;
    const restoredStages = getActiveStages(nextDecisionEnabled);
    const nextStageId = backup && restoredStages.some((stage) => stage.id === backup.currentStageId) ? backup.currentStageId : "mental_dump";
    const initialStartedAt = backup?.stageStartedAt ?? { mental_dump: now };
    initialStartedAt[nextStageId] = initialStartedAt[nextStageId] ?? now;
    submissionInFlightRef.current = false;
    sessionStartedAtRef.current = nowMs;
    pressureEndsAtRef.current = nowMs + PRESSURE_WINDOW_SECONDS * 1000;
    setError(null);
    setLastResult(null);
    setStageDrafts(nextDrafts);
    stageDraftsRef.current = nextDrafts;
    setCurrentStageId(nextStageId);
    currentStageIdRef.current = nextStageId;
    setDecisionForced(nextDecisionForced);
    setDecisionSkipped(nextDecisionSkipped);
    decisionStageEnabledRef.current = nextDecisionEnabled;
    decisionSkippedRef.current = nextDecisionSkipped;
    stageStartedAtRef.current = initialStartedAt;
    stageCompletedAtRef.current = backup?.stageCompletedAt ?? {};
    setPressureRemaining(PRESSURE_WINDOW_SECONDS);
    setIdleRemaining(IDLE_POLICIES[nextStageId].timeoutSeconds);
    setInterruptionCount(backup?.interruptionCount ?? 0);
    interruptionCountRef.current = backup?.interruptionCount ?? 0;
    dangerWasActiveRef.current = false;
    lastInputAtRef.current = Date.now();
    setState("running");
    window.setTimeout(() => textareaRef.current?.focus(), 60);
  }

  function elapsedSessionSeconds() {
    const startedAt = sessionStartedAtRef.current;
    if (!startedAt) return PRESSURE_WINDOW_SECONDS;
    return Math.max(1, Math.round((Date.now() - startedAt) / 1000));
  }

  function handleDraftChange(value: string) {
    const nextDrafts = { ...stageDraftsRef.current, [currentStage.id]: value };
    stageDraftsRef.current = nextDrafts;
    setStageDrafts(nextDrafts);
    markInputActivity();
  }

  async function exitApp() {
    try {
      await api.shutdown();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to exit CognosOS.");
    }
  }

  function markStageComplete(stageId: BreakthroughStageId) {
    const now = new Date().toISOString();
    const nextTimes = { ...stageCompletedAtRef.current, [stageId]: now };
    stageCompletedAtRef.current = nextTimes;
    return nextTimes;
  }

  function startStage(stageId: BreakthroughStageId) {
    const now = new Date().toISOString();
    setCurrentStageId(stageId);
    currentStageIdRef.current = stageId;
    const nextTimes = { ...stageStartedAtRef.current, [stageId]: stageStartedAtRef.current[stageId] ?? now };
    stageStartedAtRef.current = nextTimes;
    markInputActivity(stageId);
    window.setTimeout(() => textareaRef.current?.focus(), 40);
  }

  async function advanceStage(forceDecision = false) {
    if (stateRef.current === "submitting") return;
    const stageId = currentStageIdRef.current;
    markStageComplete(stageId);

    if (stageId === "future_reframe" && forceDecision) {
      setDecisionForced(true);
      setDecisionSkipped(false);
      decisionStageEnabledRef.current = true;
      decisionSkippedRef.current = false;
      startStage("decision_snapshot");
      return;
    }

    const active = getActiveStages(decisionStageEnabledRef.current);
    const index = active.findIndex((stage) => stage.id === stageId);
    const nextStage = active[index + 1];
    if (!nextStage) {
      await completeSession();
      return;
    }
    startStage(nextStage.id);
  }

  function goBack() {
    if (!canGoBack) return;
    const previousStage = activeStages[currentStageIndex - 1];
    if (previousStage) startStage(previousStage.id);
  }

  function skipDecision() {
    setDecisionSkipped(true);
    decisionStageEnabledRef.current = false;
    decisionSkippedRef.current = true;
    markStageComplete("decision_snapshot");
    startStage("scaffold_action");
  }

  async function completeSession() {
    if (stateRef.current === "submitting" || submissionInFlightRef.current) return;
    submissionInFlightRef.current = true;
    const completedAt = markStageComplete(currentStageIdRef.current);
    const structuredPayload = buildBreakthroughPayload({
      drafts: stageDraftsRef.current,
      decisionStageEnabled: decisionStageEnabledRef.current,
      decisionSkipped: decisionSkippedRef.current,
      stageStartedAt: stageStartedAtRef.current,
      stageCompletedAt: completedAt,
      interruptionCount: interruptionCountRef.current,
    });
    const content = compileBreakthroughMarkdown(structuredPayload);
    const finalWordCount = Object.values(stageDraftsRef.current).reduce((sum, text) => sum + countWords(text), 0);
    setState("submitting");
    try {
      const result = await api.createFlowSession({
        prompt_id: "breakthrough_canvas_v1_2",
        prompt_title: "Breakthrough Canvas",
        prompt_cues: ["breakthrough_canvas"],
        content,
        compiled_markdown: content,
        mode: "hard",
        status: "completed",
        duration_seconds: elapsedSessionSeconds(),
        idle_timeout_seconds: IDLE_POLICIES.mental_dump.timeoutSeconds,
        final_word_count: finalWordCount,
        interruption_count: interruptionCountRef.current,
        structured_payload: structuredPayload,
        pipeline_version: structuredPayload.pipeline_version,
        decision_stage_enabled: structuredPayload.decision_stage_enabled,
        stages: structuredPayload.stages,
      });
      clearDraftBackup();
      setHasProtectedDraft(false);
      setLastResult(result);
      setState("completed");
    } catch (caught) {
      submissionInFlightRef.current = false;
      setError(caught instanceof Error ? caught.message : "Failed to submit session.");
      setState("idle");
    }
  }

  async function failSession() {
    if (stateRef.current === "submitting" || submissionInFlightRef.current) return;
    submissionInFlightRef.current = true;
    const failedWordCount = Object.values(stageDraftsRef.current).reduce((sum, text) => sum + countWords(text), 0);
    clearDraftBackup();
    setHasProtectedDraft(false);
    setStageDrafts(createEmptyDrafts());
    setState("submitting");
    try {
      const result = await api.createFlowSession({
        prompt_id: "breakthrough_canvas_v1_2",
        prompt_title: "Breakthrough Canvas",
        prompt_cues: ["breakthrough_canvas"],
        content: "",
        compiled_markdown: "",
        mode: "hard",
        status: "failed",
        duration_seconds: elapsedSessionSeconds(),
        idle_timeout_seconds: IDLE_POLICIES.mental_dump.timeoutSeconds,
        final_word_count: failedWordCount,
        interruption_count: interruptionCountRef.current + 1,
        structured_payload: {
          writing_mode: "breakthrough_canvas",
          pipeline_version: PIPELINE_VERSION,
          decision_stage_enabled: false,
          stages: [],
        },
        pipeline_version: PIPELINE_VERSION,
        decision_stage_enabled: false,
        stages: [],
      });
      setLastResult(result);
      setState("failed");
    } catch (caught) {
      submissionInFlightRef.current = false;
      setError(caught instanceof Error ? caught.message : "Failed to record failed session.");
      setState("failed");
    }
  }

  const isLocked = state !== "running";
  const outcomeNotePath = state === "failed" ? null : (lastResult?.session.note_path ?? null);
  const outcomeWordCount = lastResult?.session.final_word_count ?? totalWordCount;
  const hasOutcome = Boolean(lastResult) || state === "failed";
  const launchCopy =
    state === "failed"
      ? "You stopped too long. The canvas was cleared. Start again when you are ready to keep moving."
      : "When your mind is loud, do not hand yourself to the noise. Dump it, widen time, snapshot judgment, act, then let reality check the model.";
  const launchAction =
    state === "failed"
      ? "Try Again"
      : state === "completed"
        ? "Start Next Canvas"
        : hasProtectedDraft
          ? "Resume Draft"
        : "Start Breakthrough Canvas";
  const mentalDumpText = stageDrafts.mental_dump.trim();
  const timeCapsuleExcerpt =
    currentStage.id === "future_reframe" && mentalDumpText
      ? `${mentalDumpText.slice(0, 360)}${mentalDumpText.length > 360 ? "..." : ""}`
      : "";
  const writingPressureStyle = {
    "--idle-ratio": idleRatio.toFixed(3),
    "--danger-ratio": visualDangerRatio.toFixed(3),
    "--draft-opacity": (pressureActive ? 0.24 + idleRatio * 0.76 : 1).toFixed(3),
    "--prompt-opacity": (pressureActive ? 0.18 + idleRatio * 0.52 : 0.7).toFixed(3),
  } as CSSProperties;

  return (
    <main className={`danger-app ${state} ${isWriting ? "writing" : ""}`}>
      <button className="app-exit" onClick={() => void exitApp()} disabled={state === "submitting"}>
        Exit
      </button>
      {isWriting ? (
        <section
          className={`writing-room ${currentIdlePolicy.mode}-pressure ${currentStage.id === "decision_snapshot" ? "side-prompt-stage" : ""} ${currentNudge ? "nudge-active" : ""} ${timeCapsuleExcerpt ? "has-time-capsule" : ""}`}
          style={writingPressureStyle}
          aria-label="Breakthrough writing room"
        >
          <button
            className="room-tool room-close"
            onClick={() => void failSession()}
            disabled={state === "submitting"}
            aria-label="Abort and clear"
            title="Abort and clear"
          >
            <X size={25} />
          </button>

          <div className="room-status" aria-live="polite">
            <strong>{state === "submitting" ? "Saving" : pressureUnlocked ? "Unlocked" : formatTime(pressureRemaining)}</strong>
            <span>{pressureUnlocked ? "finish when ready" : currentIdlePolicy.mode === "hard" ? "keep typing" : "stay with it"}</span>
            <em>{pressureUnlocked ? "no pressure" : currentIdlePolicy.mode === "soft" && idleRemaining === 0 ? "nudge" : `${idleRemaining}s`}</em>
          </div>

          <div className="room-stage">
            <span>{currentStage.label}</span>
            <strong>{currentStage.title}</strong>
            <p>{currentStage.subtitle}</p>
          </div>

          <div className="room-writing-prompt" aria-label="Writing prompt">
            <span>Writing prompt</span>
            <p>{currentStage.ghostStarter}</p>
          </div>

          {timeCapsuleExcerpt ? (
            <blockquote className="time-capsule-excerpt" aria-label="Past time capsule excerpt">
              <span>来自过去的时间胶囊</span>
              <p>{timeCapsuleExcerpt}</p>
            </blockquote>
          ) : null}

          <textarea
            ref={textareaRef}
            className="danger-textarea"
            value={currentDraft}
            disabled={isLocked}
            onChange={(event) => handleDraftChange(event.target.value)}
            onCompositionStart={() => {
              isComposingRef.current = true;
              markInputActivity();
            }}
            onCompositionEnd={(event) => {
              isComposingRef.current = false;
              handleDraftChange(event.currentTarget.value);
            }}
            placeholder={currentStage.ghostStarter}
            aria-label="Breakthrough stage editor"
          />

          {currentNudge ? <div className="room-nudge">{currentNudge}</div> : null}
          {state === "submitting" ? (
            <div className="room-saving">
              <RefreshCw size={18} />
              Writing to Vault
            </div>
          ) : null}
          <div className="stage-actions">
            <button className="secondary-action compact-action" onClick={goBack} disabled={!canGoBack || isLocked}>
              <ChevronLeft size={17} />
              Back
            </button>
            {suggestedDecisionAvailable ? (
              <button className="secondary-action compact-action" onClick={() => void advanceStage(true)} disabled={isLocked}>
                <Wand2 size={17} />
                Decision Trace
              </button>
            ) : null}
            {currentStage.id === "decision_snapshot" ? (
              <button className="secondary-action compact-action" onClick={skipDecision} disabled={isLocked}>
                Skip Decision
              </button>
            ) : null}
            <button className="start-writing compact-action" onClick={() => void advanceStage()} disabled={isLocked}>
              {currentStage.advanceLabel}
              <ChevronRight size={17} />
            </button>
            <button className="secondary-action compact-action" onClick={() => void completeSession()} disabled={isLocked}>
              Save Early
            </button>
          </div>
          <div className="room-wordcount">
            {currentWordCount} stage words · {totalWordCount} total
          </div>
        </section>
      ) : (
        <>
          <section className={`launch-hero ${hasOutcome ? "has-outcome" : ""}`} aria-label="Breakthrough Canvas launch">
            <div className="hero-lockup">
              <img className={`dignitas-avatar ${state === "failed" ? "failed" : ""}`} src={cognososAvatar} alt="" />
              <h1 className="launch-title breakthrough-title">
                <span>{state === "failed" ? "Canvas" : "Breakthrough"}</span>
                <strong>{state === "failed" ? "Cleared" : "Canvas"}</strong>
              </h1>
            </div>
            <p className="launch-copy">{launchCopy}</p>

            <div className="session-bubble">Pressure window: {PRESSURE_WINDOW_SECONDS / 60} minutes</div>
            <button className="start-writing" onClick={() => startSession()}>
              <Play size={20} />
              {launchAction}
            </button>

            <div className="prompt-line">
              <span>Flow:</span>
              <strong>倒出噪音 → 拉开时间 → 定格判断 → 落地行动 → 交给现实</strong>
            </div>

            {state === "failed" ? (
              <div className="danger-note hero-note">
                <ShieldAlert size={18} />
                <span>Hard mode fired after {NOISE_IDLE_TIMEOUT}s without input during the pressure window. The canvas was cleared before writeback.</span>
              </div>
            ) : null}
            {error ? <div className="error-note hero-note">{error}</div> : null}
          </section>

          {hasOutcome ? (
            <section className="after-session" id="after-session" aria-label="After the session">
              <section className={`outcome-panel ${state === "completed" ? "completed" : state}`} aria-label="Latest writing outcome">
                <div className="outcome-header">
                  <div>
                    <h3>{state === "failed" ? "This canvas was cleared" : "Last canvas completed"}</h3>
                    <p>
                      {state === "failed"
                        ? "No Obsidian note was written for the cleared canvas."
                        : "Your staged writing has been preserved as judgment, action, and review material."}
                    </p>
                    <p className="outcome-meta">{outcomeWordCount} words captured.</p>
                  </div>
                </div>

                <div className="outcome-actions">
                  <button className="start-writing compact-action" onClick={() => startSession()}>
                    <Play size={18} />
                    {state === "failed" ? "Try Again" : "Start Next Canvas"}
                  </button>
                  {outcomeNotePath ? (
                    <div className="note-path">
                      <ExternalLink size={15} />
                      <span>{outcomeNotePath}</span>
                    </div>
                  ) : null}
                </div>
              </section>
            </section>
          ) : null}
        </>
      )}
    </main>
  );
}
