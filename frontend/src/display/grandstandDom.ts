import { renderEmptyState } from "../shared/dom";
import { formatMoney } from "../shared/format";
import { formatBoardSnippetRow, raceResultView, seatMarketPrice } from "../shared/liveUi";
import type {
  ConnectedSpectator,
  LeaderboardRow,
  LiveRound,
  LiveState,
  SeatClaim,
  SeatDefinition,
  SeatMarket,
} from "../shared/types";
import {
  buildGrandstandModel,
  crowdRowLabel,
  spectatorArtPath,
} from "./grandstand";

export interface GrandstandDomElements {
  grandstandSeats: HTMLOListElement;
  grandstandCrowdRows: HTMLElement;
  resultsCard: HTMLElement;
  resultsTitle: HTMLElement;
  resultsList: HTMLElement;
  boardsSnippet: HTMLElement;
  leaderSnippet: HTMLOListElement;
  debtSnippet: HTMLOListElement;
}

function makeSpectatorCharacter(
  spectator: ConnectedSpectator,
  modifier: "crowd" | "prestige",
): HTMLElement {
  const character = document.createElement("span");
  character.className = `grandstand__character grandstand__character--${modifier}`;
  const avatar = document.createElement("img");
  avatar.src = spectatorArtPath(spectator);
  avatar.alt = "";
  avatar.width = 64;
  avatar.height = 112;
  character.append(avatar);
  return character;
}

export function renderGrandstandDom(
  elements: Pick<
    GrandstandDomElements,
    "grandstandSeats" | "grandstandCrowdRows"
  >,
  seats: SeatClaim[],
  catalog: SeatDefinition[],
  spectators: ConnectedSpectator[],
  seatMarkets: SeatMarket[] | undefined,
  renderKey: { current: string },
): void {
  const nextKey = JSON.stringify({
    catalog: catalog.map((seat) => [
      seat.slug,
      seat.name,
      seat.color,
      seat.price_cents,
      seat.payout_bonus_bps,
    ]),
    claims: seats.map((claim) => [
      claim.id,
      claim.player_id,
      claim.seat_slug,
      claim.seat_color,
      claim.nickname,
      claim.is_online,
      claim.current_price_cents,
      claim.takeover_count,
    ]),
    markets: seatMarkets?.map((market) => [
      market.seat_slug,
      market.current_price_cents,
      market.takeover_count,
    ]),
    spectators: spectators.map((spectator) => [
      spectator.player_id,
      spectator.nickname,
      spectator.avatar_version,
    ]),
  });
  if (nextKey === renderKey.current) {
    return;
  }

  const model = buildGrandstandModel(catalog, seats, spectators);
  elements.grandstandSeats.replaceChildren();
  for (const position of model.prestige) {
    const { seat, claim, spectator, rank } = position;
    const item = document.createElement("li");
    item.className = "grandstand__position";
    item.style.setProperty("--seat-color", seat.color);
    item.dataset.seatName = seat.name;
    item.dataset.rank = String(rank);
    if (spectator !== undefined) {
      item.dataset.playerId = String(spectator.player_id);
      item.dataset.ownerNickname = spectator.nickname;
    }
    item.classList.toggle("grandstand__seat--open", claim === undefined);
    item.classList.toggle(
      "grandstand__seat--offline",
      claim !== undefined && spectator === undefined,
    );
    const isThrone = seat.slug.includes("throne") || seat.name.toLowerCase().includes("throne");
    if (isThrone) {
      item.classList.add("grandstand__seat--throne");
    }

    const rankBadge = document.createElement("strong");
    rankBadge.className = "grandstand__rank";
    rankBadge.textContent = rank === 1 ? "#1 CROWN" : `#${rank} VIP`;

    const name = document.createElement("strong");
    name.className = "grandstand__seat-name";
    name.textContent = isThrone ? "The Throne" : seat.name;
    name.title = seat.name;

    const perk = document.createElement("span");
    perk.className = "grandstand__perk";
    perk.textContent = `+${seat.payout_bonus_bps / 100}% WINNINGS`;

    const occupant = document.createElement("div");
    occupant.className = "grandstand__occupant";
    if (spectator !== undefined) {
      const figure = document.createElement("div");
      figure.className = "grandstand__figure";
      figure.append(makeSpectatorCharacter(spectator, "prestige"));
      const owner = document.createElement("strong");
      owner.className = "grandstand__owner";
      owner.textContent = spectator.nickname;
      owner.title = spectator.nickname;
      figure.append(owner);
      occupant.append(figure);
    } else {
      const vacancy = document.createElement("span");
      vacancy.className = "grandstand__vacancy";
      vacancy.setAttribute("aria-hidden", "true");
      vacancy.textContent = rank === 1 ? "♛" : "◆";
      const status = document.createElement("strong");
      status.className = "grandstand__owner";
      status.textContent =
        claim === undefined
          ? `OPEN · ${formatMoney(seatMarketPrice(seat.slug, catalog, seatMarkets))}`
          : `${claim.nickname.toUpperCase()} · OFFLINE`;
      occupant.append(vacancy, status);
    }
    item.append(rankBadge, name, perk, occupant);
    elements.grandstandSeats.append(item);
  }

  elements.grandstandCrowdRows.replaceChildren();
  for (const row of model.crowdRows) {
    const rowElement = document.createElement("section");
    rowElement.className = "grandstand__crowd-row";
    rowElement.style.setProperty("--row-index", String(row.rowIndex));

    const rowName = document.createElement("strong");
    rowName.className = "grandstand__row-name";
    rowName.textContent = crowdRowLabel(row.rowIndex, model.crowdRows.length);

    const list = document.createElement("ol");
    list.setAttribute("aria-label", rowName.textContent);
    for (const slot of row.slots) {
      const item = document.createElement("li");
      item.className = "grandstand__crowd-slot";
      if (slot.spectator === undefined) {
        item.classList.add("grandstand__crowd-slot--empty");
        item.setAttribute("aria-hidden", "true");
      } else {
        item.dataset.playerId = String(slot.spectator.player_id);
        const figure = document.createElement("div");
        figure.className = "grandstand__figure";
        figure.append(makeSpectatorCharacter(slot.spectator, "crowd"));
        const owner = document.createElement("strong");
        owner.className = "grandstand__owner";
        owner.textContent = slot.spectator.nickname;
        owner.title = slot.spectator.nickname;
        figure.append(owner);
        item.append(figure);
      }
      list.append(item);
    }
    rowElement.append(rowName, list);
    elements.grandstandCrowdRows.append(rowElement);
  }
  renderKey.current = nextKey;
}

