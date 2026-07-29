import type {
  ReplayShowStage,
  ReplayStageManifest,
} from "./types";

export interface ReplayStagePosition<T extends ReplayStageManifest | ReplayShowStage> {
  stage: T;
  stageIndex: number;
  showElapsedMs: number;
  stageElapsedMs: number;
  stageRemainingMs: number;
  progress: number;
  showComplete: boolean;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

export function serverClockOffset(serverTime: string, clientNow = Date.now()): number {
  const parsed = Date.parse(serverTime);
  return Number.isFinite(parsed) ? parsed - clientNow : 0;
}

export function replayShowElapsed(
  showStartedAt: string,
  serverNow: number,
): number {
  const startedAt = Date.parse(showStartedAt);
  if (!Number.isFinite(startedAt)) {
    return 0;
  }
  return Math.max(serverNow - startedAt, 0);
}

export function replayShowDuration(
  stages: readonly (ReplayStageManifest | ReplayShowStage)[],
): number {
  const last = stages.at(-1);
  return last === undefined ? 0 : last.offset_ms + last.duration_ms;
}

export function resolveReplayStage<
  T extends ReplayStageManifest | ReplayShowStage,
>(
  stages: readonly T[],
  showElapsedMs: number,
): ReplayStagePosition<T> | null {
  if (stages.length === 0) {
    return null;
  }
  const elapsed = Math.max(showElapsedMs, 0);
  const duration = replayShowDuration(stages);
  const activeIndex = stages.findIndex(
    (stage) =>
      elapsed >= stage.offset_ms &&
      elapsed < stage.offset_ms + stage.duration_ms,
  );
  const stageIndex = activeIndex >= 0 ? activeIndex : stages.length - 1;
  const stage = stages[stageIndex];
  if (stage === undefined) {
    return null;
  }
  const stageElapsedMs = clamp(
    elapsed - stage.offset_ms,
    0,
    stage.duration_ms,
  );
  return {
    stage,
    stageIndex,
    showElapsedMs: elapsed,
    stageElapsedMs,
    stageRemainingMs: Math.max(stage.duration_ms - stageElapsedMs, 0),
    progress:
      stage.duration_ms <= 0
        ? 1
        : clamp(stageElapsedMs / stage.duration_ms, 0, 1),
    showComplete: elapsed >= duration,
  };
}

function revealWeight(word: string): number {
  if (/[.!?]["')\]]?$/u.test(word)) {
    return 1.85;
  }
  if (/[,;:]["')\]]?$/u.test(word)) {
    return 1.4;
  }
  return 1;
}

export function revealedCaption(
  caption: string,
  stageElapsedMs: number,
  stageDurationMs: number,
  reducedMotion = false,
): string {
  const words = caption.trim().split(/\s+/u).filter(Boolean);
  if (words.length === 0 || reducedMotion) {
    return caption;
  }
  const revealWindowMs = Math.max(stageDurationMs * 0.82, 1);
  const revealProgress = clamp(stageElapsedMs / revealWindowMs, 0, 1);
  const weights = words.map(revealWeight);
  const totalWeight = weights.reduce((total, weight) => total + weight, 0);
  const targetWeight = totalWeight * revealProgress;
  let accumulated = 0;
  let revealedCount = 0;
  for (const weight of weights) {
    accumulated += weight;
    if (accumulated <= targetWeight || revealedCount === 0) {
      revealedCount += 1;
      continue;
    }
    break;
  }
  if (revealProgress >= 1) {
    revealedCount = words.length;
  }
  return words.slice(0, revealedCount).join(" ");
}
