import Phaser from "phaser";

import {
  activeCountdownSeconds,
  dnfLabel,
  formatMoney,
  ordinal,
  secondsRemaining,
} from "../shared/format";
import { LiveSocket, type ConnectionStatus } from "../shared/socket";
import {
  assertNever,
  type AudienceReaction,
  type ConnectedSpectator,
  type LeaderboardRow,
  type LiveRound,
  type LiveState,
  type RaceEvent,
  type SeatClaim,
  type SeatDefinition,
  type ServerMessage,
} from "../shared/types";
import {
  buildGrandstandModel,
  crowdRowLabel,
  spectatorArtPath,
} from "./grandstand";
import {
  RaceScene,
  RACER_NAME_TAGS_EVENT,
  type RacerNameTag,
} from "./RaceScene";

function required<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (element === null) {
    throw new Error(`Missing required element: ${selector}`);
  }
  return element;
}

const roundNumber = required<HTMLElement>("#display-round");
const phase = required<HTMLElement>("#display-phase");
const clockLabel = required<HTMLElement>("#display-clock-label");
const countdown = required<HTMLElement>("#display-countdown");
const potLabel = required<HTMLElement>("#display-pot-label");
const pot = required<HTMLElement>("#display-pot");
const joinCard = required<HTMLElement>("#join-card");
const grandstand = required<HTMLElement>("#grandstand");
const grandstandSeats = required<HTMLOListElement>("#grandstand-seats");
const grandstandCrowdRows = required<HTMLElement>("#grandstand-crowd-rows");
const grandstandPresence = required<HTMLElement>("#grandstand-presence");
const racerNameLayer = required<HTMLElement>("#racer-name-layer");
const eventCard = required<HTMLElement>("#event-card");
const eventText = required<HTMLElement>("#event-text");
const resultsCard = required<HTMLElement>("#display-results");
const resultsTitle = required<HTMLElement>("#display-results-title");
const resultsList = required<HTMLElement>("#display-results-list");
const boardsSnippet = required<HTMLElement>("#display-boards-snippet");
const leaderSnippet = required<HTMLOListElement>("#display-leader-snippet");
const debtSnippet = required<HTMLOListElement>("#display-debt-snippet");
const reactionLayer = required<HTMLElement>("#reaction-layer");
const connection = required<HTMLElement>("#display-connection");
const fullscreenButton = required<HTMLButtonElement>("#fullscreen-button");
const muteButton = required<HTMLButtonElement>("#mute-button");

let state: LiveState | null = null;
let serverOffsetMs = 0;
let eventTimer: number | null = null;
let muted = false;
let grandstandRenderKey = "";
const racerNameElements = new Map<number, HTMLElement>();
const connectedSpectators = new Map<number, ConnectedSpectator>();
const DEFAULT_REACTION_DISPLAY_MS = 3_000;
const REACTION_SEAT_CLASSES = [
  "grandstand__seat--reacting",
  "grandstand__seat--reacting-cheer",
  "grandstand__seat--reacting-boo",
  "grandstand__seat--reacting-cry",
  "grandstand__seat--reacting-shout",
] as const;

const sounds = {
  bodyCheck: new Audio("/static/assets/audio/body-check.ogg"),
  finish: new Audio("/static/assets/audio/finish.ogg"),
  knockout: new Audio("/static/assets/audio/knockout.ogg"),
  stumble: new Audio("/static/assets/audio/stumble.ogg"),
};
Object.values(sounds).forEach((sound) => {
  sound.preload = "auto";
});
const activeSoundClips = new Set<HTMLAudioElement>();

function renderRacerNameTags(tags: RacerNameTag[]): void {
  const wantedRacerIds = new Set(tags.map((tag) => tag.racerId));
  for (const [racerId, element] of racerNameElements) {
    if (!wantedRacerIds.has(racerId)) {
      element.remove();
      racerNameElements.delete(racerId);
    }
  }

  for (const tag of tags) {
    let element = racerNameElements.get(tag.racerId);
    if (element === undefined) {
      element = document.createElement("strong");
      element.className = "racer-name-tag";
      element.dataset.racerId = String(tag.racerId);
      racerNameLayer.append(element);
      racerNameElements.set(tag.racerId, element);
    }
    if (element.textContent !== tag.name) {
      element.textContent = tag.name;
    }
    element.style.left = `${tag.x * 100}%`;
    element.style.top = `${tag.y * 100}%`;
  }
}