function renderBoardSnippet(
  list: HTMLOListElement,
  rows: LeaderboardRow[],
  emptyText: string,
  useNet = false,
): void {
  list.replaceChildren();
  const top = rows.slice(0, 3);
  if (top.length === 0) {
    renderEmptyState(list, emptyText, "li", "");
    return;
  }
  for (const row of top) {
    const item = document.createElement("li");
    item.textContent = formatBoardSnippetRow(row, useNet);
    list.append(item);
  }
}

export function renderDisplayResults(
  elements: GrandstandDomElements,
  round: LiveRound,
  currentState: LiveState,
): void {
  const showing = round.state === "results";
  elements.resultsCard.hidden = !showing;
  elements.resultsList.replaceChildren();
  if (!showing) {
    elements.boardsSnippet.hidden = true;
    return;
  }
  const result = raceResultView(round.entries);
  elements.resultsTitle.textContent =
    result.winner === null
      ? "Nobody finished. The house wins!"
      : `${result.winner.name} takes it!`;

  for (const row of result.rows) {
    const item = document.createElement("li");
    item.style.setProperty("--racer-color", row.entry.color);
    const place = document.createElement("strong");
    place.textContent = row.placeLabel;
    const name = document.createElement("span");
    name.textContent = row.entry.name;
    item.append(place, name);
    elements.resultsList.append(item);
  }

  const hasBoards =
    currentState.leaderboard.length > 0 || currentState.debt_board.length > 0;
  elements.boardsSnippet.hidden = !hasBoards;
  if (hasBoards) {
    renderBoardSnippet(elements.leaderSnippet, currentState.leaderboard, "No leaders yet");
    renderBoardSnippet(
      elements.debtSnippet,
      currentState.debt_board,
      "No net losses yet",
      true,
    );
  }
}

export function crowdPotCents(round: LiveRound | null, itemCatalogPrice: (slug: string) => number): number {
  if (round === null) {
    return 0;
  }
  const betPot = round.entries.reduce((total, entry) => total + entry.total_staked_cents, 0);
  return betPot + itemSpendCents(round, itemCatalogPrice);
}

export function itemSpendCents(round: LiveRound | null, itemCatalogPrice: (slug: string) => number): number {
  if (round === null) {
    return 0;
  }
  return round.item_uses.reduce(
    (total, use) => total + itemCatalogPrice(use.item_slug),
    0,
  );
}
