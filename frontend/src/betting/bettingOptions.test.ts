import { afterEach, describe, expect, it, vi } from "vitest";

import type { LivePlayer, LiveRound, LiveState } from "../shared/types";
import {
  bettingOptionCanSubmit,
  deriveBettingOptions,
} from "./bettingOptions";

const player = {
  balance_cents: 20_000,
  round_staked_cents: 0,
} as LivePlayer;

function liveRound(
  id: number,
  state: LiveRound["state"],
  entryId: number,
): LiveRound {
  return {
    id,
    state,
    locks_at: "2026-07-29T20:01:00Z",
    entries: [{ id: entryId }],
  } as LiveRound;
}

function liveState(
  bettingRound: LiveRound,
  showRound: LiveRound | null,
): LiveState {
  return {
    round: bettingRound,
    show_round: showRound,
    room: {
      is_paused: false,
      max_round_stake_cents: 15_000,
    },
  } as LiveState;
}

describe("betting options", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("allows a next-round option while the current race is running", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-29T20:00:30Z"));
    const options = deriveBettingOptions(
      liveState(
        liveRound(2, "open", 22),
        liveRound(1, "racing", 11),
      ),
      player,
      500,
      0,
      0,
    );

    expect(options.roundId).toBe(2);
    expect(bettingOptionCanSubmit(options, 22)).toBe(true);
    expect(bettingOptionCanSubmit(options, 11)).toBe(false);
  });

  it("blocks all options when the market is closed or a bet is pending", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-29T20:00:30Z"));
    const state = liveState(
      liveRound(2, "locked", 22),
      liveRound(1, "racing", 11),
    );

    expect(
      bettingOptionCanSubmit(
        deriveBettingOptions(state, player, 500, 0, 0),
        22,
      ),
    ).toBe(false);
    state.round = liveRound(2, "open", 22);
    expect(
      bettingOptionCanSubmit(
        deriveBettingOptions(state, player, 500, 1, 0),
        22,
      ),
    ).toBe(false);
  });
});