const game = new Phaser.Game({
  type: Phaser.AUTO,
  parent: "game-canvas",
  width: 1280,
  height: 720,
  backgroundColor: "#92c9d8",
  pixelArt: true,
  antialias: false,
  scene: [RaceScene],
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
});
game.events.on(RACER_NAME_TAGS_EVENT, renderRacerNameTags);

function setConnection(status: ConnectionStatus): void {
  connection.dataset.status = status;
  switch (status) {
    case "connecting":
      connection.textContent = "Connecting";
      break;
    case "connected":
      connection.textContent = "Live";
      break;
    case "disconnected":
      connection.textContent = "Reconnecting";
      break;
    default:
      assertNever(status);
  }
}

function phaseCopy(round: LiveRound | null): string {
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

function updateClock(): void {
  const round = state?.round;
  clockLabel.textContent = "Clock";
  countdown.classList.remove("is-finish-clock");
  if (round === null || round === undefined) {
    countdown.textContent = "—";
    return;
  }
  let deadline: string;
  switch (round.state) {
    case "open":
      deadline = round.locks_at;
      break;
    case "locked":
      deadline = round.race_starts_at;
      break;
    case "racing": {
      const finishClock = activeCountdownSeconds(
        round.finish_countdown_starts_at,
        round.finish_countdown_ends_at,
        serverOffsetMs,
      );
      if (finishClock === null) {
        countdown.textContent = "LIVE";
        return;
      }
      clockLabel.textContent = "Finish clock";
      countdown.classList.add("is-finish-clock");
      countdown.textContent = `${finishClock}`;
      return;
    }
    case "results":
      deadline = round.results_end_at;
      break;
    default:
      assertNever(round.state);
  }
  countdown.textContent = `${secondsRemaining(deadline, serverOffsetMs)}`;
}

function crowdPotCents(round: LiveRound | null): number {
  if (round === null) {
    return 0;
  }
  const betPot = round.entries.reduce((total, entry) => total + entry.total_staked_cents, 0);
  const itemPot = round.item_uses.reduce((total, use) => {
    const catalogItem = state?.room.item_catalog.find((item) => item.slug === use.item_slug);
    return total + (catalogItem?.price_cents ?? 0);
  }, 0);
  return betPot + itemPot;
}

function itemSpendCents(round: LiveRound | null): number {
  if (round === null) {
    return 0;
  }
  return round.item_uses.reduce((total, use) => {
    const catalogItem = state?.room.item_catalog.find((item) => item.slug === use.item_slug);
    return total + (catalogItem?.price_cents ?? 0);
  }, 0);
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

function renderGrandstand(
  seats: SeatClaim[],
  catalog: SeatDefinition[],
  spectators: ConnectedSpectator[],
): void {
  const renderKey = JSON.stringify({
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
    ]),
    spectators: spectators.map((spectator) => [
      spectator.player_id,
      spectator.nickname,
      spectator.avatar_version,
    ]),
  });
  if (renderKey === grandstandRenderKey) {
    return;
  }

  const model = buildGrandstandModel(catalog, seats, spectators);
  grandstandPresence.textContent = `${model.connectedCount} connected`;
  grandstandSeats.replaceChildren();
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
    rankBadge.textContent = rank === 1 ? "#1 CROWN" : `#${rank} PRESTIGE`;

    const name = document.createElement("strong");
    name.className = "grandstand__seat-name";
    name.textContent = seat.name;
    name.title = seat.name;

    const perk = document.createElement("span");
    perk.className = "grandstand__perk";
    perk.textContent = `+${seat.payout_bonus_bps / 100}% WIN PROFIT`;

    const occupant = document.createElement("div");
    occupant.className = "grandstand__occupant";
    if (spectator !== undefined) {
      occupant.append(makeSpectatorCharacter(spectator, "prestige"));
      const owner = document.createElement("strong");
      owner.className = "grandstand__owner";
      owner.textContent = spectator.nickname;
      owner.title = spectator.nickname;
      occupant.append(owner);
    } else {
      const vacancy = document.createElement("span");
      vacancy.className = "grandstand__vacancy";
      vacancy.setAttribute("aria-hidden", "true");
      vacancy.textContent = rank === 1 ? "♛" : "◆";
      const status = document.createElement("strong");
      status.className = "grandstand__owner";
      status.textContent =
        claim === undefined
          ? `OPEN · ${formatMoney(seat.price_cents)}`
          : "RESERVED · VIEWER OFFLINE";
      occupant.append(vacancy, status);
    }
    item.append(rankBadge, name, perk, occupant);
    grandstandSeats.append(item);
  }

  grandstandCrowdRows.replaceChildren();
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
        item.append(makeSpectatorCharacter(slot.spectator, "crowd"));
        const owner = document.createElement("strong");
        owner.className = "grandstand__owner";
        owner.textContent = slot.spectator.nickname;
        owner.title = slot.spectator.nickname;
        item.append(owner);
      }
      list.append(item);
    }
    rowElement.append(rowName, list);
    grandstandCrowdRows.append(rowElement);
  }
  grandstandRenderKey = renderKey;
}

