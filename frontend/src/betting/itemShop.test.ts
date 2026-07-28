import { describe, expect, it } from "vitest";

import { ALL_ITEM_KINDS, itemShopSection } from "../shared/itemCatalog";
import type { ItemDefinition } from "../shared/types";
import { itemUseWindowOpen, sortItemsByPrice } from "./itemShop";

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
});
