import { describe, expect, it } from "vitest";

import type {
  ConnectedSpectator,
  SeatClaim,
  SeatDefinition,
} from "../shared/types";
import {
  buildGrandstandModel,
  crowdRowLabel,
  spectatorArtPath,
} from "./grandstand";

const seats: SeatDefinition[] = [
  {
    slug: "rail",
    name: "Rail",
    description: "Small bonus",
    sprite_key: "rat",
    color: "#ff0000",
    price_cents: 4_000,
    payout_bonus_bps: 500,
  },
  {
    slug: "throne",
    name: "Throne",
    description: "Large bonus",
    sprite_key: "mimic",
    color: "#ffff00",
    price_cents: 15_000,
    payout_bonus_bps: 2_500,
  },
];

function spectator(playerId: number): ConnectedSpectator {
  return {
    player_id: playerId,
    nickname: `Viewer ${playerId}`,
    avatar_version: `look-${playerId}`,
  };
}

function claim(playerId: number, seat: SeatDefinition): SeatClaim {
  return {
    id: playerId,
    player_id: playerId,
    seat_slug: seat.slug,
    seat_name: seat.name,
    seat_description: seat.description,
    sprite_key: seat.sprite_key,
    seat_color: seat.color,
    payout_bonus_bps: seat.payout_bonus_bps,
    current_price_cents: seat.price_cents,
    takeover_count: 0,
    nickname: `Viewer ${playerId}`,
    is_online: false,
    acquired_at: "2026-07-27T12:00:00Z",
  };
}

describe("buildGrandstandModel", () => {
  it("keeps connected prestige holders out of the general rows", () => {
    const spectators = [spectator(1), spectator(2), spectator(3)];
    const model = buildGrandstandModel(
      seats,
      [claim(2, seats[1] as SeatDefinition)],
      spectators,
    );

    expect(model.prestige.map((position) => position.rank)).toEqual([2, 1]);
    expect(model.prestige[1]?.spectator?.player_id).toBe(2);
    expect(
      model.crowdRows.flatMap((row) => row.slots).map((slot) => slot.spectator?.player_id),
    ).toContain(1);
    expect(
      model.crowdRows.flatMap((row) => row.slots).map((slot) => slot.spectator?.player_id),
    ).not.toContain(2);
  });

  it("scatters general spectators across stable pseudo-random seats", () => {
    const spectators = Array.from({ length: 8 }, (_, index) => spectator(index + 1));
    const model = buildGrandstandModel([], [], spectators);
    const reversedModel = buildGrandstandModel([], [], [...spectators].reverse());
    const placements = (candidate: ReturnType<typeof buildGrandstandModel>) =>
      candidate.crowdRows
        .flatMap((row) => row.slots)
        .filter((slot) => slot.spectator !== undefined)
        .map((slot) => [slot.spectator?.player_id, slot.rowIndex, slot.slotIndex])
        .sort((first, second) => (first[0] ?? 0) - (second[0] ?? 0));

    expect(model.crowdRows).toHaveLength(3);
    expect(new Set(placements(model).map((placement) => placement[1])).size).toBeGreaterThan(1);
    expect(placements(model)).toEqual(placements(reversedModel));
    expect(crowdRowLabel(2, 3)).toBe("Trackside row");
  });
});

describe("spectatorArtPath", () => {
  it("uses a versioned personalized avatar endpoint", () => {
    expect(spectatorArtPath(spectator(3))).toBe(
      "/api/players/3/avatar/?v=look-3",
    );
  });
});
