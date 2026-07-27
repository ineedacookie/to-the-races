import { describe, expect, it } from "vitest";

import {
  EMPTY_POTION_ART_PATH,
  potionArtPath,
  potionLabel,
  WATER_POTION_ART_PATH,
} from "./itemArt";

describe("item art", () => {
  it("maps every tonic to a local pixel-art potion", () => {
    expect(potionArtPath("speed_tonic")).toMatch(/blue\.png$/);
    expect(potionArtPath("guard_tonic")).toMatch(/green\.png$/);
    expect(potionArtPath("trip_tonic")).toMatch(/red\.png$/);
    expect(potionArtPath("confusion_tonic")).toMatch(/purple\.png$/);
    expect(potionArtPath("growth_tonic")).toMatch(/growth\.png$/);
    expect(potionArtPath("shrink_tonic")).toMatch(/shrink\.png$/);
    expect(potionArtPath("transform_tonic")).toMatch(/transform\.png$/);
    expect(EMPTY_POTION_ART_PATH).toMatch(/empty\.png$/);
    expect(WATER_POTION_ART_PATH).toMatch(/water\.png$/);
  });

  it("keeps procedural track items out of the potion mapping", () => {
    expect(potionArtPath("banana")).toBeNull();
    expect(potionArtPath("pothole")).toBeNull();
    expect(potionArtPath("oil_slick")).toBeNull();
    expect(potionArtPath("boost_pad")).toBeNull();
    expect(potionArtPath("boxing_glove")).toBeNull();
    expect(potionLabel("confusion_tonic")).toBe("CONFUSION");
    expect(potionLabel("growth_tonic")).toBe("GROW");
    expect(potionLabel("shrink_tonic")).toBe("SHRINK");
    expect(potionLabel("transform_tonic")).toBe("MORPH");
  });
});