function renderBoardSnippet(
  list: HTMLOListElement,
  rows: LeaderboardRow[],
  emptyText: string,
): void {
  list.replaceChildren();
  const top = rows.slice(0, 3);
  if (top.length === 0) {
    const item = document.createElement("li");
    item.textContent = emptyText;
    list.append(item);
    return;
  }
  for (const row of top) {
    const item = document.createElement("li");
    item.textContent = `#${row.rank} ${row.nickname} · ${formatMoney(row.balance_cents)}`;
    list.append(item);
  }
}

function renderResults(round: LiveRound, currentState: LiveState): void {
  const showing = round.state === "results";
  resultsCard.hidden = !showing;
  resultsList.replaceChildren();
  if (!showing) {
    boardsSnippet.hidden = true;
    return;
  }
  const finishers = [...round.entries]
    .filter((entry) => entry.finish_place !== null)
    .sort((first, second) => (first.finish_place ?? 99) - (second.finish_place ?? 99));
  const nonFinishers = round.entries.filter((entry) => entry.finish_place === null);
  resultsTitle.textContent =
    finishers.length === 0
      ? "Nobody finished. The house wins!"
      : `${finishers[0]?.name ?? "A mystery racer"} takes it!`;

  for (const entry of [...finishers, ...nonFinishers]) {
    const item = document.createElement("li");
    item.style.setProperty("--racer-color", entry.color);
    const place = document.createElement("strong");
    place.textContent =
      entry.finish_place === null
        ? dnfLabel(entry.dnf_reason)
        : ordinal(entry.finish_place).toUpperCase();
    const name = document.createElement("span");
    name.textContent = entry.name;
    item.append(place, name);
    resultsList.append(item);
  }

  const hasBoards =
    (currentState.leaderboard?.length ?? 0) > 0 || (currentState.debt_board?.length ?? 0) > 0;
  boardsSnippet.hidden = !hasBoards;
  if (hasBoards) {
    renderBoardSnippet(leaderSnippet, currentState.leaderboard ?? [], "No leaders yet");
    renderBoardSnippet(debtSnippet, currentState.debt_board ?? [], "No debtors");
  }
}

