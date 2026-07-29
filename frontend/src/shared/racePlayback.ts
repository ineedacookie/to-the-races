import type { RacerFrame, TimelineFrame, TrackItemFrame } from "./types";

export function frameForRacer(
  frame: TimelineFrame,
  racerId: number,
): RacerFrame | undefined {
  return frame.racers.find((racer) => racer.id === racerId);
}

export function neighboringFrames(
  timeline: readonly TimelineFrame[],
  tick: number,
): [TimelineFrame, TimelineFrame] {
  if (timeline.length === 0) {
    throw new Error("Race timeline cannot be empty.");
  }
  let low = 0;
  let high = timeline.length - 1;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    const candidate = timeline[middle];
    if (candidate !== undefined && candidate.tick <= tick) {
      low = middle;
    } else {
      high = middle - 1;
    }
  }
  const current = timeline[low] ?? timeline[0];
  const next = timeline[Math.min(low + 1, timeline.length - 1)] ?? current;
  if (current === undefined || next === undefined) {
    throw new Error("Race timeline cannot be empty.");
  }
  return [current, next];
}

export function frameProgress(
  current: TimelineFrame,
  next: TimelineFrame,
  tick: number,
): number {
  const distance = Math.max(next.tick - current.tick, 1);
  return Math.min(Math.max((tick - current.tick) / distance, 0), 1);
}

function interpolate(start: number, finish: number, progress: number): number {
  return start + (finish - start) * progress;
}

export function interpolatedRacerFrame(
  timeline: readonly TimelineFrame[],
  racerId: number,
  tick: number,
): RacerFrame | null {
  const [currentFrame, nextFrame] = neighboringFrames(timeline, tick);
  const current = frameForRacer(currentFrame, racerId);
  const next = frameForRacer(nextFrame, racerId) ?? current;
  if (current === undefined || next === undefined) {
    return null;
  }
  const progress = frameProgress(currentFrame, nextFrame, tick);
  return {
    ...current,
    x: interpolate(current.x, next.x, progress),
    y: interpolate(current.y, next.y, progress),
    rotation: interpolate(current.rotation, next.rotation, progress),
    scale: interpolate(current.scale, next.scale, progress),
  };
}

export function interpolatedTrackItemFrame(
  timeline: readonly TimelineFrame[],
  effectId: number,
  tick: number,
): TrackItemFrame | null {
  const [currentFrame, nextFrame] = neighboringFrames(timeline, tick);
  const current = currentFrame.track_items?.find((item) => item.id === effectId);
  const next = nextFrame.track_items?.find((item) => item.id === effectId) ?? current;
  if (current === undefined || next === undefined) {
    return null;
  }
  const progress = frameProgress(currentFrame, nextFrame, tick);
  return {
    ...current,
    x: interpolate(current.x, next.x, progress),
    y: interpolate(current.y, next.y, progress),
  };
}
