import { describe, expect, it } from "vitest";

import type { TonicKind } from "../shared/itemCatalog";
import type { ItemUse, RaceEffect, RaceEvent } from "../shared/types";
import {
  activeAuraColors,
  mixedDrinkColor,
  shouldAnnounceRaceEvent,
} from "./potionPresentation";

function itemUse(id: number, kind: TonicKind, racerId: number): ItemUse {
  return {
    id,
    buyer: "Tester",
    item_slug: kind,
    item_name: kind,
    item_icon: "",
    item_color: "#ffffff",
    kind,
    target_entry_id: racerId,
    target_racer_id: racerId,
    target_racer_name: `Racer ${racerId}`,
    track_lane: null,
    track_position: null,
    activation_tick: 0,
    price_paid_cents: 100,
    created_at: "2026-07-28T00:00:00Z",
  };
}

function effect(id: number, kind: TonicKind, racerId: number): RaceEffect {
  return {
    id,
    kind,
    item_name: kind,
    item_icon: "",
    item_color: "#ffffff",
    buyer: "Tester",
    target_racer_id: racerId,
    activation_tick: 0,
    strength: 1,
  };
}

const event: RaceEvent = {
  tick: 1,
  kind: "recover",
  racer_id: 1,
  message: "Recovered!",
};

describe("potion presentation", () => {
  it("blends every potion for a racer into one drink color", () => {
    expect(
      mixedDrinkColor(
        [
          itemUse(1, "speed_tonic", 1),
          itemUse(2, "guard_tonic", 1),
          itemUse(3, "trip_tonic", 2),
        ],
        1,
      ),
    ).toBe(0x7ee4cd);
    expect(mixedDrinkColor([], 1)).toBeNull();
  });

  it("blends successful persistent bonuses into one aura color", () => {
    const colors = activeAuraColors(
      [
        effect(1, "speed_tonic", 1),
        effect(2, "guard_tonic", 1),
        effect(3, "recovery_brew", 1),
        effect(4, "trip_tonic", 2),
      ],
      new Set([1, 2, 3, 4]),
    );

    expect(colors.get(1)).toBe(0x7ee4cd);
    expect(colors.has(2)).toBe(false);
  });

  it("keeps potion announcements private without hiding normal events", () => {
    const tonic = effect(9, "speed_tonic", 1);
    expect(
      shouldAnnounceRaceEvent(
        { ...event, kind: "potion_used", effect_id: tonic.id },
        [tonic],
      ),
    ).toBe(false);
    expect(shouldAnnounceRaceEvent({ ...event, effect_id: tonic.id }, [tonic])).toBe(false);
    expect(shouldAnnounceRaceEvent(event, [tonic])).toBe(true);
  });
});
