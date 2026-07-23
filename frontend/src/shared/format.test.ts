import { afterEach, describe, expect, it, vi } from "vitest";

import {
  activeCountdownSeconds,
  dnfLabel,
  formatMoney,
  formatOdds,
  ordinal,
} from "./format";

describe("display formatting", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

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
    expect(dnfLabel("finish_countdown")).toBe("DNF · CLOCK");
    expect(dnfLabel("unknown")).toBe("DNF");
  });

  it("starts the finish countdown only after the first crossing", () => {
    vi.useFakeTimers();
    const start = new Date("2026-07-23T20:00:10Z");
    const end = new Date("2026-07-23T20:00:40Z");

    vi.setSystemTime(new Date("2026-07-23T20:00:09Z"));
    expect(activeCountdownSeconds(start.toISOString(), end.toISOString(), 0)).toBeNull();

    vi.setSystemTime(start);
    expect(activeCountdownSeconds(start.toISOString(), end.toISOString(), 0)).toBe(30);

    vi.setSystemTime(new Date("2026-07-23T20:00:25.100Z"));
    expect(activeCountdownSeconds(start.toISOString(), end.toISOString(), 0)).toBe(15);
  });
});
