import { describe, expect, it } from "vitest";

import type { ItemUse, RaceEffect, RaceEvent } from "../shared/types";
import { activeTrackItemEffects, consumedTrackEffectId } from "./trackItemPlayback";

const effect: RaceEffect = {
  id: 7,
  kind: "boxing_glove",
  item_name: "Boxing Glove",
  item_icon: "🥊",
  item_color: "#ffff00",
  buyer: "Tester",
  lane: 2,
  position: 0.5,
  activation_tick: 100,
  strength: 1,
};

const itemUse: ItemUse = {
  id: effect.id,
  buyer: effect.buyer,
  item_slug: "boxing-glove",
  item_name: effect.item_name,
  item_icon: effect.item_icon,
  item_color: effect.item_color,
  kind: effect.kind,
  target_entry_id: 4,
  target_racer_id: 8,
  target_racer_name: "Runner",
  track_lane: effect.lane ?? null,
  track_position: effect.position ?? null,
  activation_tick: effect.activation_tick,
  price_paid_cents: 500,
  created_at: "2026-07-28T12:00:00Z",
};

describe("track item playback", () => {
  it("keeps a live item hidden until its activation tick", () => {
    expect(activeTrackItemEffects([effect], [itemUse], 99, new Set())).toEqual([]);
    expect(activeTrackItemEffects([effect], [itemUse], 100, new Set())).toEqual([effect]);
  });

  it("does not respawn a consumed item", () => {
    expect(activeTrackItemEffects([effect], [itemUse], 100, new Set([effect.id]))).toEqual([]);
  });

  it("marks single-use obstacle hits as consumed", () => {
    const event: RaceEvent = {
      tick: 110,
      kind: "obstacle_hit",
      racer_id: 8,
      effect_id: effect.id,
      message: "Hit a boxing glove",
    };

    expect(consumedTrackEffectId(event, [effect])).toBe(effect.id);
  });
});
