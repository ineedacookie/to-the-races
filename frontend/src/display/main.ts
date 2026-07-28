import Phaser from "phaser";

import { required } from "../shared/dom";
import { formatMoney } from "../shared/format";
import {
  applyConnectionStatus,
  createLiveClockController,
  displayPhaseLabel,
} from "../shared/liveUi";
import { defaultReactionMessage } from "../shared/reactions";
import { LiveSocket } from "../shared/socket";
import {
  assertNever,
  type AudienceReaction,
  type ConnectedSpectator,
  type LiveState,
  type RaceEvent,
  type ServerMessage,
} from "../shared/types";
import {
  FIRST_FINISHER_EVENT,
  isOfficialFirstFinish,
  isPriorityRaceEvent,
} from "./firstFinisher";
import {
  crowdPotCents,
  itemSpendCents,
  renderDisplayResults,
  renderGrandstandDom,
  type GrandstandDomElements,
} from "./grandstandDom";
import {
  RaceScene,
  RACER_NAME_TAGS_EVENT,
  RACE_EVENT_SOUND_EVENT,
  type RacerNameTag,
} from "./RaceScene";

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

const grandstandElements: GrandstandDomElements = {
  grandstandSeats,
  grandstandCrowdRows,
  resultsCard,
  resultsTitle,
  resultsList,
  boardsSnippet,
  leaderSnippet,
  debtSnippet,
};

let state: LiveState | null = null;
let eventTimer: number | null = null;
let importantEventVisibleUntil = 0;
let muted = false;
const grandstandRenderKey = { current: "" };
const racerNameElements = new Map<number, HTMLElement>();
const connectedSpectators = new Map<number, ConnectedSpectator>();
const liveClock = createLiveClockController({
  clockLabel,
  countdown,
  getRound: () => state?.round,
});
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

function itemCatalogPrice(slug: string): number {
  const catalogItem = state?.room.item_catalog.find((item) => item.slug === slug);
  return catalogItem?.price_cents ?? 0;
}

function renderRacerNameTags(tags: RacerNameTag[]): void {
  const hideDuringRace = state?.round?.state === "racing";
  racerNameLayer.hidden = hideDuringRace;
  if (hideDuringRace) {
    for (const element of racerNameElements.values()) {
      element.remove();
    }
    racerNameElements.clear();
    return;
  }
  for (const [racerId, element] of racerNameElements) {
    if (!tags.some((tag) => tag.racerId === racerId)) {
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

function setConnection(status: Parameters<LiveSocket["options"]["onStatus"]>[0]): void {
  applyConnectionStatus(connection, status);
}

function renderGrandstandFromState(): void {
  if (state === null) {
    return;
  }
  renderGrandstandDom(
    grandstandElements,
    state.round?.seats ?? [],
    state.room.seat_catalog,
    [...connectedSpectators.values()],
    state.round?.seat_markets,
    grandstandRenderKey,
  );
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

  const label = reaction.text || defaultReactionMessage(reaction.kind);
  bubble.classList.add(`reaction-bubble--${reaction.kind}`);

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
  liveClock.sync(nextState.server_time);
  const round = nextState.round;
  roundNumber.textContent = round === null ? "Next round" : `Round ${round.number}`;
  phase.textContent = displayPhaseLabel(round, nextState.room.is_paused);

  const chaosSpend = itemSpendCents(round, itemCatalogPrice);
  if (chaosSpend > 0) {
    potLabel.textContent = "Chaos fund";
    pot.textContent = formatMoney(chaosSpend);
  } else {
    potLabel.textContent = "Crowd pot";
    pot.textContent = formatMoney(crowdPotCents(round, itemCatalogPrice));
  }

  renderGrandstandFromState();
  joinCard.classList.toggle("join-card--compact", round?.state !== "open");
  if (round !== null) {
    renderDisplayResults(grandstandElements, round, nextState);
  } else {
    resultsCard.hidden = true;
    boardsSnippet.hidden = true;
  }
  racerNameLayer.hidden = round?.state === "racing";
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
    case "obstacle_hit":
    case "obstacle_removed":
    case "item_cleared":
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
  const firstFinish = isOfficialFirstFinish(event);
  const important = isPriorityRaceEvent(event);
  playEventSound(event);
  if (!important && performance.now() < importantEventVisibleUntil) {
    return;
  }
  const displayDuration = important ? 3_200 : 2_200;
  importantEventVisibleUntil = important ? performance.now() + displayDuration : 0;
  eventText.textContent = event.message;
  eventCard.dataset.kind = event.kind;
  eventCard.classList.toggle("event-card--first-finish", firstFinish);
  eventCard.hidden = false;
  if (eventTimer !== null) {
    window.clearTimeout(eventTimer);
  }
  eventTimer = window.setTimeout(() => {
    eventCard.hidden = true;
    eventCard.classList.remove("event-card--first-finish");
    importantEventVisibleUntil = 0;
  }, displayDuration);
}

function triggerFirstFinisherCelebration(): void {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  countdown.classList.add("is-finish-clock-pulse");
  const clearPulse = (): void => {
    countdown.classList.remove("is-finish-clock-pulse");
  };
  if (reducedMotion) {
    window.setTimeout(clearPulse, 450);
  } else {
    countdown.addEventListener("animationend", clearPulse, { once: true });
  }

  grandstand.classList.add("grandstand--celebrating");
  window.setTimeout(
    () => grandstand.classList.remove("grandstand--celebrating"),
    reducedMotion ? 900 : 2_600,
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
    case "upgrades.updated":
    case "bailout.updated":
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
      renderGrandstandFromState();
      break;
    case "presence.join":
      connectedSpectators.set(message.spectator.player_id, message.spectator);
      renderGrandstandFromState();
      break;
    case "presence.leave":
      connectedSpectators.delete(message.player_id);
      renderGrandstandFromState();
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

game.events.on(RACE_EVENT_SOUND_EVENT, (event: RaceEvent) => {
  playEventSound(event);
});

game.events.on(FIRST_FINISHER_EVENT, () => {
  triggerFirstFinisherCelebration();
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
liveClock.start();
