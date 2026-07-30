import { describe, expect, it } from "vitest";

import type { LivePlayer, LiveState, SeatClaim } from "../shared/types";
import { updateSeatPresence } from "./liveState";

const ownedSeat: SeatClaim = {
  id: 1,
  player_id: 7,
  seat_slug: "finish-barrel",
  seat_name: "Finish Barrel",
  seat_description: "Trackside",
  sprite_key: "finish-barrel",
  seat_color: "#ffffff",
  payout_bonus_bps: 500,
  current_price_cents: 4_500,
  takeover_count: 1,
  nickname: "Seat Holder",
  is_online: true,
  acquired_at: "2026-07-27T20:00:00Z",
};

const player: LivePlayer = {
  id: 7,
  nickname: "Seat Holder",
  avatar_recipe: { skin: 0, eyes: 0, bottoms: 0, tops: 0, shoes: 0, hair: 0 },
  avatar_version: "avatar-v1",
  avatar_url: "/avatar.png",
  replay_preference: "ask",
  balance_cents: 10_000,
  round_staked_cents: 0,
  round_stake_remaining_cents: 50_000,
  round_item_spent_cents: 0,
  bets: [],
  inventory: [],
  item_uses: [],
  seat_claim: ownedSeat,
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
  track_medic: { eligible: false, session: null, stale: false },
};

function stateWith(seats: SeatClaim[], livePlayer: LivePlayer | null): LiveState {
  return {
    protocol_version: 18,
    server_time: "2026-07-27T20:00:00Z",
    room: {
      name: "Test room",
      is_paused: false,
      broadcast_enabled: true,
      betting_seconds: 30,
      max_round_stake_cents: 50_000,
      max_inventory_items: 4,
      max_round_item_spend_cents: 25_000,
      max_round_item_uses: 4,
      item_catalog: [],
      seat_catalog: [],
      upgrade_catalog: [],
    },
    round: {
      id: 1,
      number: 1,
      state: "open",
      opened_at: "2026-07-27T20:00:00Z",
      locks_at: "2026-07-27T20:01:00Z",
      race_starts_at: "2026-07-27T20:01:03Z",
      race_ends_at: "2026-07-27T20:03:03Z",
      results_end_at: "2026-07-27T20:03:11Z",
      finish_countdown_starts_at: null,
      finish_countdown_ends_at: null,
      entries: [],
      item_uses: [],
      seats,
      seat_markets: [],
      result: {},
    },
    show_round: null,
    player: livePlayer,
    leaderboard: [],
    debt_board: [],
  };
}

describe("updateSeatPresence", () => {
  it("updates seat-owner presence without waiting for a state refresh", () => {
    const current = stateWith([ownedSeat], player);

    const offline = updateSeatPresence(current, player.id, false);

    expect(offline.round?.seats[0]?.is_online).toBe(false);
    expect(offline.player?.seat_claim?.is_online).toBe(false);
    expect(current.round?.seats[0]?.is_online).toBe(true);
  });
});
