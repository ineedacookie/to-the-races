import { describe, expect, it } from "vitest";

import { dnfLabel, formatMoney, formatOdds, ordinal } from "./format";

describe("display formatting", () => {
  it("keeps negative play-money balances readable", () => {
    expect(formatMoney(-1250)).toBe("−$12.50");
  });

  it("normalizes decimal odds", () => {
    expect(formatOdds("4.5")).toBe("4.50×");
  });

  it("formats ordinal edge cases", () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21].map(ordinal)).toEqual([
      "1st",
      "2nd",
      "3rd",
      "4th",
      "11th",
      "12th",
      "13th",
      "21st",
    ]);
  });

  it("explains destructive non-finishes", () => {
    expect(dnfLabel("fire_pit")).toBe("DNF · FIRE PIT");
    expect(dnfLabel("stomped")).toBe("DNF · STOMPED");
    expect(dnfLabel("track_consumed")).toBe("DNF · FIRE");
    expect(dnfLabel("unknown")).toBe("DNF");
  });
});
