import { ApiError } from "./api";
import {
  activeCountdownSeconds,
  dnfLabel,
  formatMoney,
  ordinal,
  secondsRemaining,
} from "./format";
import type { ConnectionStatus } from "./socket";
import {
  assertNever,
  type LeaderboardRow,
  type LiveRound,
  type LiveState,
  type PlayerBettingRecord,
  type RacerEntry,
  type SeatDefinition,
  type SeatMarket,
} from "./types";

const CONNECTION_LABELS: Record<ConnectionStatus, string> = {
  connecting: "Connecting…",
  connected: "Live",
  disconnected: "Reconnecting…",
};

export function seatMarketPrice(
  seatSlug: string,
  catalog: SeatDefinition[],
  markets: SeatMarket[] | undefined,
): number {
  const market = markets?.find((entry) => entry.seat_slug === seatSlug);
  const catalogSeat = catalog.find((entry) => entry.slug === seatSlug);
  return market?.current_price_cents ?? catalogSeat?.price_cents ?? 0;
}

export function connectionStatusLabel(status: ConnectionStatus): string {
  return CONNECTION_LABELS[status];
}

export function presentationRound(state: LiveState): LiveRound | null {
  return state.show_round ?? state.round;
}

export function applyConnectionStatus(element: HTMLElement, status: ConnectionStatus): void {
  element.dataset.status = status;
  element.textContent = connectionStatusLabel(status);
}

export function bettingPhaseLabel(round: LiveRound | null, isPaused = false): string {
  if (isPaused) {
    return "Race night paused";
  }
  if (round === null) {
    return "Warming up";
  }
  switch (round.state) {
    case "open":
      return "Betting open";
    case "locked":
      return "Bets locked";
    case "racing":
      return "They're off!";
    case "results":
      return "Official result";
    default:
      return assertNever(round.state);
  }
}

export function displayPhaseLabel(round: LiveRound | null, isPaused = false): string {
  if (isPaused) {
    return "Race night paused";
  }
  if (round === null) {
    return "Preparing the track";
  }
  switch (round.state) {
    case "open":
      return "Place your bets";
    case "locked":
      return "Final lineup";
    case "racing":
      return "They're off!";
    case "results":
      return "Official result";
    default:
      return assertNever(round.state);
  }
}

interface LiveClockView {
  clockLabel: string;
  countdownText: string;
  isFinishClock: boolean;
}

export function formatLiveClock(
  round: LiveRound | null | undefined,
  serverOffsetMs: number,
): LiveClockView {
  if (round === null || round === undefined) {
    return { clockLabel: "Clock", countdownText: "—", isFinishClock: false };
  }

  switch (round.state) {
    case "open":
      return {
        clockLabel: "Clock",
        countdownText: `${secondsRemaining(round.locks_at, serverOffsetMs)}s`,
        isFinishClock: false,
      };
    case "locked":
      return {
        clockLabel: "Clock",
        countdownText: `${secondsRemaining(round.race_starts_at, serverOffsetMs)}s`,
        isFinishClock: false,
      };
    case "racing": {
      const finishClock = activeCountdownSeconds(
        round.finish_countdown_starts_at,
        round.finish_countdown_ends_at,
        serverOffsetMs,
      );
      if (finishClock === null) {
        return { clockLabel: "Clock", countdownText: "LIVE", isFinishClock: false };
      }
      return {
        clockLabel: "Finish clock",
        countdownText: `${finishClock}s`,
        isFinishClock: true,
      };
    }
    case "results":
      return {
        clockLabel: "Clock",
        countdownText: `${secondsRemaining(round.results_end_at, serverOffsetMs)}s`,
        isFinishClock: false,
      };
    default:
      return assertNever(round.state);
  }
}

function applyLiveClock(
  clockLabel: HTMLElement,
  countdown: HTMLElement,
  round: LiveRound | null | undefined,
  serverOffsetMs: number,
): void {
  const view = formatLiveClock(round, serverOffsetMs);
  clockLabel.textContent = view.clockLabel;
  countdown.textContent = view.countdownText;
  countdown.classList.toggle("is-finish-clock", view.isFinishClock);
}

interface LiveClockControllerOptions {
  clockLabel: HTMLElement;
  countdown: HTMLElement;
  getRound: () => LiveRound | null | undefined;
  intervalMs?: number;
}

