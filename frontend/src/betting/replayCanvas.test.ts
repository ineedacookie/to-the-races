import { describe, expect, it } from "vitest";

import type { ReplayMontageClip } from "../shared/types";
import { replayTickForOffset } from "./replayCanvas";

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
});
