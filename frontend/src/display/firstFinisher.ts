import type { RaceEvent, RacePlayback } from "../shared/types";

export const FIRST_FINISHER_EVENT = "first-finisher";

export function racePlaybackKey(roundId: number, race: RacePlayback): string {
  const fallbackVersion = [
    race.duration_ticks,
    race.events.length,
    race.events.at(-1)?.tick ?? -1,
    race.effects?.length ?? 0,
  ].join(":");
  return `${roundId}:${race.seed}:${race.generated_at ?? fallbackVersion}`;
}

export function isOfficialFirstFinish(event: RaceEvent): boolean {
  return event.kind === "finish" && event.finish_place === 1;
}

export function isPriorityRaceEvent(event: RaceEvent): boolean {
  return (
    isOfficialFirstFinish(event) ||
    event.kind === "knockout" ||
    event.kind === "destroyed" ||
    event.kind === "timeout"
  );
}

export function shouldCelebrateFirstFinisher(
  event: RaceEvent,
  alreadyCelebrated: boolean,
): boolean {
  return !alreadyCelebrated && isOfficialFirstFinish(event);
}

export function firstFinisherAlreadyPassed(events: RaceEvent[], fromIndex: number): boolean {
  return events
    .slice(0, fromIndex)
    .some((event) => isOfficialFirstFinish(event));
}