function spawnReactionBubble(reaction: AudienceReaction): void {
  const bubble = document.createElement("div");
  bubble.className = "reaction-bubble";
  bubble.style.setProperty("--seat-color", reaction.seat_color || "#f3bc3e");
  const displayMs = Math.min(
    Math.max(reaction.display_ms ?? DEFAULT_REACTION_DISPLAY_MS, 1_000),
    10_000,
  );
  bubble.style.setProperty("--reaction-duration", `${displayMs}ms`);
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let label: string;
  switch (reaction.kind) {
    case "cheer":
      label = reaction.text || "Cheer!";
      bubble.classList.add("reaction-bubble--cheer");
      break;
    case "boo":
      label = reaction.text || "Boo!";
      bubble.classList.add("reaction-bubble--boo");
      break;
    case "cry":
      label = reaction.text || "Waaah!";
      bubble.classList.add("reaction-bubble--cry");
      break;
    case "shout":
      label = reaction.text || "…";
      bubble.classList.add("reaction-bubble--shout");
      break;
    default:
      return assertNever(reaction.kind);
  }

  const who = document.createElement("small");
  who.textContent = reaction.seat_name
    ? `${reaction.nickname} · ${reaction.seat_name}`
    : reaction.nickname;
  const text = document.createElement("strong");
  text.textContent = label;
  bubble.append(who, text);

  const reactionAnchor = grandstand.querySelector<HTMLElement>(
    `[data-player-id="${reaction.player_id}"]`,
  );
  let reactionToken = "";
  if (reactionAnchor !== null) {
    const seatBounds = reactionAnchor.getBoundingClientRect();
    const layerBounds = reactionLayer.getBoundingClientRect();
    bubble.classList.add("reaction-bubble--seated");
    bubble.style.left = `${seatBounds.left + seatBounds.width / 2 - layerBounds.left}px`;
    bubble.style.top = `${seatBounds.top - layerBounds.top - 4}px`;
    reactionToken = `${reaction.at}:${Math.random()}`;
    reactionAnchor.dataset.reactionToken = reactionToken;
    reactionAnchor.style.setProperty("--reaction-duration", `${displayMs}ms`);
    reactionAnchor.classList.remove(...REACTION_SEAT_CLASSES);
    reactionAnchor.classList.add(
      "grandstand__seat--reacting",
      `grandstand__seat--reacting-${reaction.kind}`,
    );
  } else {
    let nicknameHash = 0;
    for (const character of reaction.nickname) {
      nicknameHash = (nicknameHash * 31 + (character.codePointAt(0) ?? 0)) >>> 0;
    }
    const grandstandBounds = grandstand.getBoundingClientRect();
    const layerBounds = reactionLayer.getBoundingClientRect();
    const horizontalPosition = 0.12 + (nicknameHash % 77) / 100;
    bubble.classList.add("reaction-bubble--seated", "reaction-bubble--standing-room");
    bubble.style.left = `${
      grandstandBounds.left +
      grandstandBounds.width * horizontalPosition -
      layerBounds.left
    }px`;
    bubble.style.top = `${grandstandBounds.top - layerBounds.top + 4}px`;
  }
  reactionLayer.append(bubble);

  let removed = false;
  let cleanupTimer: number | null = null;
  const cleanup = (): void => {
    if (removed) {
      return;
    }
    removed = true;
    if (cleanupTimer !== null) {
      window.clearTimeout(cleanupTimer);
    }
    bubble.remove();
    if (
      reactionAnchor !== null &&
      reactionAnchor.dataset.reactionToken === reactionToken
    ) {
      reactionAnchor.classList.remove(...REACTION_SEAT_CLASSES);
      reactionAnchor.style.removeProperty("--reaction-duration");
      delete reactionAnchor.dataset.reactionToken;
    }
  };

  cleanupTimer = window.setTimeout(cleanup, displayMs + (reducedMotion ? 0 : 150));
  if (!reducedMotion) {
    bubble.addEventListener("animationend", cleanup, { once: true });
  }
}

function render(nextState: LiveState): void {
  state = nextState;
  serverOffsetMs = Date.parse(nextState.server_time) - Date.now();
  const round = nextState.round;
  roundNumber.textContent = round === null ? "Next round" : `Round ${round.number}`;
  phase.textContent = nextState.room.is_paused ? "Race night paused" : phaseCopy(round);

  const chaosSpend = itemSpendCents(round);
  if (chaosSpend > 0) {
    potLabel.textContent = "Chaos fund";
    pot.textContent = formatMoney(chaosSpend);
  } else {
    potLabel.textContent = "Crowd pot";
    pot.textContent = formatMoney(crowdPotCents(round));
  }

  renderGrandstand(
    round?.seats ?? [],
    nextState.room.seat_catalog,
    [...connectedSpectators.values()],
  );
  joinCard.classList.toggle("join-card--compact", round?.state !== "open");
  updateClock();
  if (round !== null) {
    renderResults(round, nextState);
  } else {
    resultsCard.hidden = true;
    boardsSnippet.hidden = true;
  }
  game.registry.set("liveState", nextState);
  game.events.emit("live-state", nextState);
}

