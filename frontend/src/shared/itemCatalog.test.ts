import { existsSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  ALL_ITEM_KINDS,
  isTonicKind,
  itemArtPath,
  shouldDespawnTrackItemOnHit,
  WATER_POTION_ART_PATH,
} from "./itemCatalog";

describe("item catalog", () => {
  it("maps every tonic to a local pixel-art potion", () => {
    expect(itemArtPath("speed_tonic")).toMatch(/blue\.png$/);
    expect(itemArtPath("guard_tonic")).toMatch(/green\.png$/);
    expect(itemArtPath("trip_tonic")).toMatch(/red\.png$/);
    expect(itemArtPath("confusion_tonic")).toMatch(/purple\.png$/);
    expect(itemArtPath("growth_tonic")).toMatch(/growth\.png$/);
    expect(itemArtPath("shrink_tonic")).toMatch(/shrink\.png$/);
    expect(itemArtPath("transform_tonic")).toMatch(/transform\.png$/);
    expect(itemArtPath("fireproof_tonic")).toMatch(/fireproof\.png$/);
    expect(itemArtPath("nitro_serum")).toMatch(/nitro\.png$/);
    expect(itemArtPath("recovery_brew")).toMatch(/recovery\.png$/);
    expect(itemArtPath("ghost_draught")).toMatch(/ghost\.png$/);
    expect(itemArtPath("second_wind")).toMatch(/second_wind\.png$/);
    expect(itemArtPath("phoenix_flask")).toMatch(/phoenix\.png$/);
    expect(WATER_POTION_ART_PATH).toMatch(/water\.png$/);
  });

  it("maps every track item to a local pixel-art sprite", () => {
    for (const kind of ALL_ITEM_KINDS.filter((itemKind) => !isTonicKind(itemKind))) {
      expect(itemArtPath(kind)).toMatch(new RegExp(`/track/${kind}\\.png$`));
    }
  });

  it("covers the full item catalog", () => {
    for (const kind of ALL_ITEM_KINDS) {
      const publicPath = itemArtPath(kind);
      expect(publicPath).toMatch(/\.png$/);
      expect(existsSync(resolve(process.cwd(), publicPath.replace(/^\/static\//, "static/")))).toBe(
        true,
      );
    }
  });

  it("despawns only single-use track items on impact", () => {
    expect(shouldDespawnTrackItemOnHit("boxing_glove")).toBe(true);
    expect(shouldDespawnTrackItemOnHit("portal_gate")).toBe(true);
    expect(shouldDespawnTrackItemOnHit("magnet_mine")).toBe(true);
    expect(shouldDespawnTrackItemOnHit("pothole")).toBe(false);
    expect(shouldDespawnTrackItemOnHit("roomba_vacuum")).toBe(false);
  });

  it("keeps tonic classification exhaustive", () => {
    expect(ALL_ITEM_KINDS.filter((kind) => isTonicKind(kind))).toHaveLength(15);
  });
});
