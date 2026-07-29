import { describe, expect, it } from "vitest";

import {
  replayShowDuration,
  replayShowElapsed,
  resolveReplayStage,
  revealedCaption,
  serverClockOffset,
} from "./replayTimeline";
import type { ReplayStageManifest } from "./types";

const stages: ReplayStageManifest[] = [
  {
    id: "intro",
    kind: "intro",
    offset_ms: 0,
    duration_ms: 4_500,
  },
  {
    id: "clip",
    kind: "clip",
    offset_ms: 4_500,
    duration_ms: 6_000,
    clip_id: "clip-1",
    clip_index: 0,
  },
  {
    id: "podium",
    kind: "podium",
    offset_ms: 10_500,
    duration_ms: 6_500,
  },
];

describe("replay show timeline", () => {
  it("resolves exact boundaries into the newly active stage", () => {
    expect(resolveReplayStage(stages, 0)?.stage.id).toBe("intro");
    expect(resolveReplayStage(stages, 4_499)?.stage.id).toBe(
      "intro",
    );
    const clip = resolveReplayStage(stages, 4_500);
    expect(clip?.stage.id).toBe("clip");
    expect(clip?.stageElapsedMs).toBe(0);
    expect(resolveReplayStage(stages, 10_500)?.stage.id).toBe(
      "podium",
    );
  });

  it("reports a late tune-in offset and clamps after completion", () => {
    const clip = resolveReplayStage(stages, 7_250);
    const complete = resolveReplayStage(stages, 30_000);

    expect(clip?.stage.id).toBe("clip");
    expect(clip?.stageElapsedMs).toBe(2_750);
    expect(clip?.progress).toBeCloseTo(2_750 / 6_000);
    expect(complete?.stage.id).toBe("podium");
    expect(complete?.stageElapsedMs).toBe(6_500);
    expect(complete?.showComplete).toBe(true);
    expect(replayShowDuration(stages)).toBe(17_000);
  });

  it("aligns client time to server-authored show time", () => {
    const clientNow = Date.parse("2026-07-28T20:00:00Z");
    const offset = serverClockOffset(
      "2026-07-28T20:00:02Z",
      clientNow,
    );

    expect(offset).toBe(2_000);
    expect(
      replayShowElapsed(
        "2026-07-28T19:59:57Z",
        clientNow + offset,
      ),
    ).toBe(5_000);
  });

  it("reveals words from elapsed time with punctuation pauses", () => {
    const caption =
      "Freeze the tape, racers! History just kicked down the door.";
    const early = revealedCaption(caption, 600, 6_500);
    const late = revealedCaption(caption, 5_500, 6_500);

    expect(early.split(" ").length).toBeLessThan(
      late.split(" ").length,
    );
    expect(late).toBe(caption);
    expect(revealedCaption(caption, 0, 6_500, true)).toBe(
      caption,
    );
  });

});
