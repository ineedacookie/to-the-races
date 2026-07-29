import { renderEmptyState } from "../shared/dom";
import { formatMoney, formatOdds } from "../shared/format";
import {
  formatBoardStats,
  formatPlayerBettingRecordSummary,
  presentationRound,
  raceResultView,
} from "../shared/liveUi";
import type { LeaderboardRow, LivePlayer, LiveState } from "../shared/types";

export interface AccountRecordsElements {
  accountName: HTMLElement;
  accountAvatar: HTMLImageElement;
  accountBalance: HTMLElement;
  accountStaked: HTMLElement;
  accountBettingRecord: HTMLElement;
  accountInventory: HTMLElement;
  inventorySeat: HTMLElement;
  inventoryTabCount: HTMLElement;
  leaderboardList: HTMLElement;
  debtList: HTMLElement;
  ledgerList: HTMLElement;
  betsList: HTMLElement;
  resultsPanel: HTMLElement;
  resultsTitle: HTMLElement;
  resultsList: HTMLElement;
}

export interface AccountRecordsContext {
  playerInventoryCapacity: (player: LivePlayer) => number;
}

function renderBoardRow(row: LeaderboardRow, showNet = false): HTMLElement {
  const item = document.createElement("li");
  const rank = document.createElement("span");
  rank.className = "board-rank";
  rank.textContent = `#${row.rank}`;
  const name = document.createElement("strong");
  name.textContent = row.nickname;
  const stats = document.createElement("span");
  stats.className = "board-stats";
  stats.textContent = formatBoardStats(row, showNet);
  stats.classList.toggle("is-negative", row.betting_record.net_cents < 0);
  item.append(rank, name, stats);
  return item;
}

export function renderBoards(
  elements: AccountRecordsElements,
  currentState: LiveState,
): void {
  elements.leaderboardList.replaceChildren();
  elements.debtList.replaceChildren();
  const leaders = currentState.leaderboard;
  const debtors = currentState.debt_board;
  if (leaders.length === 0) {
    renderEmptyState(elements.leaderboardList, "Nobody on the board yet.", "li");
  } else {
    for (const row of leaders) {
      elements.leaderboardList.append(renderBoardRow(row));
    }
  }
  if (debtors.length === 0) {
    renderEmptyState(elements.debtList, "No net betting losses yet—suspicious.", "li");
  } else {
    for (const row of debtors) {
      elements.debtList.append(renderBoardRow(row, true));
    }
  }
}

export function renderAccountAndInventory(
  elements: AccountRecordsElements,
  context: AccountRecordsContext,
  player: LivePlayer,
): void {
  elements.accountName.textContent = player.nickname;
  elements.accountAvatar.src = player.avatar_url;
  elements.accountAvatar.alt = `${player.nickname}'s bleacher character`;
  elements.accountBalance.textContent = formatMoney(player.balance_cents);
  elements.accountStaked.textContent = formatMoney(player.round_staked_cents);
  const betting = player.betting_record;
  elements.accountBettingRecord.textContent = formatPlayerBettingRecordSummary(betting);
  elements.accountBettingRecord.classList.toggle("is-negative", betting.net_cents < 0);
  elements.accountInventory.textContent = `${player.inventory.length} in bag · capacity ${context.playerInventoryCapacity(player)} slots · ${
    player.owned_upgrades.length
  } permanent upgrade${player.owned_upgrades.length === 1 ? "" : "s"}`;
  elements.inventorySeat.textContent =
    player.seat_claim === null
      ? "No prestige seat owned."
      : `Seat: ${player.seat_claim.seat_name} · +${
          player.seat_claim.payout_bonus_bps / 100
        }% winning profit · held until outbid`;
  const inventoryCount = player.inventory.length;
  elements.inventoryTabCount.textContent = String(inventoryCount);
  elements.inventoryTabCount
    .closest("button")
    ?.setAttribute(
      "aria-label",
      `Inventory, ${inventoryCount} item${inventoryCount === 1 ? "" : "s"}`,
    );
}

export function renderBets(elements: AccountRecordsElements, player: LivePlayer): void {
  elements.betsList.replaceChildren();
  if (player.bets.length === 0) {
    renderEmptyState(elements.betsList, "No tickets this round—yet.", "li");
    return;
  }

  for (const bet of player.bets) {
    const item = document.createElement("li");
    const label = document.createElement("span");
    label.textContent = `${bet.racer_name} · ${formatOdds(bet.odds)}`;
    const value = document.createElement("strong");
    value.textContent =
      bet.status === "won"
        ? `+${formatMoney(bet.payout_cents)}`
        : `${formatMoney(bet.amount_cents)} · ${bet.status}`;
    item.append(label, value);
    elements.betsList.append(item);
  }
}

export function renderLedger(elements: AccountRecordsElements, player: LivePlayer): void {
  elements.ledgerList.replaceChildren();
  const rows = player.recent_ledger;
  if (rows.length === 0) {
    renderEmptyState(elements.ledgerList, "No ledger entries yet.", "li");
    return;
  }
  for (const row of rows) {
    const item = document.createElement("li");
    const desc = document.createElement("span");
    desc.textContent = row.description;
    const amount = document.createElement("strong");
    amount.textContent = formatMoney(row.amount_cents);
    amount.classList.toggle("is-negative", row.amount_cents < 0);
    item.append(desc, amount);
    elements.ledgerList.append(item);
  }
}

export function renderBettingResults(
  elements: AccountRecordsElements,
  currentState: LiveState,
  onFirstResult: (roundId: number, title: string) => void,
): void {
  const round = presentationRound(currentState);
  const show = round?.state === "results";
  elements.resultsPanel.hidden = !show;
  elements.resultsList.replaceChildren();
  if (!show || round === null) {
    return;
  }

  const result = raceResultView(round.entries);
  elements.resultsTitle.textContent =
    result.winner === null ? "Total chaos. The house wins." : `${result.winner.name} wins!`;
  for (const row of result.rows) {
    const item = document.createElement("li");
    const place = document.createElement("strong");
    place.textContent = row.placeLabel;
    const name = document.createElement("span");
    name.textContent = row.entry.name;
    item.append(place, name);
    elements.resultsList.append(item);
  }
  onFirstResult(round.id, elements.resultsTitle.textContent ?? "result posted");
}
