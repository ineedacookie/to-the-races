import { racerPortraitPath } from "../shared/assets";
import { formatMoney, formatOdds } from "../shared/format";
import { formatRacerRecordSummary, loadingActionLabel } from "../shared/liveUi";
import type { LivePlayer, RacerEntry } from "../shared/types";
import {
  bettingOptionCanSubmit,
  type BettingOptions,
} from "./bettingOptions";

export interface RaceSheetElements {
  racerGrid: HTMLElement;
}

export interface RaceSheetContext {
  options: BettingOptions;
  pendingEntries: ReadonlySet<number>;
  selectedBetFor: (entry: RacerEntry, player: LivePlayer) => number;
  placeBet: (entry: RacerEntry) => void;
}

function betButtonLabel(isPending: boolean, stakeCents: number): string {
  return isPending ? loadingActionLabel("Placing") : `Bet ${formatMoney(stakeCents)}`;
}

function racerDetailHref(entry: RacerEntry): string {
  return `/racers/${encodeURIComponent(entry.slug)}/`;
}

function makeRacerCard(
  entry: RacerEntry,
  player: LivePlayer,
  context: RaceSheetContext,
): HTMLElement {
  const card = document.createElement("article");
  card.className = "racer-card";
  card.style.setProperty("--racer-color", entry.color);

  const heading = document.createElement("div");
  heading.className = "racer-card__heading";

  const portrait = document.createElement("img");
  portrait.className = "racer-portrait";
  portrait.src = racerPortraitPath(entry.sprite_key);
  portrait.alt = "";
  portrait.addEventListener("error", () => {
    portrait.hidden = true;
    heading.dataset.fallback = entry.name.slice(0, 1);
  });
  const portraitLink = document.createElement("a");
  portraitLink.className = "racer-card__portrait-link";
  portraitLink.href = racerDetailHref(entry);
  portraitLink.setAttribute("aria-label", `Open ${entry.name}'s racer dossier`);
  portraitLink.append(portrait);

  const nameWrap = document.createElement("div");
  const lane = document.createElement("span");
  lane.className = "eyebrow";
  lane.textContent = `Lane ${entry.lane}`;
  const name = document.createElement("h3");
  name.textContent = entry.name;
  const nameLink = document.createElement("a");
  nameLink.className = "racer-card__name-link";
  nameLink.href = racerDetailHref(entry);
  nameLink.append(name);
  const tagline = document.createElement("p");
  tagline.className = "racer-tagline";
  tagline.textContent = entry.tagline || "Mystery contender.";
  nameWrap.append(lane, nameLink, tagline);

  const odds = document.createElement("strong");
  odds.className = "odds-badge";
  odds.textContent = formatOdds(entry.odds);
  odds.setAttribute("aria-label", `${entry.odds} times payout`);
  heading.append(portraitLink, nameWrap, odds);

  const dossierLink = document.createElement("a");
  dossierLink.className = "racer-dossier-link";
  dossierLink.href = racerDetailHref(entry);
  dossierLink.textContent = "Read the classified dossier →";

  const meta = document.createElement("div");
  meta.className = "racer-card__meta";
  const crowd = document.createElement("span");
  crowd.textContent = `Crowd: ${formatMoney(entry.total_staked_cents)}`;
  const yours = document.createElement("span");
  const playerStake = context.selectedBetFor(entry, player);
  yours.textContent = playerStake > 0 ? `You: ${formatMoney(playerStake)}` : "No bet yet";
  const record = document.createElement("span");
  record.textContent = formatRacerRecordSummary(entry.record);
  meta.append(crowd, yours, record);

  const button = document.createElement("button");
  button.className = "bet-button";
  button.type = "button";
  button.textContent = betButtonLabel(
    context.pendingEntries.has(entry.id),
    context.options.stakeCents,
  );
  button.disabled = !bettingOptionCanSubmit(context.options, entry.id);
  button.addEventListener("click", () => {
    context.placeBet(entry);
  });

  card.append(heading, dossierLink, meta, button);
  return card;
}

export function renderRaceSheet(
  elements: RaceSheetElements,
  entries: RacerEntry[],
  player: LivePlayer,
  context: RaceSheetContext,
): void {
  elements.racerGrid.replaceChildren();
  for (const entry of entries) {
    elements.racerGrid.append(
      makeRacerCard(entry, player, context),
    );
  }
}

export function trackPositionLabel(position: number): string {
  if (position < 0.42) {
    return "Start";
  }
  if (position < 0.68) {
    return "Middle";
  }
  return "Final";
}

export function trackLaneLabel(lane: number, racerCount: number): string {
  return `Lane ${Math.max(Math.round(lane * (racerCount + 1)), 1)}`;
}