export function createLiveClockController(options: LiveClockControllerOptions): {
  sync: (serverTime: string) => void;
  start: () => void;
  offsetMs: () => number;
} {
  let serverOffsetMs = 0;
  const update = (): void => {
    applyLiveClock(
      options.clockLabel,
      options.countdown,
      options.getRound(),
      serverOffsetMs,
    );
  };
  return {
    sync(serverTime): void {
      serverOffsetMs = Date.parse(serverTime) - Date.now();
      update();
    },
    start: () => {
      window.setInterval(update, options.intervalMs ?? 250);
    },
    offsetMs: () => serverOffsetMs,
  };
}

interface OrderedRaceResults<T extends { finish_place: number | null }> {
  finishers: T[];
  nonFinishers: T[];
}

export function orderRaceResults<T extends { finish_place: number | null }>(
  entries: T[],
): OrderedRaceResults<T> {
  const finishers = [...entries]
    .filter((entry) => entry.finish_place !== null)
    .sort((first, second) => (first.finish_place ?? 99) - (second.finish_place ?? 99));
  const nonFinishers = entries.filter((entry) => entry.finish_place === null);
  return { finishers, nonFinishers };
}

export function finishPlaceLabel(entry: RacerEntry): string {
  return entry.finish_place === null
    ? dnfLabel(entry.dnf_reason)
    : ordinal(entry.finish_place).toUpperCase();
}

export function raceResultView(entries: RacerEntry[]): {
  winner: RacerEntry | null;
  rows: Array<{ entry: RacerEntry; placeLabel: string }>;
} {
  const { finishers, nonFinishers } = orderRaceResults(entries);
  return {
    winner: finishers[0] ?? null,
    rows: [...finishers, ...nonFinishers].map((entry) => ({
      entry,
      placeLabel: finishPlaceLabel(entry),
    })),
  };
}

export function formatPlayerBettingRecordSummary(record: PlayerBettingRecord): string {
  if (record.total_bets === 0) {
    return "No settled bets yet.";
  }
  return `${record.winning_bets} wins · ${record.losing_bets} losses · ${formatMoney(record.total_staked_cents)} staked · ${formatMoney(record.total_returned_cents)} returned · net ${formatMoney(record.net_cents)}`;
}

export function formatBoardStats(row: LeaderboardRow, showNet = false): string {
  if (showNet) {
    return `${formatMoney(row.betting_record.net_cents)} · ${row.betting_record.losing_bets} losses · ${row.betting_record.total_bets} bets`;
  }
  return `${formatMoney(row.balance_cents)} · ${row.wins} wins · ${row.total_bets} bets · net ${formatMoney(row.betting_record.net_cents)}`;
}

export function formatBoardSnippetRow(row: LeaderboardRow, useNet = false): string {
  return useNet
    ? `#${row.rank} ${row.nickname} · ${formatMoney(row.betting_record.net_cents)} net`
    : `#${row.rank} ${row.nickname} · ${formatMoney(row.balance_cents)}`;
}

export function formatRacerRecordSummary(record: RacerEntry["record"]): string {
  if (record.starts === 0) {
    return "No settled starts yet";
  }
  const winPct = Math.round(record.win_rate * 100);
  const dnfSuffix = record.dnfs > 0 ? ` · ${record.dnfs} DNFs` : "";
  return `${record.wins}-${record.losses} (${winPct}% wins${dnfSuffix})`;
}

export function loadingActionLabel(action: string): string {
  return `${action}…`;
}

interface PurchaseActionLabelOptions {
  pending: boolean;
  pendingAction: string;
  blockedLabel?: string;
  requiredCents?: number;
  actionLabel: string;
}

export function purchaseActionLabel({
  pending,
  pendingAction,
  blockedLabel,
  requiredCents,
  actionLabel,
}: PurchaseActionLabelOptions): string {
  if (pending) {
    return loadingActionLabel(pendingAction);
  }
  if (blockedLabel !== undefined) {
    return blockedLabel;
  }
  if (requiredCents !== undefined) {
    return `Need ${formatMoney(requiredCents)}`;
  }
  return actionLabel;
}

export function userFacingApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return fallback;
}