function playEventSound(event: RaceEvent): void {
  if (muted) {
    return;
  }
  let sound: HTMLAudioElement | null;
  switch (event.kind) {
    case "finish":
      sound = sounds.finish;
      break;
    case "knockout":
    case "pileup":
    case "destroyed":
      sound = sounds.knockout;
      break;
    case "body_check":
    case "stomp":
    case "obstacle_hit":
      sound = sounds.bodyCheck;
      break;
    case "potion_triggered":
    case "potion_fizzled":
    case "portal_hop":
    case "second_wind":
    case "panic_sprint":
      sound = sounds.stumble;
      break;
    case "recover":
    case "turn_around":
    case "wrong_way":
    case "lane_drift":
    case "stumble":
    case "showboat":
    case "evasive_juke":
      sound = sounds.stumble;
      break;
    case "start":
    case "timeout":
    case "potion_used":
      sound = null;
      break;
    default:
      return assertNever(event.kind);
  }
  if (sound !== null) {
    const clip = sound.cloneNode(true) as HTMLAudioElement;
    const releaseClip = (): void => {
      activeSoundClips.delete(clip);
      clip.removeEventListener("ended", releaseClip);
      clip.removeEventListener("error", releaseClip);
      clip.pause();
    };
    clip.volume = 0.42;
    clip.addEventListener("ended", releaseClip, { once: true });
    clip.addEventListener("error", releaseClip, { once: true });
    activeSoundClips.add(clip);
    void clip.play().catch(releaseClip);
  }
}

function showRaceEvent(event: RaceEvent): void {
  eventText.textContent = event.message;
  eventCard.dataset.kind = event.kind;
  eventCard.hidden = false;
  playEventSound(event);
  if (eventTimer !== null) {
    window.clearTimeout(eventTimer);
  }
  eventTimer = window.setTimeout(() => {
    eventCard.hidden = true;
  }, 2_200);
}

function renderConnectedCrowd(): void {
  if (state === null) {
    return;
  }
  renderGrandstand(
    state.round?.seats ?? [],
    state.room.seat_catalog,
    [...connectedSpectators.values()],
  );
}

function handleMessage(message: ServerMessage): void {
  switch (message.type) {
    case "state.sync":
    case "round.opened":
    case "round.locked":
    case "race.started":
    case "race.finished":
    case "bets.updated":
    case "items.updated":
    case "seats.updated":
      render(message.state);
      break;
    case "audience.reaction":
      spawnReactionBubble(message.reaction);
      break;
    case "presence.sync":
      connectedSpectators.clear();
      for (const spectator of message.spectators) {
        connectedSpectators.set(spectator.player_id, spectator);
      }
      renderConnectedCrowd();
      break;
    case "presence.join":
      connectedSpectators.set(message.spectator.player_id, message.spectator);
      renderConnectedCrowd();
      break;
    case "presence.leave":
      connectedSpectators.delete(message.player_id);
      renderConnectedCrowd();
      break;
    case "audience.rejected":
      break;
    case "balance.updated":
    case "pong":
      break;
    default:
      assertNever(message);
  }
}

game.events.on("race-event", (event: RaceEvent) => {
  showRaceEvent(event);
});

fullscreenButton.addEventListener("click", () => {
  if (document.fullscreenElement === null) {
    void document.documentElement.requestFullscreen();
  } else {
    void document.exitFullscreen();
  }
});

muteButton.addEventListener("click", () => {
  muted = !muted;
  muteButton.textContent = muted ? "Sound off" : "Sound on";
  muteButton.setAttribute("aria-pressed", String(muted));
});

const socket = new LiveSocket({
  role: "display",
  onMessage: handleMessage,
  onStatus: setConnection,
});
socket.start();
window.setInterval(updateClock, 250);
