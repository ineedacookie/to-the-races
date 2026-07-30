import { describe, expect, it } from "vitest";

import type { LivePlayer, LiveRound } from "../shared/types";
import {
  applyLawnMowingReceipt,
  lawnMowingForRound,
  shouldShowLawnMowingCallout,
} from "./lawnMowing";

const round = { id: 12 } as LiveRound;
const player = {
  lawn_mowing: { eligible: true, stale: false, session: null },
} as LivePlayer;

describe("lawn mowing state", () => {
  it("shows an eligible unused job", () => {
    expect(shouldShowLawnMowingCallout(player, round)).toBe(true);
  });

  it("marks a session from another round stale", () => {
    const stalePlayer = {
      ...player,
      lawn_mowing: {
        eligible: true,
        stale: false,
        session: {
          id: 1,
          round_id: 11,
          completed: false,
          mowed_cells: [],
          cell_count: 60,
          columns: 10,
          rows: 6,
          reward_cents: 2_000,
        },
      },
    };
    expect(lawnMowingForRound(stalePlayer, round).stale).toBe(true);
  });

  it("applies server progress and completion", () => {
    const active = {
      eligible: true,
      stale: false,
      session: {
        id: 3,
        round_id: 12,
        completed: false,
        mowed_cells: [0],
        cell_count: 60,
        columns: 10,
        rows: 6,
        reward_cents: 2_000,
      },
    };
    const updated = applyLawnMowingReceipt(active, {
      session_id: 3,
      mowed_cells: [0, 1],
      completed: true,
    });
    expect(updated.eligible).toBe(false);
    expect(updated.session?.mowed_cells).toEqual([0, 1]);
    expect(updated.session?.completed).toBe(true);
  });
});
