import { describe, expect, it } from "vitest";

import type { RaceEvent, RacePlayback } from "../shared/types";
import {
  firstFinisherAlreadyPassed,
  isOfficialFirstFinish,
  isPriorityRaceEvent,
  racePlaybackKey,
  shouldCelebrateFirstFinisher,
} from "./firstFinisher";

function finishEvent(place: number | null | undefined, tick = 10): RaceEvent {
  return {
    tick,
    kind: "finish",
    racer_id: 1,
    message: "Finished!",
    finish_place: place,
  };
}

describe("firstFinisher helpers", () => {
  it("recognizes the official first-place finish event", () => {
    expect(isOfficialFirstFinish(finishEvent(1))).toBe(true);
    expect(isOfficialFirstFinish(finishEvent(2))).toBe(false);
    expect(isOfficialFirstFinish(finishEvent(null))).toBe(false);
    expect(isOfficialFirstFinish({ ...finishEvent(1), kind: "stumble" })).toBe(false);
  });

  it("celebrates only the first official place-one crossing", () => {
    expect(shouldCelebrateFirstFinisher(finishEvent(1), false)).toBe(true);
    expect(shouldCelebrateFirstFinisher(finishEvent(1), true)).toBe(false);
    expect(shouldCelebrateFirstFinisher(finishEvent(2), false)).toBe(false);
  });

  it("holds elimination events long enough to be readable", () => {
    expect(isPriorityRaceEvent(finishEvent(1))).toBe(true);
    expect(isPriorityRaceEvent(finishEvent(2))).toBe(false);
    expect(isPriorityRaceEvent({ ...finishEvent(undefined), kind: "knockout" })).toBe(true);
    expect(isPriorityRaceEvent({ ...finishEvent(undefined), kind: "destroyed" })).toBe(true);
    expect(isPriorityRaceEvent({ ...finishEvent(undefined), kind: "timeout" })).toBe(true);
    expect(isPriorityRaceEvent({ ...finishEvent(undefined), kind: "stumble" })).toBe(false);
  });

  it("treats skipped reconnect playback as already celebrated", () => {
    const events = [finishEvent(1, 12), finishEvent(2, 20)];
    expect(firstFinisherAlreadyPassed(events, 0)).toBe(false);
    expect(firstFinisherAlreadyPassed(events, 1)).toBe(true);
    expect(firstFinisherAlreadyPassed(events, 2)).toBe(true);
  });

  it("changes playback identity when a live item regenerates the race", () => {
    const playback: RacePlayback = {
      seed: 42,
      generated_at: "2026-07-27T21:00:00Z",
      tick_rate: 20,
      duration_ticks: 400,
      timeline: [],
      events: [finishEvent(1)],
    };

    expect(racePlaybackKey(7, playback)).not.toBe(
      racePlaybackKey(7, {
        ...playback,
        generated_at: "2026-07-27T21:00:01Z",
      }),
    );
  });
});
