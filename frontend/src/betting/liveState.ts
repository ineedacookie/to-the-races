import type { LiveState } from "../shared/types";
import { TRACK_MEDIC_BALANCE_LIMIT_CENTS } from "./trackMedic";

export function updateSeatPresence(
  currentState: LiveState,
  playerId: number,
  isOnline: boolean,
): LiveState {
  const updateSeat = (seat: NonNullable<LiveState["player"]>["seat_claim"]) =>
    seat !== null && seat.player_id === playerId ? { ...seat, is_online: isOnline } : seat;
  return {
    ...currentState,
    round:
      currentState.round === null
        ? null
        : {
            ...currentState.round,
            seats: currentState.round.seats.map((seat) => updateSeat(seat) ?? seat),
          },
    player:
      currentState.player === null
        ? null
        : {
            ...currentState.player,
            seat_claim: updateSeat(currentState.player.seat_claim),
          },
  };
}

export function mergePlayerState(
  currentState: LiveState | null,
  incoming: LiveState,
): LiveState {
  const currentPlayer = currentState?.player ?? incoming.player;
  const roundChanged = currentState?.round?.id !== incoming.round?.id;
  if (currentPlayer === null) {
    return { ...incoming, player: null };
  }
  const syncedSeat =
    incoming.round?.seats.find((seat) => seat.player_id === currentPlayer.id) ??
    (incoming.round === null ? currentPlayer.seat_claim : null);
  const syncedPlayer = {
    ...currentPlayer,
    seat_claim: syncedSeat,
  };
  if (!roundChanged) {
    return { ...incoming, player: syncedPlayer };
  }
  return {
    ...incoming,
    player: {
      ...syncedPlayer,
      round_staked_cents: 0,
      round_stake_remaining_cents: incoming.room.max_round_stake_cents,
      round_item_spent_cents: 0,
      item_uses: [],
      bets: [],
      track_medic: incoming.player?.track_medic ?? {
        eligible:
          currentPlayer.balance_cents < TRACK_MEDIC_BALANCE_LIMIT_CENTS &&
          incoming.round !== null,
        session: null,
        stale: false,
      },
    },
  };
}
