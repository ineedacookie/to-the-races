import type { LiveState } from "../shared/types";

export function updateSeatPresence(
  currentState: LiveState,
  playerId: number,
  isOnline: boolean,
): LiveState {
  const updateSeat = (seat: NonNullable<LiveState["player"]>["seat_claim"]) =>
    seat !== null && seat.player_id === playerId ? { ...seat, is_online: isOnline } : seat;
  const updateRoundSeats = (
    round: LiveState["round"],
  ): LiveState["round"] =>
    round === null
      ? null
      : {
          ...round,
          seats: round.seats.map((seat) => updateSeat(seat) ?? seat),
        };
  return {
    ...currentState,
    round: updateRoundSeats(currentState.round),
    show_round: updateRoundSeats(currentState.show_round),
    player:
      currentState.player === null
        ? null
        : {
            ...currentState.player,
            seat_claim: updateSeat(currentState.player.seat_claim),
          },
  };
}
