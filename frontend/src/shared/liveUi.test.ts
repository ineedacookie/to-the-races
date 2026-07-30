import { afterEach, describe, expect, it, vi } from "vitest";

import {
  bettingPhaseLabel,
  connectionStatusLabel,
  createLiveClockController,
  displayPhaseLabel,
  finishPlaceLabel,
  formatBoardSnippetRow,
  formatBoardStats,
  formatLiveClock,
  formatPlayerBettingRecordSummary,
  formatRacerRecordSummary,
  loadingActionLabel,
  orderRaceResults,
  presentationRound,
  purchaseActionLabel,
  raceResultView,
  roundTransitionDeadlineMs,
  seatMarketPrice,
  userFacingApiError,
} from "./liveUi";
import { ApiError } from "./api";
import type {
  LeaderboardRow,
  LiveRound,
  LiveState,
  RacerEntry,
} from "./types";

const sampleRound = (state: LiveRound["state"]): LiveRound =>
  ({
    id: 1,
    number: 3,
    state,
    opened_at: "2026-07-23T20:00:00Z",
    locks_at: "2026-07-23T20:01:00Z",
    race_starts_at: "2026-07-23T20:01:30Z",
    race_ends_at: "2026-07-23T20:02:30Z",
    finish_countdown_starts_at: "2026-07-23T20:02:00Z",
    finish_countdown_ends_at: "2026-07-23T20:02:30Z",
    results_end_at: "2026-07-23T20:03:00Z",
    result: null,
    entries: [],
    item_uses: [],
    seats: [],
    seat_markets: [],
  }) as unknown as LiveRound;

