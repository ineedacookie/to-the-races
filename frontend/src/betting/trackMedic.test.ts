import { describe, expect, it } from "vitest";

import type { LivePlayer, LiveRound, TrackMedicState } from "../shared/types";
import {
  applyTrackMedicPatch,
  shouldShowTrackMedicCallout,
  trackMedicCalloutCopy,
  trackMedicForRound,
  woundButtonLabel,
} from "./trackMedic";

function player(overrides: Partial<LivePlayer> = {}): LivePlayer {
  return {
    id: 1,
    nickname: "Tester",
    avatar_recipe: {
      skin: 0,
      eyes: 0,
      bottoms: 0,
      tops: 0,
      shoes: 0,
      hair: 0,
    },
    avatar_version: "v1",
    avatar_url: "/api/players/1/avatar/",
    replay_preference: "ask",
    balance_cents: 0,
    round_staked_cents: 0,
    round_stake_remaining_cents: 15_000,
    round_item_spent_cents: 0,
    bets: [],
    inventory: [],
    item_uses: [],
    seat_claim: null,
    owned_upgrades: [],
    effective_inventory_capacity: 4,
    next_inventory_upgrade: null,
    recent_ledger: [],
    betting_record: {
      winning_bets: 0,
      losing_bets: 0,
      total_bets: 0,
      total_staked_cents: 0,
      total_returned_cents: 0,
      net_cents: 0,
    },
    track_medic: {
      eligible: true,
      session: null,
      stale: false,
    },
    ...overrides,
  };
}

function round(overrides: Partial<LiveRound> = {}): LiveRound {
  return {
    id: 9,
    number: 9,
    state: "open",
    opened_at: "2026-07-27T00:00:00Z",
    locks_at: "2026-07-27T00:05:00Z",
    race_starts_at: "2026-07-27T00:06:00Z",
    race_ends_at: "2026-07-27T00:08:00Z",
    results_end_at: "2026-07-27T00:09:00Z",
    finish_countdown_starts_at: null,
    finish_countdown_ends_at: null,
    entries: [],
    item_uses: [],
    seats: [],
    seat_markets: [],
    result: {},
    ...overrides,
  };
}

describe("trackMedic helpers", () => {
  it("shows the callout when eligible below ten dollars", () => {
    expect(shouldShowTrackMedicCallout(player({ balance_cents: 999 }), round())).toBe(true);
  });

  it("hides the callout when the server marks the player ineligible", () => {
    expect(
      shouldShowTrackMedicCallout(
        player({
          balance_cents: 1_000,
          track_medic: { eligible: false, session: null, stale: false },
        }),
        round(),
      ),
    ).toBe(false);
  });

  it("keeps the callout available throughout the current round", () => {
    const eligible = player({ balance_cents: 999 });

    expect(shouldShowTrackMedicCallout(eligible, round({ state: "locked" }))).toBe(true);
    expect(shouldShowTrackMedicCallout(eligible, round({ state: "racing" }))).toBe(true);
    expect(shouldShowTrackMedicCallout(eligible, round({ state: "results" }))).toBe(true);
  });

  it("keeps the callout visible while a session is in progress", () => {
    const inProgress: TrackMedicState = {
      eligible: true,
      stale: false,
      session: {
        id: 3,
        round_id: 9,
        completed: false,
        target: {
          race_entry_id: 1,
          racer_id: 2,
          racer_name: "Goblin",
          sprite_key: "goblin",
          portrait_url: "/static/assets/racers/portraits/goblin.png",
        },
        wounds: [
          { index: 0, x: 0.35, y: 0.42, patched: true },
          { index: 1, x: 0.55, y: 0.38, patched: false },
        ],
        patched_count: 1,
        wound_count: 2,
        reward_cents: 2_000,
      },
    };
    expect(
      shouldShowTrackMedicCallout(
        player({ track_medic: inProgress }),
        round(),
      ),
    ).toBe(true);
    expect(trackMedicCalloutCopy(player({ track_medic: inProgress }), round()).action).toBe(
      "Keep patching",
    );
  });

  it("treats sessions from another round as stale", () => {
    const stale = trackMedicForRound(
      player({
        track_medic: {
          eligible: false,
          stale: false,
          session: {
            id: 4,
            round_id: 8,
            completed: false,
            target: {
              race_entry_id: 1,
              racer_id: 2,
              racer_name: "Goblin",
              sprite_key: "goblin",
              portrait_url: "/static/assets/racers/portraits/goblin.png",
            },
            wounds: [],
            patched_count: 0,
            wound_count: 2,
            reward_cents: 2_000,
          },
        },
      }),
      round({ id: 9 }),
    );
    expect(stale.session).toBeNull();
    expect(stale.stale).toBe(true);
  });

  it("labels wound buttons accessibly", () => {
    expect(woundButtonLabel(0)).toBe("Patch wound 1");
    expect(woundButtonLabel(4)).toBe("Patch wound 5");
  });

  it("applies a patch receipt before the next state refresh", () => {
    const trackMedic: TrackMedicState = {
      eligible: true,
      stale: false,
      session: {
        id: 3,
        round_id: 9,
        completed: false,
        target: {
          race_entry_id: 1,
          racer_id: 2,
          racer_name: "Goblin",
          sprite_key: "goblin",
          portrait_url: "/static/assets/racers/portraits/goblin.png",
        },
        wounds: [
          { index: 0, x: 0.35, y: 0.42, patched: false },
          { index: 1, x: 0.55, y: 0.38, patched: false },
        ],
        patched_count: 0,
        wound_count: 2,
        reward_cents: 2_000,
      },
    };

    const updated = applyTrackMedicPatch(trackMedic, {
      session_id: 3,
      patched_indices: [0],
      completed: false,
    });

    expect(updated.session?.patched_count).toBe(1);
    expect(updated.session?.wounds[0]?.patched).toBe(true);
    expect(updated.session?.wounds[1]?.patched).toBe(false);
    expect(trackMedic.session?.wounds[0]?.patched).toBe(false);
  });
});
