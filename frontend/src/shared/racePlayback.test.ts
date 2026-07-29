import { describe, expect, it } from "vitest";

import {
  frameProgress,
  interpolatedRacerFrame,
  interpolatedTrackItemFrame,
  neighboringFrames,
} from "./racePlayback";
import type { TimelineFrame } from "./types";

const timeline: TimelineFrame[] = [
  {
    tick: 0,
    racers: [
      {
        id: 1,
        x: 0.1,
        y: 0.2,
        state: "running",
        facing: 1,
        rotation: 0,
        scale: 1,
        sprite_key: "skeleton",
        place: null,
      },
    ],
    track_items: [{ id: 91, x: 0.2, y: 0.3, active: true }],
  },
  {
    tick: 10,
    racers: [
      {
        id: 1,
        x: 0.5,
        y: 0.4,
        state: "fallen",
        facing: -1,
        rotation: 30,
        scale: 1.5,
        sprite_key: "skeleton",
        place: null,
      },
    ],
    track_items: [{ id: 91, x: 0.6, y: 0.5, active: false }],
  },
];

describe("race playback interpolation", () => {
  it("finds surrounding frames and clamps progress", () => {
    const [current, next] = neighboringFrames(timeline, 5);

    expect(current.tick).toBe(0);
    expect(next.tick).toBe(10);
    expect(frameProgress(current, next, 5)).toBe(0.5);
    expect(frameProgress(current, next, -5)).toBe(0);
    expect(frameProgress(current, next, 15)).toBe(1);
  });

  it("interpolates continuous racer fields while retaining current state", () => {
    const frame = interpolatedRacerFrame(timeline, 1, 5);

    expect(frame).toMatchObject({
      rotation: 15,
      scale: 1.25,
      state: "running",
      facing: 1,
    });
    expect(frame?.x).toBeCloseTo(0.3);
    expect(frame?.y).toBeCloseTo(0.3);
  });

  it("rejects an empty timeline", () => {
    expect(() => neighboringFrames([], 0)).toThrow("Race timeline cannot be empty.");
  });

  it("interpolates moving track items while retaining lifecycle state", () => {
    const item = interpolatedTrackItemFrame(timeline, 91, 5);

    expect(item?.x).toBeCloseTo(0.4);
    expect(item?.y).toBeCloseTo(0.4);
    expect(item?.active).toBe(true);
  });
});
