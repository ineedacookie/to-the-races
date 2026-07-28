import { racerPortraitPath } from "../shared/assets";
import { renderEmptyState } from "../shared/dom";
import { formatMoney } from "../shared/format";
import { purchaseActionLabel, seatMarketPrice } from "../shared/liveUi";
import type { LivePlayer, LiveState, SeatClaim, SeatDefinition } from "../shared/types";

export interface SeatMarketElements {
  seatGrid: HTMLElement;
}

export interface SeatMarketContext {
  round: LiveState["round"] | null | undefined;
  room: LiveState["room"] | undefined;
  pendingSeats: ReadonlySet<string>;
  buySeat: (seat: SeatDefinition, expectedPriceCents: number) => void;
}

function makeSeatCard(
  seat: SeatDefinition,
  claim: SeatClaim | undefined,
  player: LivePlayer,
  marketOpen: boolean,
  context: SeatMarketContext,
): HTMLElement {
  const card = document.createElement("article");
  card.className = "seat-card";
  card.style.setProperty("--seat-color", seat.color);
  const isThrone = seat.slug.includes("throne");
  if (isThrone) {
    card.classList.add("seat-card--throne");
  }

  const crown = document.createElement("span");
  crown.className = "seat-crown";
  crown.textContent = "👑";
  crown.setAttribute("aria-hidden", "true");
  crown.hidden = !isThrone;

  const mascot = document.createElement("img");
  mascot.className = "seat-mascot";
  mascot.src = racerPortraitPath(seat.sprite_key);
  mascot.alt = "";
  mascot.width = 48;
  mascot.height = 48;

  const title = document.createElement("h3");
  title.textContent = seat.name;
  const perk = document.createElement("span");
  perk.className = "seat-perk";
  perk.textContent = `+${seat.payout_bonus_bps / 100}% winning profit`;
  const desc = document.createElement("p");
  desc.textContent = seat.description;
  const owner = document.createElement("p");
  owner.className = "seat-owner";
  const currentPriceCents = seatMarketPrice(
    seat.slug,
    context.room?.seat_catalog ?? [],
    context.round?.seat_markets,
  );
  const takeoverCount =
    context.round?.seat_markets.find((entry) => entry.seat_slug === seat.slug)?.takeover_count ??
    0;
  const claimed = claim !== undefined;
  owner.textContent = claimed
    ? `Held by ${claim.nickname}${claim.is_online ? "" : " · offline"} · ${formatMoney(currentPriceCents)}`
    : `${formatMoney(currentPriceCents)} · open`;
  if (takeoverCount > 0) {
    const escalation = document.createElement("span");
    escalation.className = "seat-escalation";
    escalation.textContent = `${takeoverCount} takeover${takeoverCount === 1 ? "" : "s"} this round`;
    owner.append(document.createElement("br"), escalation);
  }

  const claimBtn = document.createElement("button");
  claimBtn.type = "button";
  claimBtn.className = "seat-claim-btn";
  const alreadyOwns = player.seat_claim?.seat_slug === seat.slug;
  const canAfford = player.balance_cents >= currentPriceCents;
  claimBtn.textContent = purchaseActionLabel({
    pending: context.pendingSeats.has(seat.slug),
    pendingAction: "Taking over",
    blockedLabel: alreadyOwns ? "Your seat" : undefined,
    requiredCents: canAfford ? undefined : currentPriceCents,
    actionLabel: claimed
      ? `Take over · ${formatMoney(currentPriceCents)}`
      : `Claim · ${formatMoney(currentPriceCents)}`,
  });
  claimBtn.disabled = !marketOpen || alreadyOwns || !canAfford || context.pendingSeats.has(seat.slug);
  claimBtn.setAttribute(
    "aria-label",
    alreadyOwns ? `You already own ${seat.name}` : `Take over ${seat.name}`,
  );
  claimBtn.addEventListener("click", () => {
    context.buySeat(seat, currentPriceCents);
  });

  card.append(crown, mascot, title, perk, desc, owner, claimBtn);
  return card;
}

export function renderSeatMarket(
  elements: SeatMarketElements,
  player: LivePlayer,
  marketOpen: boolean,
  context: SeatMarketContext,
): void {
  elements.seatGrid.replaceChildren();
  const catalog = context.room?.seat_catalog ?? [];
  const claims = context.round?.seats ?? [];
  if (catalog.length === 0) {
    renderEmptyState(elements.seatGrid, "Grandstand seats will appear when the round opens.");
    return;
  }
  for (const seat of catalog) {
    const claim = claims.find((candidate) => candidate.seat_slug === seat.slug);
    elements.seatGrid.append(makeSeatCard(seat, claim, player, marketOpen, context));
  }
}
