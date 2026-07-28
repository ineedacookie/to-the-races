import { describe, expect, it } from "vitest";

import {
  isValidStake,
  maxStakeCents,
  parseStakeCents,
  roundStakeRemainingCents,
  stakeBlockReason,
  stakeDraftMaxCents,
} from "./stakeLimits";

describe("stakeLimits", () => {
  const maxRoundStake = 15_000;

  it("computes remaining round stake from the cap", () => {
    expect(roundStakeRemainingCents(12_000, maxRoundStake)).toBe(3_000);
    expect(roundStakeRemainingCents(15_000, maxRoundStake)).toBe(0);
  });

  it("uses the minimum of balance and remaining cap", () => {
    expect(maxStakeCents(30_000, 0, maxRoundStake)).toBe(15_000);
    expect(maxStakeCents(10_000, 0, maxRoundStake)).toBe(10_000);
    expect(maxStakeCents(45, 0, maxRoundStake)).toBe(45);
    expect(maxStakeCents(60_000, 12_000, maxRoundStake)).toBe(3_000);
    expect(maxStakeCents(0, 0, maxRoundStake)).toBe(0);
  });

  it("allows preparing a next-round stake while betting is closed", () => {
    expect(stakeDraftMaxCents(false, 0, maxRoundStake, maxRoundStake)).toBe(
      maxRoundStake,
    );
    expect(stakeDraftMaxCents(true, 0, maxRoundStake, maxRoundStake)).toBe(0);
  });

  it("parses fractional dollar stakes as integer cents", () => {
    expect(parseStakeCents("0.45")).toBe(45);
    expect(parseStakeCents(".45")).toBe(45);
    expect(parseStakeCents("5")).toBe(500);
    expect(parseStakeCents("1.2")).toBe(120);
    expect(parseStakeCents("0.001")).toBe(0);
  });

  it("allows any positive whole-cent stake", () => {
    expect(stakeBlockReason(45, 10_000, 0, maxRoundStake)).toBeNull();
    expect(isValidStake(45, 10_000, 0, maxRoundStake)).toBe(true);
    expect(stakeBlockReason(0, 10_000, 0, maxRoundStake)).toBe(
      "Minimum stake is $0.01.",
    );
  });

  it("blocks stakes above available balance", () => {
    expect(stakeBlockReason(5_000, 4_000, 0, maxRoundStake)).toBe(
      "That exceeds your available balance.",
    );
  });

  it("blocks aggregate stakes above the round cap", () => {
    expect(stakeBlockReason(6_000, 20_000, 12_000, maxRoundStake)).toBe(
      "That exceeds this round's $150 stake cap. You may stake $30 more.",
    );
    expect(stakeBlockReason(100, 20_000, 14_955, maxRoundStake)).toBe(
      "That exceeds this round's $150 stake cap. You may stake $0.45 more.",
    );
    expect(isValidStake(3_000, 20_000, 12_000, maxRoundStake)).toBe(true);
  });
});
