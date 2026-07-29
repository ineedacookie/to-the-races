import { secondsRemaining } from "../shared/format";
import type { LivePlayer, LiveState } from "../shared/types";
import { stakeBlockReason } from "./stakeLimits";

export interface BettingOptions {
  roundId: number | null;
  entryIds: ReadonlySet<number>;
  marketOpen: boolean;
  stakeCents: number;
  stakeError: string | null;
  submissionPending: boolean;
}

export function deriveBettingOptions(
  currentState: LiveState,
  player: LivePlayer,
  stakeCents: number,
  pendingEntryCount: number,
  serverOffsetMs: number,
): BettingOptions {
  const bettingRound = currentState.round;
  return {
    roundId: bettingRound?.id ?? null,
    entryIds: new Set(bettingRound?.entries.map((entry) => entry.id) ?? []),
    marketOpen:
      bettingRound?.state === "open" &&
      !currentState.room.is_paused &&
      secondsRemaining(bettingRound.locks_at, serverOffsetMs) > 0,
    stakeCents,
    stakeError: stakeBlockReason(
      stakeCents,
      player.balance_cents,
      player.round_staked_cents,
      currentState.room.max_round_stake_cents,
    ),
    submissionPending: pendingEntryCount > 0,
  };
}

export function bettingOptionCanSubmit(
  options: BettingOptions,
  entryId: number,
): boolean {
  return (
    options.marketOpen &&
    options.entryIds.has(entryId) &&
    options.stakeError === null &&
    !options.submissionPending
  );
}
