import { describe, expect, it } from "vitest";

import { defaultReactionMessage } from "./reactions";

describe("defaultReactionMessage", () => {
  it("provides readable fallback copy for every reaction", () => {
    expect(defaultReactionMessage("cheer")).toBe("Cheer!");
    expect(defaultReactionMessage("boo")).toBe("Boo!");
    expect(defaultReactionMessage("cry")).toBe("Waaah!");
    expect(defaultReactionMessage("shout")).toBe("Shout!");
  });
});
