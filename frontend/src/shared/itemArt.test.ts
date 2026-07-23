import { describe, expect, it } from "vitest";

import { EMPTY_POTION_ART_PATH, potionArtPath, potionLabel } from "./itemArt";

describe("item art", () => {
  it("maps every tonic to a local pixel-art potion", () => {
    expect(potionArtPath("speed_tonic")).toMatch(/blue\.png$/);
    expect(potionArtPath("guard_tonic")).toMatch(/green\.png$/);
    expect(potionArtPath("trip_tonic")).toMatch(/red\.png$/);
    expect(potionArtPath("confusion_tonic")).toMatch(/purple\.png$/);
    expect(EMPTY_POTION_ART_PATH).toMatch(/empty\.png$/);
  });

  it("keeps procedural track items out of the potion mapping", () => {
    expect(potionArtPath("banana")).toBeNull();
    expect(potionArtPath("pothole")).toBeNull();
    expect(potionLabel("confusion_tonic")).toBe("CONFUSION");
  });
});
