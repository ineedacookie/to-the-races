import { formatMoney } from "../shared/format";

export function roundStakeRemainingCents(
  roundStakedCents: number,
  maxRoundStakeCents: number,
): number {
  return Math.max(0, maxRoundStakeCents - roundStakedCents);
}

export function maxStakeCents(
  balanceCents: number,
  roundStakedCents: number,
  maxRoundStakeCents: number,
): number {
  return Math.min(
    Math.max(0, balanceCents),
    roundStakeRemainingCents(roundStakedCents, maxRoundStakeCents),
  );
}

export function stakeDraftMaxCents(
  bettingOpen: boolean,
  balanceCents: number,
  roundStakedCents: number,
  maxRoundStakeCents: number,
): number {
  return bettingOpen
    ? maxStakeCents(balanceCents, roundStakedCents, maxRoundStakeCents)
    : Math.max(0, maxRoundStakeCents);
}

export function parseStakeCents(value: string): number {
  const normalized = value.trim();
  if (
    normalized === "" ||
    normalized === "." ||
    !/^\d*(?:\.\d{0,2})?$/.test(normalized)
  ) {
    return 0;
  }
  const [dollars = "0", decimal = ""] = normalized.split(".");
  const cents = Number(dollars || "0") * 100 + Number(decimal.padEnd(2, "0"));
  return Number.isSafeInteger(cents) ? cents : 0;
}

export function stakeBlockReason(
  stakeCents: number,
  balanceCents: number,
  roundStakedCents: number,
  maxRoundStakeCents: number,
): string | null {
  if (!Number.isSafeInteger(stakeCents) || stakeCents < 1) {
    return "Minimum stake is $0.01.";
  }
  if (stakeCents > balanceCents) {
    return "That exceeds your available balance.";
  }
  const remaining = roundStakeRemainingCents(roundStakedCents, maxRoundStakeCents);
  if (stakeCents > remaining) {
    return (
      `That exceeds this round's ${formatMoney(maxRoundStakeCents)} stake cap. ` +
      `You may stake ${formatMoney(remaining)} more.`
    );
  }
  return null;
}

export function isValidStake(
  stakeCents: number,
  balanceCents: number,
  roundStakedCents: number,
  maxRoundStakeCents: number,
): boolean {
  return stakeBlockReason(stakeCents, balanceCents, roundStakedCents, maxRoundStakeCents) === null;
}
