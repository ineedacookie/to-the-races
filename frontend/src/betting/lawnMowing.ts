import type { LawnMowingState, LivePlayer, LiveRound } from "../shared/types";

export function lawnMowingForRound(
  player: LivePlayer,
  round: LiveRound | null,
): LawnMowingState {
  const lawn = player.lawn_mowing;
  if (round === null) {
    return { eligible: false, session: null, stale: lawn.stale };
  }
  if (lawn.session !== null && lawn.session.round_id !== round.id) {
    return { eligible: false, session: null, stale: true };
  }
  return lawn;
}

export function shouldShowLawnMowingCallout(
  player: LivePlayer,
  round: LiveRound | null,
): boolean {
  const lawn = lawnMowingForRound(player, round);
  return lawn.session === null ? lawn.eligible : !lawn.session.completed;
}

export function applyLawnMowingReceipt(
  lawn: LawnMowingState,
  receipt: {
    session_id: number;
    mowed_cells: number[];
    completed: boolean;
  },
): LawnMowingState {
  if (lawn.session === null || lawn.session.id !== receipt.session_id) {
    return lawn;
  }
  return {
    ...lawn,
    eligible: !receipt.completed,
    session: {
      ...lawn.session,
      completed: receipt.completed,
      mowed_cells: receipt.mowed_cells,
    },
  };
}
