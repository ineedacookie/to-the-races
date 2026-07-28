import type { LivePlayer, LiveRound, TrackMedicState } from "../shared/types";

export const TRACK_MEDIC_BALANCE_LIMIT_CENTS = 1_000;

interface TrackMedicPatch {
  session_id: number;
  patched_indices: number[];
  completed: boolean;
}

export function applyTrackMedicPatch(
  trackMedic: TrackMedicState,
  patch: TrackMedicPatch,
): TrackMedicState {
  const session = trackMedic.session;
  if (session === null || session.id !== patch.session_id) {
    return trackMedic;
  }
  const patchedIndices = new Set(patch.patched_indices);
  return {
    ...trackMedic,
    eligible: patch.completed ? false : trackMedic.eligible,
    session: {
      ...session,
      completed: patch.completed,
      patched_count: patchedIndices.size,
      wounds: session.wounds.map((wound) => ({
        ...wound,
        patched: patchedIndices.has(wound.index),
      })),
    },
  };
}

export function trackMedicForRound(
  player: LivePlayer,
  round: LiveRound | null,
): TrackMedicState {
  const trackMedic = player.track_medic;
  if (round === null) {
    return { eligible: false, session: null, stale: trackMedic.stale };
  }
  if (trackMedic.session !== null && trackMedic.session.round_id !== round.id) {
    return { eligible: false, session: null, stale: true };
  }
  return trackMedic;
}

export function shouldShowTrackMedicCallout(
  player: LivePlayer,
  round: LiveRound | null,
): boolean {
  if (round === null) {
    return false;
  }
  const trackMedic = trackMedicForRound(player, round);
  if (trackMedic.session !== null) {
    return !trackMedic.session.completed;
  }
  return trackMedic.eligible;
}

export function trackMedicCalloutCopy(
  player: LivePlayer,
  round: LiveRound | null,
): { title: string; copy: string; action: string } {
  const trackMedic = trackMedicForRound(player, round);
  if (trackMedic.session !== null && !trackMedic.session.completed) {
    const remaining =
      trackMedic.session.wound_count - trackMedic.session.patched_count;
    return {
      title: "Track medic on duty",
      copy: `Patch ${trackMedic.session.target.racer_name}'s wounds to earn $20.`,
      action: remaining === trackMedic.session.wound_count ? "Open medic kit" : "Keep patching",
    };
  }
  return {
    title: "Running low? Patch wounds for cash",
    copy: "Below $10? Take one job this round and earn $20 by bandaging a random racer's 2–5 wounds.",
    action: "Start track medic",
  };
}

export function woundButtonLabel(index: number): string {
  return `Patch wound ${index + 1}`;
}
