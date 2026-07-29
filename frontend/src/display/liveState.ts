import type { LiveRound, LiveState } from "../shared/types";

function preservePresentationPayload(
  currentRound: LiveRound | null,
  incomingRound: LiveRound | null,
): LiveRound | null {
  if (
    currentRound === null ||
    incomingRound === null ||
    currentRound.id !== incomingRound.id
  ) {
    return incomingRound;
  }
  return {
    ...incomingRound,
    race: incomingRound.race ?? currentRound.race,
    display_replay:
      incomingRound.display_replay ?? currentRound.display_replay,
  };
}

/**
 * Market events intentionally omit large display-only playback payloads.
 * Preserve those payloads for matching rounds so a bet, purchase, or seat
 * update cannot interrupt an in-progress race or highlight broadcast.
 */
export function mergeDisplayState(
  currentState: LiveState | null,
  incomingState: LiveState,
): LiveState {
  if (currentState === null) {
    return incomingState;
  }
  return {
    ...incomingState,
    round: preservePresentationPayload(
      currentState.round,
      incomingState.round,
    ),
    show_round: preservePresentationPayload(
      currentState.show_round,
      incomingState.show_round,
    ),
  };
}
