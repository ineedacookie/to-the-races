import { describe, expect, it } from "vitest";

import type {
  LiveRound,
  LiveState,
  RacePlayback,
  ReplayMontage,
} from "../shared/types";
import { mergeDisplayState } from "./liveState";

const race = {
  seed: 42,
  generated_at: "2026-07-29T20:00:00Z",
  tick_rate: 20,
  duration_ticks: 600,
  timeline: [{ tick: 0, racers: [] }],
  events: [],
} as RacePlayback;

const replay = {
  playback_key: "round-1",
  show_started_at: "2026-07-29T20:01:00Z",
  stages: [],
} as unknown as ReplayMontage;

function round(id: number, state: LiveRound["state"]): LiveRound {
  return {
    id,
    number: id,
    state,
    opened_at: "2026-07-29T20:00:00Z",
    locks_at: "2026-07-29T20:00:30Z",
    race_starts_at: "2026-07-29T20:00:33Z",
    race_ends_at: "2026-07-29T20:01:03Z",
    results_end_at: "2026-07-29T20:02:00Z",
    finish_countdown_starts_at: null,
    finish_countdown_ends_at: null,
    entries: [],
    item_uses: [],
    seats: [],
    seat_markets: [],
    result: {},
  };
}

function state(
  bettingRound: LiveRound,
  showRound: LiveRound | null,
): LiveState {
  return {
    protocol_version: 17,
    server_time: "2026-07-29T20:00:10Z",
    room: {
      name: "Test room",
      is_paused: false,
      broadcast_enabled: true,
      betting_seconds: 30,
      max_round_stake_cents: 15_000,
      max_inventory_items: 4,
      max_round_item_spend_cents: 25_000,
      max_round_item_uses: 4,
      item_catalog: [],
      seat_catalog: [],
      upgrade_catalog: [],
    },
    round: bettingRound,
    show_round: showRound,
    player: null,
    leaderboard: [],
    debt_board: [],
  };
}

describe("mergeDisplayState", () => {
  it("keeps live race playback when a bet updates the next-round market", () => {
    const bettingRound = round(2, "open");
    const liveRound = { ...round(1, "racing"), race };
    const current = state(bettingRound, liveRound);
    const updatedBettingRound = {
      ...bettingRound,
      entries: [{ id: 99, total_staked_cents: 500 }],
    } as LiveRound;
    const incoming = state(updatedBettingRound, round(1, "racing"));

    const merged = mergeDisplayState(current, incoming);

    expect(merged.round?.entries[0]?.total_staked_cents).toBe(500);
    expect(merged.show_round?.race).toBe(race);
  });

  it("keeps an active replay while partial market updates arrive", () => {
    const current = state(
      round(2, "open"),
      { ...round(1, "results"), display_replay: replay },
    );
    const incoming = state(round(2, "open"), round(1, "results"));

    expect(
      mergeDisplayState(current, incoming).show_round?.display_replay,
    ).toBe(replay);
  });

  it("does not carry playback into a different show round", () => {
    const current = state(round(2, "open"), {
      ...round(1, "racing"),
      race,
    });
    const incoming = state(round(3, "open"), round(2, "racing"));

    expect(mergeDisplayState(current, incoming).show_round?.race).toBeUndefined();
  });
});