describe("liveUi helpers", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("uses consistent connection copy", () => {
    expect(connectionStatusLabel("connecting")).toBe("Connecting…");
    expect(connectionStatusLabel("connected")).toBe("Live");
    expect(connectionStatusLabel("disconnected")).toBe("Reconnecting…");
  });

  it("labels phases per surface", () => {
    expect(bettingPhaseLabel(sampleRound("open"))).toBe("Betting open");
    expect(displayPhaseLabel(sampleRound("open"))).toBe("Place your bets");
    expect(bettingPhaseLabel(null)).toBe("Warming up");
    expect(displayPhaseLabel(null)).toBe("Preparing the track");
    expect(bettingPhaseLabel(sampleRound("locked"), true)).toBe("Race night paused");
  });

  it("prefers show_round state for betting phase label", () => {
    const bettingRound = sampleRound("open");
    const racingShowRound = { ...sampleRound("racing"), id: 2 };
    expect(bettingPhaseLabel(bettingRound, false, racingShowRound)).toBe("They're off!");

    const resultsShowRound = { ...sampleRound("results"), id: 3 };
    expect(bettingPhaseLabel(bettingRound, false, resultsShowRound)).toBe("Official result");
  });

  it("falls back to round state when show_round is null", () => {
    const bettingRound = sampleRound("open");
    expect(bettingPhaseLabel(bettingRound, false, null)).toBe("Betting open");
  });

  it("keeps an active race or results show separate from the betting round", () => {
    const bettingRound = sampleRound("open");
    const racingShowRound = {
      ...sampleRound("racing"),
      id: 2,
    };
    const resultsShowRound = {
      ...sampleRound("results"),
      id: 3,
    };
    const state = {
      round: bettingRound,
      show_round: racingShowRound,
    } as LiveState;

    expect(presentationRound(state)).toBe(racingShowRound);
    expect(
      presentationRound({ ...state, show_round: resultsShowRound }),
    ).toBe(resultsShowRound);
    expect(
      presentationRound({ ...state, show_round: null }),
    ).toBe(bettingRound);
  });

  it("formats countdowns with second suffixes", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-23T20:00:50Z"));
    const openClock = formatLiveClock(sampleRound("open"), 0);
    expect(openClock.countdownText).toBe("10s");

    vi.setSystemTime(new Date("2026-07-23T20:02:10Z"));
    const finishClock = formatLiveClock(sampleRound("racing"), 0);
    expect(finishClock.isFinishClock).toBe(true);
    expect(finishClock.countdownText).toBe("20s");

    vi.setSystemTime(new Date("2026-07-23T20:01:50Z"));
    const liveClock = formatLiveClock(sampleRound("racing"), 0);
    expect(liveClock.countdownText).toBe("LIVE");
  });

  it("requests a fresh state when a transition event is overdue", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-23T20:00:59Z"));
    const onTransitionOverdue = vi.fn();
    const clockLabel = { textContent: "" } as HTMLElement;
    const countdown = {
      textContent: "",
      classList: { toggle: vi.fn() },
    } as unknown as HTMLElement;
    const round = sampleRound("open");
    const controller = createLiveClockController({
      clockLabel,
      countdown,
      getRound: () => round,
      onTransitionOverdue,
    });
    vi.stubGlobal("window", {
      setInterval: globalThis.setInterval,
    });

    expect(roundTransitionDeadlineMs(round)).toBe(
      Date.parse("2026-07-23T20:01:00Z"),
    );
    controller.start();
    vi.advanceTimersByTime(2_499);
    expect(onTransitionOverdue).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onTransitionOverdue).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(5_000);
    expect(onTransitionOverdue).toHaveBeenCalledTimes(2);
  });

  it("orders finishers before non-finishers", () => {
    const ordered = orderRaceResults([
      { finish_place: null, name: "D" },
      { finish_place: 2, name: "B" },
      { finish_place: 1, name: "A" },
    ]);
    expect(ordered.finishers.map((entry) => entry.name)).toEqual(["A", "B"]);
    expect(ordered.nonFinishers.map((entry) => entry.name)).toEqual(["D"]);
  });

  it("builds shared result rows and purchase labels", () => {
    const winner = { finish_place: 1, dnf_reason: "", name: "A" } as RacerEntry;
    const dnf = { finish_place: null, dnf_reason: "timeout", name: "D" } as RacerEntry;
    const result = raceResultView([dnf, winner]);

    expect(result.winner).toBe(winner);
    expect(result.rows.map((row) => row.placeLabel)).toEqual(["1ST", "DNF · TIME"]);
    expect(
      purchaseActionLabel({
        pending: true,
        pendingAction: "Buying",
        actionLabel: "Buy",
      }),
    ).toBe("Buying…");
    expect(
      purchaseActionLabel({
        pending: false,
        pendingAction: "Buying",
        requiredCents: 1_500,
        actionLabel: "Buy",
      }),
    ).toBe("Need $15");
  });

  it("uses live seat prices before catalog fallbacks", () => {
    const catalog = [
      {
        slug: "throne",
        name: "The Throne",
        description: "Best seat",
        sprite_key: "king",
        color: "#f6c453",
        price_cents: 15_000,
        payout_bonus_bps: 2_500,
      },
    ];
    const markets = [{ seat_slug: "throne", current_price_cents: 17_500, takeover_count: 1 }];

    expect(seatMarketPrice("throne", catalog, markets)).toBe(17_500);
    expect(seatMarketPrice("throne", catalog, undefined)).toBe(15_000);
    expect(seatMarketPrice("missing", catalog, markets)).toBe(0);
  });

  it("formats board and betting record copy", () => {
    const row: LeaderboardRow = {
      rank: 1,
      nickname: "Unlucky",
      balance_cents: 250,
      wins: 3,
      total_bets: 10,
      betting_record: {
        winning_bets: 3,
        losing_bets: 7,
        total_bets: 10,
        total_staked_cents: 5_000,
        total_returned_cents: 3_200,
        net_cents: -1_800,
      },
    };
    expect(formatBoardStats(row, true)).toContain("−$18");
    expect(formatBoardSnippetRow(row, true)).toBe("#1 Unlucky · −$18 net");
    expect(
      formatPlayerBettingRecordSummary({
        winning_bets: 0,
        losing_bets: 0,
        total_bets: 0,
        total_staked_cents: 0,
        total_returned_cents: 0,
        net_cents: 0,
      }),
    ).toBe("No settled bets yet.");
  });

  it("formats racer records and finish labels", () => {
    const entry = {
      finish_place: 1,
      dnf_reason: "",
    } as RacerEntry;
    expect(finishPlaceLabel(entry)).toBe("1ST");
    expect(
      formatRacerRecordSummary({
        starts: 4,
        wins: 2,
        losses: 2,
        dnfs: 1,
        win_rate: 0.5,
      }),
    ).toBe("2-2 (50% wins · 1 DNFs)");
  });

  it("normalizes loading and API error labels", () => {
    expect(loadingActionLabel("Placing")).toBe("Placing…");
    expect(userFacingApiError(new ApiError("bad_stake", "Too much."), "fallback")).toBe(
      "Too much.",
    );
    expect(userFacingApiError(new Error("Network down"), "fallback")).toBe("Network down");
    expect(userFacingApiError({}, "fallback")).toBe("fallback");
  });
});
