import { describe, expect, it } from "vitest";

import { ALL_ITEM_KINDS, itemShopSection } from "../shared/itemCatalog";
import type { ItemDefinition, LiveRound } from "../shared/types";
import {
  itemPromotion,
  itemTargetRound,
  itemUseWindowOpen,
  promotionalItems,
  sortItemsByPrice,
} from "./itemShop";

describe("item shop sections", () => {
  it("assigns every catalog kind to a shop section", () => {
    for (const kind of ALL_ITEM_KINDS) {
      expect(["positive", "negative", "neutral", "live"]).toContain(itemShopSection(kind));
    }
  });

  it("sorts every subsection by ascending price with stable name ties", () => {
    const item = (name: string, priceCents: number): ItemDefinition => ({
      slug: name.toLowerCase(),
      name,
      description: "",
      icon: "",
      color: "#ffffff",
      price_cents: priceCents,
      discount_pct: 0,
      effective_price_cents: priceCents,
      effect_strength: 1,
      kind: "speed_tonic",
      target: "racer",
    });
    const unsorted = [item("C", 3_000), item("B", 1_000), item("A", 1_000)];

    expect(sortItemsByPrice(unsorted).map(({ name }) => name)).toEqual(["A", "B", "C"]);
    expect(unsorted.map(({ name }) => name)).toEqual(["C", "B", "A"]);
  });

  it("closes live-item use while a race is paused", () => {
    const racing = { state: "racing" } as const;

    expect(itemUseWindowOpen("banana", false, racing, false)).toBe(true);
    expect(itemUseWindowOpen("banana", false, racing, true)).toBe(false);
    expect(itemUseWindowOpen("speed_tonic", true, racing, true)).toBe(true);
  });

  it("opens tonics only when potion window is open", () => {
    const open = { state: "open" } as const;
    const racing = { state: "racing" } as const;

    expect(itemUseWindowOpen("speed_tonic", true, open, false)).toBe(true);
    expect(itemUseWindowOpen("speed_tonic", false, open, false)).toBe(false);
    expect(itemUseWindowOpen("speed_tonic", true, racing, false)).toBe(true);
  });

  it("opens live track items only during racing", () => {
    const open = { state: "open" } as const;
    const locked = { state: "locked" } as const;
    const racing = { state: "racing" } as const;
    const results = { state: "results" } as const;

    expect(itemUseWindowOpen("banana", false, open, false)).toBe(false);
    expect(itemUseWindowOpen("banana", false, locked, false)).toBe(false);
    expect(itemUseWindowOpen("banana", false, racing, false)).toBe(true);
    expect(itemUseWindowOpen("banana", false, results, false)).toBe(false);
  });

  it("targets tonics at the betting lineup and track items at the live lineup", () => {
    const bettingRound = { id: 2, state: "open" } as LiveRound;
    const showRound = { id: 1, state: "racing" } as LiveRound;

    expect(itemTargetRound("speed_tonic", bettingRound, showRound)).toBe(bettingRound);
    expect(itemTargetRound("banana", bettingRound, showRound)).toBe(showRound);
  });

  it("puts 40% markdowns in clearance above ordinary sales", () => {
    const item = (name: string, discountPct: number): ItemDefinition => ({
      slug: name.toLowerCase(),
      name,
      description: "",
      icon: "",
      color: "#ffffff",
      price_cents: 1_000,
      discount_pct: discountPct,
      effective_price_cents: 1_000 - discountPct * 10,
      effect_strength: 1,
      kind: "speed_tonic",
      target: "racer",
    });
    const grouped = promotionalItems([
      item("Regular", 0),
      item("Sale", 25),
      item("Clearance", 40),
      item("Deep Clearance", 50),
    ]);

    expect(itemPromotion(0)).toBeNull();
    expect(itemPromotion(39)).toBe("sale");
    expect(itemPromotion(40)).toBe("clearance");
    expect(grouped.clearance.map(({ name }) => name)).toEqual([
      "Deep Clearance",
      "Clearance",
    ]);
    expect(grouped.sale.map(({ name }) => name)).toEqual(["Sale"]);
    expect(grouped.regular.map(({ name }) => name)).toEqual(["Regular"]);
  });
});
