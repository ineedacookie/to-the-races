import { describe, expect, it } from "vitest";

import type { ReplayMontageClip } from "../shared/types";
import {
  replayRacerAnimationElapsed,
  replayTickForOffset,
  replayTrackItemPosition,
} from "./replayCanvas";

const clip: ReplayMontageClip = {
  id: "clip-1",
  kind: "incident",
  anchor_tick: 30,
  start_tick: 10,
  end_tick: 50,
  playback_rate: 0.5,
  caption: "A dramatic incident.",
  focus_racer_ids: [1],
  event_kind: "stumble",
  effect_id: null,
  consumed_effect_ids_at_start: [],
  timeline: [],
  events: [],
};

describe("replay canvas seeking", () => {
  it("joins halfway through a clip at the matching replay tick", () => {
    // Forty ticks at 20Hz is two seconds, played at half speed for four seconds.
    expect(replayTickForOffset(clip, 20, 2_000)).toBe(30);
    expect(replayTickForOffset(clip, 20, 4_000)).toBe(50);
    expect(replayTickForOffset(clip, 20, 9_000)).toBe(50);
  });

  it("uses the authored anchor frame under reduced motion", () => {
    expect(replayTickForOffset(clip, 20, 2_000, true)).toBe(
      clip.anchor_tick,
    );
  });

  it("keeps normalized item placement coordinates unchanged", () => {
    expect(
      replayTrackItemPosition(
        { position: 0.62, lane: 0.8 },
        null,
      ),
    ).toEqual({ x: 0.62, y: 0.8 });
    expect(
      replayTrackItemPosition(
        { position: 0.62, lane: 0.8 },
        { x: 0.7, y: 0.35 },
      ),
    ).toEqual({ x: 0.7, y: 0.35 });
  });

  it("freezes sprite animation without rewinding race playback", () => {
    expect(replayRacerAnimationElapsed(0, 4_000, false)).toBe(0);
    expect(replayRacerAnimationElapsed(1_200, 4_000, false)).toBe(1_200);
    expect(replayRacerAnimationElapsed(4_000, 4_000, false)).toBe(0);
    expect(replayRacerAnimationElapsed(9_000, 4_000, false)).toBe(0);
    expect(replayRacerAnimationElapsed(1_200, 4_000, true)).toBe(0);
    expect(replayTickForOffset(clip, 20, 9_000)).toBe(50);
  });
});
