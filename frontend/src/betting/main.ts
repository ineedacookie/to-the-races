import {
  ApiError,
  claimSeat,
  discardItem,
  fetchState,
  identifyPlayer,
  loginPlayer,
  purchaseItem,
  submitBet,
  suggestNickname,
  useItem,
} from "../shared/api";
import {
  activeCountdownSeconds,
  dnfLabel,
  formatMoney,
  formatOdds,
  ordinal,
  secondsRemaining,
} from "../shared/format";
import { potionArtPath } from "../shared/itemArt";
import { LiveSocket, type ConnectionStatus } from "../shared/socket";
import {
  assertNever,
  isTonicKind,
  type AudienceReactionKind,
  type InventoryItem,
  type ItemDefinition,
  type ItemKind,
  type ItemUse,
  type LeaderboardRow,
  type LivePlayer,
  type LiveState,
  type RacerEntry,
  type SeatClaim,
  type SeatDefinition,
  type ServerMessage,
} from "../shared/types";
import { createAvatarBuilder } from "./avatarBuilder";

function required<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (element === null) {
    throw new Error(`Missing required element: ${selector}`);
  }
  return element;
}

const identityPanel = required<HTMLElement>("#identity-panel");
const identityForm = required<HTMLFormElement>("#identity-form");
const identityModeSelector = required<HTMLElement>("#identity-mode");
const identityModeSignup = required<HTMLButtonElement>("#identity-mode-signup");
const identityModeLogin = required<HTMLButtonElement>("#identity-mode-login");
const identityTitle = required<HTMLElement>("#identity-title");
const identityCopy = required<HTMLElement>("#identity-copy");
const nicknameInput = required<HTMLInputElement>("#nickname");
const nicknameLabel = required<HTMLLabelElement>("#nickname-label");
const randomNameButton = required<HTMLButtonElement>("#random-name");
const randomAvatarButton = required<HTMLButtonElement>("#random-avatar");
const identityCancel = required<HTMLButtonElement>("#identity-cancel");
const identitySubmit = required<HTMLButtonElement>("#identity-submit");
const avatarBuilderRoot = required<HTMLElement>("#avatar-builder");
const avatarBuilder = createAvatarBuilder(avatarBuilderRoot);
const identityToast = required<HTMLElement>("#identity-toast");
const bettingHeader = required<HTMLElement>(".betting-header");
const bettingMain = required<HTMLElement>("main");
const gamePanel = required<HTMLElement>("#betting-panel");
const accountToolbar = required<HTMLElement>("#account-toolbar");
const playerName = required<HTMLElement>("#player-name");
const balance = required<HTMLElement>("#balance");
const roundLabel = required<HTMLElement>("#round-label");
const phaseLabel = required<HTMLElement>("#phase-label");
const clockLabel = required<HTMLElement>("#clock-label");
const countdown = required<HTMLElement>("#countdown");
const gameMenuButton = required<HTMLButtonElement>("#game-menu-button");
const gameMenuCount = required<HTMLElement>("#game-menu-count");
const gameMenuBackdrop = required<HTMLElement>("#game-menu-backdrop");
const gameMenu = required<HTMLElement>("#game-menu");
const gameMenuClose = required<HTMLButtonElement>("#game-menu-close");
const menuTabs = Array.from(
  document.querySelectorAll<HTMLButtonElement>("[data-menu-panel]"),
);
const menuPanels = Array.from(
  document.querySelectorAll<HTMLElement>("[data-menu-content]"),
);
const racerGrid = required<HTMLElement>("#racer-grid");
const betsList = required<HTMLElement>("#bets-list");
const itemCapText = required<HTMLElement>("#item-cap-text");
const itemMarket = required<HTMLElement>("#item-market");
const inventorySummary = required<HTMLElement>("#inventory-summary");
const itemInventoryGrid = required<HTMLElement>("#item-inventory-grid");
const itemTargetStep = required<HTMLElement>("#item-target-step");
const itemTargetCopy = required<HTMLElement>("#item-target-copy");
const itemTargetGrid = required<HTMLElement>("#item-target-grid");
const itemTargetCancel = required<HTMLButtonElement>("#item-target-cancel");
const mySchemesList = required<HTMLElement>("#my-schemes-list");
const seatGrid = required<HTMLElement>("#seat-grid");
const leaderboardList = required<HTMLElement>("#leaderboard-list");
const debtList = required<HTMLElement>("#debt-list");
const ledgerList = required<HTMLElement>("#ledger-list");
const inventorySeat = required<HTMLElement>("#inventory-seat");
const accountName = required<HTMLElement>("#account-name");
const accountAvatar = required<HTMLImageElement>("#account-avatar");
const editIdentityButton = required<HTMLButtonElement>("#edit-identity");
const accountBalance = required<HTMLElement>("#account-balance");
const accountStaked = required<HTMLElement>("#account-staked");
const accountInventory = required<HTMLElement>("#account-inventory");
const resultsPanel = required<HTMLElement>("#results-panel");
const resultsTitle = required<HTMLElement>("#results-title");
const resultsList = required<HTMLElement>("#results-list");
const raceSheet = required<HTMLElement>("#race-sheet");
const lineupOverlay = required<HTMLElement>("#lineup-overlay");
const lineupLockTitle = required<HTMLElement>("#lineup-lock-title");
const lineupLockCopy = required<HTMLElement>("#lineup-lock-copy");
const customStake = required<HTMLInputElement>("#custom-stake");
const toast = required<HTMLElement>("#toast");
const messageFeed = required<HTMLOListElement>("#message-feed");
const messageFeedEmpty = required<HTMLElement>("#message-feed-empty");
const connectionText = required<HTMLElement>("#connection-text");
const crowdBar = required<HTMLElement>("#crowd-bar");
const crowdCheer = required<HTMLButtonElement>("#crowd-cheer");
const crowdBoo = required<HTMLButtonElement>("#crowd-boo");
const crowdCry = required<HTMLButtonElement>("#crowd-cry");
const crowdShout = required<HTMLInputElement>("#crowd-shout");
const crowdShoutSend = required<HTMLButtonElement>("#crowd-shout-send");
let state: LiveState | null = null;
type IdentityMode = "signup" | "login";
let identityMode: IdentityMode = "signup";
let editingIdentity = false;
let selectedStakeCents = 500;
let serverOffsetMs = 0;
let identityToastTimer: number | null = null;
let refreshGeneration = 0;
let renderedRoundId: number | null = null;
let notifiedResultRoundId: number | null = null;
const pendingEntries = new Set<number>();
const pendingPurchases = new Set<string>();
const pendingItemUses = new Set<number>();
const pendingDiscards = new Set<number>();
const pendingSeats = new Set<string>();
let targetingInventoryItemId: number | null = null;
let menuReturnFocus: HTMLElement | null = null;
const REACTION_SUBMISSION_COOLDOWN_MS = 3_000;
let reactionCooldownUntil = 0;
let reactionCooldownTimer: number | null = null;

type NoticeTone = "good" | "bad" | "neutral";

function updateReactionControls(): void {
  const remainingMs = Math.max(reactionCooldownUntil - Date.now(), 0);
  const coolingDown = remainingMs > 0;
  crowdCheer.disabled = coolingDown;
  crowdBoo.disabled = coolingDown;
  crowdCry.disabled = coolingDown;
  crowdShoutSend.disabled = coolingDown;
  crowdBar.classList.toggle("is-cooling-down", coolingDown);
  const title = coolingDown
    ? `Ready in ${Math.max(Math.ceil(remainingMs / 1_000), 1)} seconds`
    : "";
  crowdCheer.title = title;
  crowdBoo.title = title;
  crowdCry.title = title;
  crowdShoutSend.title = title;
  if (reactionCooldownTimer !== null) {
    window.clearTimeout(reactionCooldownTimer);
    reactionCooldownTimer = null;
  }
  if (coolingDown) {
    reactionCooldownTimer = window.setTimeout(
      updateReactionControls,
      remainingMs + 25,
    );
  }
}

function startReactionCooldown(): void {
  reactionCooldownUntil = Date.now() + REACTION_SUBMISSION_COOLDOWN_MS;
  updateReactionControls();
}

function appendTrackNotice(
  message: string,
  tone: NoticeTone,
  author?: string,
): void {
  messageFeedEmpty.hidden = true;
  const item = document.createElement("li");
  item.dataset.tone = tone;
  const marker = document.createElement("span");
  marker.setAttribute("aria-hidden", "true");
  marker.textContent = tone === "good" ? "✓" : tone === "bad" ? "!" : "•";
  const copy = document.createElement("span");
  copy.className = "message-feed__copy";
  if (author === undefined) {
    copy.textContent = message;
  } else {
    item.classList.add("message-feed__reaction");
    const name = document.createElement("strong");
    name.className = "message-feed__author";
    name.textContent = author;
    const reaction = document.createElement("span");
    reaction.className = "message-feed__message";
    reaction.textContent = message;
    copy.append(name, reaction);
  }
  item.append(marker, copy);
  messageFeed.prepend(item);

  const notices = Array.from(messageFeed.querySelectorAll<HTMLLIElement>("li:not(#message-feed-empty)"));
  for (const staleNotice of notices.slice(8)) {
    staleNotice.remove();
  }
}

function showToast(
  message: string,
  tone: NoticeTone = "neutral",
  author?: string,
): void {
  if (gamePanel.hidden) {
    identityToast.textContent = message;
    identityToast.dataset.tone = tone;
    identityToast.hidden = false;
    if (identityToastTimer !== null) {
      window.clearTimeout(identityToastTimer);
    }
    identityToastTimer = window.setTimeout(() => {
      identityToast.hidden = true;
    }, 4_500);
    return;
  }

  toast.replaceChildren();
  if (author === undefined) {
    toast.textContent = message;
  } else {
    const name = document.createElement("strong");
    name.className = "toast__author";
    name.textContent = author;
    const reaction = document.createElement("span");
    reaction.className = "toast__message";
    reaction.textContent = message;
    toast.append(name, reaction);
  }
  toast.dataset.tone = tone;
  toast.hidden = false;
  appendTrackNotice(message, tone, author);
}

function setConnection(status: ConnectionStatus): void {
  connectionText.dataset.status = status;
  switch (status) {
    case "connecting":
      connectionText.textContent = "Connecting…";
      break;
    case "connected":
      connectionText.textContent = "Live";
      break;
    case "disconnected":
      connectionText.textContent = "Reconnecting…";
      break;
    default:
      assertNever(status);
  }
}

function selectMenuPanel(panelName: string): void {
  for (const tab of menuTabs) {
    const selected = tab.dataset.menuPanel === panelName;
    tab.classList.toggle("is-selected", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
  }
  for (const panel of menuPanels) {
    panel.hidden = panel.dataset.menuContent !== panelName;
  }
}

function openGameMenu(panelName = "shop"): void {
  menuReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  selectMenuPanel(panelName);
  gameMenuBackdrop.hidden = false;
  gameMenuButton.setAttribute("aria-expanded", "true");
  document.body.classList.add("game-menu-open");
  bettingHeader.inert = true;
  bettingMain.inert = true;
  gameMenuClose.focus();
}

function closeGameMenu(): void {
  if (gameMenuBackdrop.hidden) {
    return;
  }
  gameMenuBackdrop.hidden = true;
  gameMenuButton.setAttribute("aria-expanded", "false");
  document.body.classList.remove("game-menu-open");
  bettingHeader.inert = false;
  bettingMain.inert = false;
  menuReturnFocus?.focus();
  menuReturnFocus = null;
}

function trapGameMenuFocus(event: KeyboardEvent): void {
  const focusable = Array.from(
    gameMenu.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((element) => !element.hidden && element.offsetParent !== null);
  const first = focusable[0];
  const last = focusable.at(-1);
  if (first === undefined || last === undefined) {
    return;
  }
  if (event.shiftKey && (document.activeElement === first || !gameMenu.contains(document.activeElement))) {
    event.preventDefault();
    last.focus();
  } else if (
    !event.shiftKey &&
    (document.activeElement === last || !gameMenu.contains(document.activeElement))
  ) {
    event.preventDefault();
    first.focus();
  }
}

function renderIdentity(player: LivePlayer | null): void {
  const identified = player !== null;
  const showingEditor = !identified || editingIdentity;
  const loggingIn = !identified && !editingIdentity && identityMode === "login";
  identityPanel.hidden = !showingEditor;
  identityPanel.classList.toggle("identity-card--login", loggingIn);
  gamePanel.hidden = showingEditor;
  accountToolbar.hidden = showingEditor;
  gameMenuButton.hidden = showingEditor;
  identityModeSelector.hidden = editingIdentity;
  identityModeSignup.setAttribute("aria-pressed", String(!loggingIn));
  identityModeLogin.setAttribute("aria-pressed", String(loggingIn));
  avatarBuilderRoot.hidden = loggingIn;
  randomNameButton.hidden = loggingIn;
  nicknameInput.required = loggingIn;
  nicknameLabel.textContent = loggingIn ? "Existing username" : "Nickname";
  identityTitle.textContent = editingIdentity
    ? "Change your trackside identity"
    : loggingIn
      ? "Welcome back, troublemaker"
      : "What should the bookie call you?";
  identityCopy.textContent = editingIdentity
    ? "Update your username or wardrobe. Every device logged into this account will share the change."
    : loggingIn
      ? "Enter an existing username to reclaim its balance, inventory, bets, and bleacher character. No password required."
      : "Pick a nickname and build your bleacher self. This device will remember both next time. No password, no real money, no sensible financial decisions.";
  identityForm.classList.toggle("identity-form--editing", editingIdentity);
  identityCancel.hidden = !editingIdentity;
  identitySubmit.textContent = editingIdentity
    ? "Save name & look"
    : loggingIn
      ? "Log in"
      : "Get my sheet";
  if (player === null) {
    closeGameMenu();
    return;
  }
  if (!editingIdentity) {
    identityToast.hidden = true;
  }
  playerName.textContent = player.nickname;
  balance.textContent = formatMoney(player.balance_cents);
  balance.classList.toggle("is-negative", player.balance_cents < 0);
}

function phaseCopy(roundState: LiveState["round"]): string {
  if (roundState === null) {
    return "Warming up";
  }
  switch (roundState.state) {
    case "open":
      return "Betting open";
    case "locked":
      return "Bets locked";
    case "racing":
      return "They're off!";
    case "results":
      return "Official result";
    default:
      return assertNever(roundState.state);
  }
}

function lockedLineupMessage(currentState: LiveState): { title: string; copy: string } {
  if (currentState.room.is_paused) {
    return {
      title: "Bookie pause",
      copy: "The lineup is frozen while race night is paused.",
    };
  }
  const round = currentState.round;
  if (round === null) {
    return {
      title: "Lineup incoming",
      copy: "Officials are assembling the next group of little menaces.",
    };
  }
  switch (round.state) {
    case "open":
      return {
        title: "Market closing",
        copy: "The last betting slips are being collected.",
      };
    case "locked":
      return {
        title: "Pencils down",
        copy: "Bets are locked. Public schemes are being staged.",
      };
    case "racing":
      return {
        title: "Race in progress",
        copy: "Betting is closed. Shout from the trackside wire instead.",
      };
    case "results":
      return {
        title: "Official call posted",
        copy: "The result is on the trackside wire. A fresh market opens soon.",
      };
    default:
      return assertNever(round.state);
  }
}

function updateClock(): void {
  clockLabel.textContent = "Clock";
  countdown.classList.remove("is-finish-clock");
  if (state?.round === null || state?.round === undefined) {
    countdown.textContent = "—";
    return;
  }
  const round = state.round;
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
      countdown.textContent = `${finishClock}s`;
      return;
    }
    case "results":
      deadline = round.results_end_at;
      break;
    default:
      assertNever(round.state);
  }
  countdown.textContent = `${secondsRemaining(deadline, serverOffsetMs)}s`;
}

function selectedBetFor(entry: RacerEntry, player: LivePlayer): number {
  return player.bets
    .filter((bet) => bet.racer_id === entry.racer_id)
    .reduce((total, bet) => total + bet.amount_cents, 0);
}

function trackPositionLabel(position: number): string {
  if (position < 0.42) {
    return "Start";
  }
  if (position < 0.68) {
    return "Middle";
  }
  return "Final";
}

function trackLaneLabel(lane: number): string {
  const racerCount = state?.round?.entries.length ?? 4;
  return `Lane ${Math.max(Math.round(lane * (racerCount + 1)), 1)}`;
}

function racerDetailHref(entry: RacerEntry): string {
  return `/racers/${encodeURIComponent(entry.slug)}/`;
}

function makeRacerCard(entry: RacerEntry, player: LivePlayer, bettingOpen: boolean): HTMLElement {
  const card = document.createElement("article");
  card.className = "racer-card";
  card.style.setProperty("--racer-color", entry.color);

  const heading = document.createElement("div");
  heading.className = "racer-card__heading";

  const portrait = document.createElement("img");
  portrait.className = "racer-portrait";
  portrait.src = `/static/assets/racers/portraits/${entry.sprite_key}.png`;
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
  const playerStake = selectedBetFor(entry, player);
  yours.textContent = playerStake > 0 ? `You: ${formatMoney(playerStake)}` : "No bet yet";
  meta.append(crowd, yours);

  const button = document.createElement("button");
  button.className = "bet-button";
  button.type = "button";
  button.textContent = pendingEntries.has(entry.id)
    ? "Placing…"
    : `Bet ${formatMoney(selectedStakeCents)}`;
  button.disabled =
    !bettingOpen || pendingEntries.has(entry.id) || selectedStakeCents < 100;
  button.addEventListener("click", () => {
    void placeBet(entry);
  });

  card.append(heading, dossierLink, meta, button);
  return card;
}

function renderBoardRow(row: LeaderboardRow): HTMLElement {
  const item = document.createElement("li");
  const rank = document.createElement("span");
  rank.className = "board-rank";
  rank.textContent = `#${row.rank}`;
  const name = document.createElement("strong");
  name.textContent = row.nickname;
  const stats = document.createElement("span");
  stats.className = "board-stats";
  stats.textContent = `${formatMoney(row.balance_cents)} · ${row.wins} wins · ${row.total_bets} bets`;
  item.append(rank, name, stats);
  return item;
}

function renderBoards(currentState: LiveState): void {
  leaderboardList.replaceChildren();
  debtList.replaceChildren();
  const leaders = currentState.leaderboard ?? [];
  const debtors = currentState.debt_board ?? [];
  if (leaders.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "Nobody on the board yet.";
    leaderboardList.append(empty);
  } else {
    for (const row of leaders) {
      leaderboardList.append(renderBoardRow(row));
    }
  }
  if (debtors.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No debtors—suspicious.";
    debtList.append(empty);
  } else {
    for (const row of debtors) {
      debtList.append(renderBoardRow(row));
    }
  }
}

type ItemShopSection = "positive" | "negative" | "neutral" | "live";

const ITEM_SHOP_SECTIONS: ReadonlyArray<{
  key: ItemShopSection;
  title: string;
  copy: string;
}> = [
  {
    key: "positive",
    title: "Positive potions",
    copy: "Buffs. Assign during betting; racers drink them at the next start.",
  },
  {
    key: "negative",
    title: "Negative potions",
    copy: "Debuffs. Assign during betting; resilience and Guard can resist them.",
  },
  {
    key: "neutral",
    title: "Neutral potions",
    copy: "Tradeoffs and identity chaos. Strong upside always comes with a catch.",
  },
  {
    key: "live",
    title: "Live race items",
    copy: "Use only while racers are moving. Choose a portrait to place it ahead.",
  },
];

function itemShopSection(kind: ItemKind): ItemShopSection {
  switch (kind) {
    case "speed_tonic":
    case "guard_tonic":
      return "positive";
    case "trip_tonic":
    case "confusion_tonic":
      return "negative";
    case "growth_tonic":
    case "shrink_tonic":
    case "transform_tonic":
      return "neutral";
    case "banana":
    case "pothole":
    case "oil_slick":
    case "boost_pad":
    case "boxing_glove":
      return "live";
    default:
      return assertNever(kind);
  }
}

function canPurchaseItem(player: LivePlayer, item: ItemDefinition): boolean {
  if (pendingPurchases.has(item.slug)) {
    return false;
  }
  const room = state?.room;
  if (room === undefined) {
    return false;
  }
  return (
    item.price_cents <= player.balance_cents &&
    player.inventory.length < room.max_inventory_items
  );
}

function makeItemIcon(kind: ItemKind, fallback: string): HTMLElement {
  const icon = document.createElement("span");
  icon.className = "item-icon";
  icon.setAttribute("aria-hidden", "true");
  const artPath = potionArtPath(kind);
  if (artPath === null) {
    icon.textContent = fallback;
    return icon;
  }

  icon.classList.add("item-icon--potion");
  const image = document.createElement("img");
  image.src = artPath;
  image.alt = "";
  image.width = 48;
  image.height = 48;
  icon.append(image);
  return icon;
}

function makeItemCard(
  item: ItemDefinition,
  player: LivePlayer,
): HTMLElement {
  const card = document.createElement("article");
  card.className = "item-card";
  card.style.setProperty("--item-color", item.color);

  const header = document.createElement("div");
  header.className = "item-card__header";
  const icon = makeItemIcon(item.kind, item.icon);
  const titleWrap = document.createElement("div");
  const timing = document.createElement("span");
  timing.className = "item-card__timing";
  timing.textContent = isTonicKind(item.kind) ? "Next start" : "Use live";
  const title = document.createElement("h3");
  title.textContent = item.name;
  const desc = document.createElement("p");
  desc.textContent = item.description;
  titleWrap.append(timing, title, desc);
  const price = document.createElement("strong");
  price.className = "item-price";
  price.textContent = formatMoney(item.price_cents);
  header.append(icon, titleWrap, price);
  card.append(header);

  const targetHint = document.createElement("p");
  targetHint.className = "item-card__target-hint";
  targetHint.textContent =
    isTonicKind(item.kind)
      ? "Assign during betting. It triggers when the water is served at race start."
      : "Activate during the race. It appears ahead in the selected racer's path.";
  card.append(targetHint);

  const buyButton = document.createElement("button");
  buyButton.type = "button";
  buyButton.className = "item-buy-btn";
  buyButton.textContent = pendingPurchases.has(item.slug)
    ? "Buying…"
    : player.inventory.length >= (state?.room.max_inventory_items ?? 4)
      ? "Bag full"
    : item.price_cents > player.balance_cents
      ? `Need ${formatMoney(item.price_cents)}`
      : "Buy";
  buyButton.disabled = !canPurchaseItem(player, item);
  buyButton.setAttribute(
    "aria-label",
    `Buy ${item.name} for ${formatMoney(item.price_cents)}`,
  );
  buyButton.addEventListener("click", () => {
    void buyItem(item);
  });
  card.append(buyButton);
  return card;
}

function renderItemMarket(player: LivePlayer): void {
  itemMarket.replaceChildren();
  const catalog = state?.room.item_catalog ?? [];
  if (catalog.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "The black market is closed—no schemes listed.";
    itemMarket.append(empty);
    return;
  }
  for (const section of ITEM_SHOP_SECTIONS) {
    const sectionItems = catalog.filter(
      (item) => itemShopSection(item.kind) === section.key,
    );
    if (sectionItems.length === 0) {
      continue;
    }
    const group = document.createElement("section");
    group.className = `item-market__section item-market__section--${section.key}`;
    const heading = document.createElement("div");
    heading.className = "item-market__heading";
    const title = document.createElement("h3");
    title.textContent = section.title;
    const copy = document.createElement("p");
    copy.textContent = section.copy;
    heading.append(title, copy);
    const grid = document.createElement("div");
    grid.className = "item-market__grid";
    for (const item of sectionItems) {
      grid.append(makeItemCard(item, player));
    }
    group.append(heading, grid);
    itemMarket.append(group);
  }

  const spent = player.round_item_spent_cents;
  const maxSpend = state?.room.max_round_item_spend_cents ?? 0;
  const uses = player.item_uses.length;
  const maxUses = state?.room.max_round_item_uses ?? 0;
  const maxInventory = state?.room.max_inventory_items ?? 4;
  itemCapText.textContent = `Bag ${player.inventory.length}/${maxInventory} · this round ${uses}/${maxUses} uses · ${formatMoney(spent)}/${formatMoney(maxSpend)}`;

  mySchemesList.replaceChildren();
  if (player.item_uses.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No schemes deployed yet.";
    mySchemesList.append(empty);
  } else {
    for (const use of player.item_uses) {
      mySchemesList.append(renderItemUse(use));
    }
  }
}

function canUseInventoryItem(
  player: LivePlayer,
  inventoryItem: InventoryItem,
  potionWindowOpen: boolean,
): boolean {
  const room = state?.room;
  const useWindowOpen = isTonicKind(inventoryItem.kind)
    ? potionWindowOpen
    : state?.round?.state === "racing";
  if (
    !useWindowOpen ||
    room === undefined ||
    pendingItemUses.has(inventoryItem.id) ||
    pendingDiscards.has(inventoryItem.id)
  ) {
    return false;
  }
  return (
    player.item_uses.length < room.max_round_item_uses &&
    player.round_item_spent_cents + inventoryItem.price_paid_cents <=
      room.max_round_item_spend_cents
  );
}

function inventoryUseLabel(
  player: LivePlayer,
  inventoryItem: InventoryItem,
  potionWindowOpen: boolean,
): string {
  const room = state?.room;
  if (pendingItemUses.has(inventoryItem.id)) {
    return "Using…";
  }
  if (isTonicKind(inventoryItem.kind) && !potionWindowOpen) {
    return "Use during betting";
  }
  if (!isTonicKind(inventoryItem.kind) && state?.round?.state !== "racing") {
    return "Use during race";
  }
  if (player.item_uses.length >= (room?.max_round_item_uses ?? 0)) {
    return "Use limit reached";
  }
  if (
    player.round_item_spent_cents + inventoryItem.price_paid_cents >
    (room?.max_round_item_spend_cents ?? 0)
  ) {
    return "Use budget reached";
  }
  return "Use";
}

function renderInventory(
  player: LivePlayer,
  entries: RacerEntry[],
  potionWindowOpen: boolean,
): void {
  const maxInventory = state?.room.max_inventory_items ?? 4;
  const targetItem =
    player.inventory.find((item) => item.id === targetingInventoryItemId) ?? null;
  if (targetItem === null) {
    targetingInventoryItemId = null;
  }

  inventorySummary.textContent = `${player.inventory.length} / ${maxInventory} items`;
  itemInventoryGrid.replaceChildren();
  for (const inventoryItem of player.inventory) {
    const card = document.createElement("article");
    card.className = "inventory-item-card";
    card.dataset.inventoryId = String(inventoryItem.id);
    card.style.setProperty("--item-color", inventoryItem.item_color);
    card.setAttribute("role", "listitem");
    card.classList.toggle("is-targeting", inventoryItem.id === targetingInventoryItemId);

    const trashButton = document.createElement("button");
    trashButton.type = "button";
    trashButton.className = "inventory-item-trash-button";
    trashButton.textContent = "🗑";
    trashButton.title = `Throw away ${inventoryItem.item_name} — no refund`;
    trashButton.setAttribute("aria-label", `Throw away ${inventoryItem.item_name}`);
    trashButton.disabled =
      pendingDiscards.has(inventoryItem.id) || pendingItemUses.has(inventoryItem.id);
    trashButton.addEventListener("click", () => {
      void trashInventoryItem(inventoryItem);
    });

    const details = document.createElement("div");
    details.className = "inventory-item-card__details";
    const icon = makeItemIcon(inventoryItem.kind, inventoryItem.item_icon);
    const name = document.createElement("strong");
    name.textContent = inventoryItem.item_name;
    const price = document.createElement("span");
    price.textContent = formatMoney(inventoryItem.price_paid_cents);
    details.append(icon, name, price);

    const useButton = document.createElement("button");
    useButton.type = "button";
    useButton.className = "inventory-item-use-button";
    useButton.textContent = inventoryUseLabel(player, inventoryItem, potionWindowOpen);
    useButton.disabled = !canUseInventoryItem(
      player,
      inventoryItem,
      potionWindowOpen,
    );
    useButton.setAttribute("aria-label", `Use ${inventoryItem.item_name}`);
    useButton.addEventListener("click", () => {
      targetingInventoryItemId = inventoryItem.id;
      if (state !== null) {
        render(state);
        window.requestAnimationFrame(() => {
          itemTargetGrid.querySelector<HTMLButtonElement>("button")?.focus();
        });
      }
    });

    card.append(trashButton, details, useButton);
    itemInventoryGrid.append(card);
  }
  for (let slot = player.inventory.length; slot < maxInventory; slot += 1) {
    const empty = document.createElement("div");
    empty.className = "inventory-item-card inventory-item-card--empty";
    empty.setAttribute("aria-hidden", "true");
    empty.textContent = "Empty slot";
    itemInventoryGrid.append(empty);
  }

  itemTargetStep.hidden = targetItem === null;
  itemTargetGrid.replaceChildren();
  if (targetItem !== null) {
    itemTargetCopy.textContent =
      isTonicKind(targetItem.kind)
        ? `Choose who drinks ${targetItem.item_name} at the next race start.`
        : `Choose whose path receives ${targetItem.item_name} right now.`;
    for (const entry of entries) {
      const targetButton = document.createElement("button");
      targetButton.type = "button";
      targetButton.className = "item-target-portrait";
      targetButton.disabled = pendingItemUses.has(targetItem.id);
      targetButton.setAttribute(
        "aria-label",
        `Use ${targetItem.item_name} on ${entry.name}`,
      );
      const portrait = document.createElement("img");
      portrait.src = `/static/assets/racers/portraits/${entry.sprite_key}.png`;
      portrait.alt = "";
      portrait.width = 72;
      portrait.height = 72;
      const name = document.createElement("strong");
      name.textContent = entry.name;
      targetButton.append(portrait, name);
      targetButton.addEventListener("click", () => {
        void deployInventoryItem(targetItem, entry);
      });
      itemTargetGrid.append(targetButton);
    }
  }
}

function renderItemUse(use: ItemUse): HTMLElement {
  const item = document.createElement("li");
  item.style.setProperty("--item-color", use.item_color);
  const icon = makeItemIcon(use.kind, use.item_icon);
  const label = document.createElement("span");
  if (use.target_racer_name) {
    label.textContent = `${use.item_name} → ${use.target_racer_name}`;
  } else if (use.track_lane !== null && use.track_position !== null) {
    label.textContent = `${use.item_name} → ${trackLaneLabel(use.track_lane)}, ${trackPositionLabel(use.track_position)}`;
  } else {
    label.textContent = use.item_name;
  }
  item.append(icon, label);
  return item;
}

function makeSeatCard(
  seat: SeatDefinition,
  claim: SeatClaim | undefined,
  player: LivePlayer,
  marketOpen: boolean,
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
  mascot.src = `/static/assets/racers/portraits/${seat.sprite_key}.png`;
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
  const claimed = claim !== undefined;
  owner.textContent = claimed
    ? `Held by ${claim.nickname}`
    : `${formatMoney(seat.price_cents)} · unclaimed`;

  const claimBtn = document.createElement("button");
  claimBtn.type = "button";
  claimBtn.className = "seat-claim-btn";
  const alreadyOwns = player.seat_claim?.seat_slug === seat.slug;
  const canAfford = player.balance_cents >= seat.price_cents;
  claimBtn.textContent = pendingSeats.has(seat.slug)
    ? "Claiming…"
    : claimed
      ? "Taken"
      : !canAfford
        ? `Need ${formatMoney(seat.price_cents)}`
        : `Claim · ${formatMoney(seat.price_cents)}`;
  claimBtn.disabled =
    !marketOpen ||
    claimed ||
    alreadyOwns ||
    player.seat_claim !== null ||
    !canAfford ||
    pendingSeats.has(seat.slug);
  claimBtn.setAttribute("aria-label", `Claim ${seat.name}`);
  claimBtn.addEventListener("click", () => {
    void buySeat(seat);
  });

  card.append(crown, mascot, title, perk, desc, owner, claimBtn);
  return card;
}

function renderSeatMarket(player: LivePlayer, marketOpen: boolean): void {
  seatGrid.replaceChildren();
  const catalog = state?.room.seat_catalog ?? [];
  const claims = state?.round?.seats ?? [];
  if (catalog.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "Grandstand seats will appear when the round opens.";
    seatGrid.append(empty);
    return;
  }
  for (const seat of catalog) {
    const claim = claims.find((candidate) => candidate.seat_slug === seat.slug);
    seatGrid.append(makeSeatCard(seat, claim, player, marketOpen));
  }
}

function renderLedger(player: LivePlayer): void {
  ledgerList.replaceChildren();
  const rows = player.recent_ledger ?? [];
  if (rows.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No ledger entries yet.";
    ledgerList.append(empty);
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
    ledgerList.append(item);
  }
}

function renderAccountAndInventory(player: LivePlayer): void {
  accountName.textContent = player.nickname;
  accountAvatar.src = player.avatar_url;
  accountAvatar.alt = `${player.nickname}'s bleacher character`;
  accountBalance.textContent = formatMoney(player.balance_cents);
  accountBalance.classList.toggle("is-negative", player.balance_cents < 0);
  accountStaked.textContent = formatMoney(player.round_staked_cents);
  const inventoryCount =
    player.inventory.length +
    player.item_uses.length +
    (player.seat_claim === null ? 0 : 1);
  accountInventory.textContent = `${player.inventory.length} in bag · ${
    player.item_uses.length
  } used${player.seat_claim === null ? "" : " · 1 seat"}`;
  inventorySeat.textContent =
    player.seat_claim === null
      ? "No prestige seat claimed."
      : `Seat: ${player.seat_claim.seat_name} · +${
          player.seat_claim.payout_bonus_bps / 100
        }% winning profit`;
  gameMenuCount.textContent = String(player.bets.length + inventoryCount);
}

function renderBets(player: LivePlayer): void {
  betsList.replaceChildren();
  if (player.bets.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-state";
    empty.textContent = "No tickets this round—yet.";
    betsList.append(empty);
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
    betsList.append(item);
  }
}

function renderResults(currentState: LiveState): void {
  const round = currentState.round;
  const show = round?.state === "results";
  resultsPanel.hidden = !show;
  resultsList.replaceChildren();
  if (!show || round === null) {
    return;
  }

  const finishers = [...round.entries]
    .filter((entry) => entry.finish_place !== null)
    .sort((first, second) => (first.finish_place ?? 99) - (second.finish_place ?? 99));
  if (finishers.length === 0) {
    resultsTitle.textContent = "Total chaos. The house wins.";
  } else {
    resultsTitle.textContent = `${finishers[0]?.name ?? "Unknown"} wins!`;
  }
  for (const entry of [...finishers, ...round.entries.filter((item) => item.finish_place === null)]) {
    const item = document.createElement("li");
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
  if (notifiedResultRoundId !== round.id) {
    notifiedResultRoundId = round.id;
    showToast(`Official: ${resultsTitle.textContent ?? "result posted"}`, "good");
  }
}

function render(currentState: LiveState): void {
  const nextRoundId = currentState.round?.id ?? null;
  if (renderedRoundId !== null && nextRoundId !== renderedRoundId) {
    targetingInventoryItemId = null;
  }
  renderedRoundId = nextRoundId;
  state = currentState;
  document.body.dataset.roundState = currentState.round?.state ?? "waiting";
  serverOffsetMs = Date.parse(currentState.server_time) - Date.now();
  renderIdentity(currentState.player);
  phaseLabel.textContent = currentState.room.is_paused
    ? "Race night paused"
    : phaseCopy(currentState.round);
  roundLabel.textContent = currentState.round ? `Round ${currentState.round.number}` : "Next round";
  updateClock();
  renderBoards(currentState);

  if (currentState.player === null) {
    return;
  }

  const player = currentState.player;
  renderAccountAndInventory(player);
  const entries = currentState.round?.entries ?? [];
  crowdBar.hidden = false;
  document.body.classList.remove("crowd-active");

  racerGrid.replaceChildren();
  const marketOpen =
    currentState.round?.state === "open" &&
    !currentState.room.is_paused &&
    secondsRemaining(currentState.round.locks_at, serverOffsetMs) > 0;
  const bettingOpen = marketOpen;
  const lineupLocked = currentState.round !== null && !bettingOpen;
  const lockMessage = lockedLineupMessage(currentState);
  raceSheet.classList.toggle("is-locked", lineupLocked);
  raceSheet.setAttribute("aria-disabled", String(lineupLocked));
  racerGrid.inert = lineupLocked;
  lineupOverlay.hidden = !lineupLocked;
  lineupLockTitle.textContent = lockMessage.title;
  lineupLockCopy.textContent = lockMessage.copy;
  for (const entry of entries) {
    racerGrid.append(makeRacerCard(entry, player, bettingOpen));
  }
  renderItemMarket(player);
  renderInventory(player, entries, marketOpen);
  renderSeatMarket(player, marketOpen);
  renderLedger(player);
  renderBets(player);
  renderResults(currentState);
}

async function refresh(): Promise<void> {
  const generation = ++refreshGeneration;
  try {
    const nextState = await fetchState();
    if (generation === refreshGeneration) {
      render(nextState);
    }
  } catch (error: unknown) {
    if (generation === refreshGeneration) {
      showToast(error instanceof Error ? error.message : "Could not refresh the race.", "bad");
    }
  }
}

async function placeBet(entry: RacerEntry): Promise<void> {
  if (pendingEntries.has(entry.id) || selectedStakeCents < 100) {
    customStake.focus();
    return;
  }
  pendingEntries.add(entry.id);
  if (state !== null) {
    render(state);
  }
  try {
    const receipt = await submitBet(entry.id, selectedStakeCents);
    showToast(
      `${formatMoney(receipt.bet.amount_cents)} on ${receipt.bet.racer_name}. Good luck!`,
      "good",
    );
    await refresh();
  } catch (error: unknown) {
    showToast(error instanceof ApiError ? error.message : "That bet did not go through.", "bad");
  } finally {
    pendingEntries.delete(entry.id);
    if (state !== null) {
      render(state);
    }
  }
}

async function buyItem(item: ItemDefinition): Promise<void> {
  if (pendingPurchases.has(item.slug)) {
    return;
  }
  pendingPurchases.add(item.slug);
  if (state !== null) {
    render(state);
  }
  try {
    const receipt = await purchaseItem(item.slug);
    showToast(
      `${item.name} is in your bag. ${formatMoney(receipt.balance_cents)} left.`,
      "good",
    );
    await refresh();
  } catch (error: unknown) {
    showToast(error instanceof ApiError ? error.message : "Purchase failed.", "bad");
  } finally {
    pendingPurchases.delete(item.slug);
    if (state !== null) {
      render(state);
    }
  }
}

async function deployInventoryItem(
  inventoryItem: InventoryItem,
  entry: RacerEntry,
): Promise<void> {
  if (
    pendingItemUses.has(inventoryItem.id) ||
    state?.round === null ||
    state?.round === undefined
  ) {
    return;
  }
  const roundId = state.round.id;
  pendingItemUses.add(inventoryItem.id);
  render(state);
  try {
    await useItem(roundId, inventoryItem.id, entry.id);
    targetingInventoryItemId = null;
    showToast(
      isTonicKind(inventoryItem.kind)
        ? `${entry.name} will drink ${inventoryItem.item_name} at the next start.`
        : `${inventoryItem.item_name} is live in ${entry.name}'s path!`,
      "good",
    );
    await refresh();
  } catch (error: unknown) {
    showToast(error instanceof ApiError ? error.message : "Item use failed.", "bad");
  } finally {
    pendingItemUses.delete(inventoryItem.id);
    if (state !== null) {
      render(state);
    }
  }
}

async function trashInventoryItem(inventoryItem: InventoryItem): Promise<void> {
  if (
    pendingDiscards.has(inventoryItem.id) ||
    pendingItemUses.has(inventoryItem.id) ||
    !window.confirm(
      `Throw away ${inventoryItem.item_name}? This permanently frees the bag slot and gives no refund.`,
    )
  ) {
    return;
  }
  pendingDiscards.add(inventoryItem.id);
  if (targetingInventoryItemId === inventoryItem.id) {
    targetingInventoryItemId = null;
  }
  if (state !== null) {
    render(state);
  }
  try {
    await discardItem(inventoryItem.id);
    showToast(`${inventoryItem.item_name} was thrown away. No refund.`, "neutral");
    await refresh();
  } catch (error: unknown) {
    showToast(error instanceof ApiError ? error.message : "Could not discard that item.", "bad");
  } finally {
    pendingDiscards.delete(inventoryItem.id);
    if (state !== null) {
      render(state);
    }
  }
}

async function buySeat(seat: SeatDefinition): Promise<void> {
  if (pendingSeats.has(seat.slug) || state?.round === null || state?.round === undefined) {
    return;
  }
  pendingSeats.add(seat.slug);
  if (state !== null) {
    render(state);
  }
  try {
    const receipt = await claimSeat(state.round.id, seat.slug);
    showToast(`You claimed ${receipt.seat_claim.seat_name}!`, "good");
    await refresh();
  } catch (error: unknown) {
    showToast(error instanceof ApiError ? error.message : "Seat claim failed.", "bad");
  } finally {
    pendingSeats.delete(seat.slug);
    if (state !== null) {
      render(state);
    }
  }
}

function mergePlayerState(incoming: LiveState): LiveState {
  const currentPlayer = state?.player ?? incoming.player;
  const roundChanged = state?.round?.id !== incoming.round?.id;
  if (currentPlayer === null || !roundChanged) {
    return { ...incoming, player: currentPlayer };
  }
  return {
    ...incoming,
    player: {
      ...currentPlayer,
      round_staked_cents: 0,
      round_item_spent_cents: 0,
      item_uses: [],
      bets: [],
      seat_claim: null,
    },
  };
}

function defaultReactionMessage(kind: AudienceReactionKind): string {
  switch (kind) {
    case "cheer":
      return "Cheer!";
    case "boo":
      return "Boo!";
    case "cry":
      return "Waaah!";
    case "shout":
      return "Shout!";
    default:
      return assertNever(kind);
  }
}

function handleMessage(message: ServerMessage): void {
  if (
    message.type !== "audience.reaction" &&
    message.type !== "audience.rejected" &&
    message.type !== "presence.sync" &&
    message.type !== "presence.join" &&
    message.type !== "presence.leave" &&
    message.type !== "pong"
  ) {
    refreshGeneration += 1;
  }
  switch (message.type) {
    case "state.sync":
      render(message.state);
      break;
    case "round.opened":
      render(mergePlayerState(message.state));
      void refresh();
      showToast("A fresh betting sheet is open.", "good");
      break;
    case "round.locked":
      render(mergePlayerState(message.state));
      showToast("Pencils down—bets are locked.");
      break;
    case "race.started":
      render(mergePlayerState(message.state));
      showToast("They're off!");
      break;
    case "race.finished":
      render(mergePlayerState(message.state));
      void refresh();
      break;
    case "bets.updated":
    case "items.updated":
    case "seats.updated":
      render(mergePlayerState(message.state));
      void refresh();
      break;
    case "balance.updated":
      if (state?.player !== null && state?.player !== undefined) {
        state.player.balance_cents = message.balance_cents;
        render(state);
      }
      void refresh();
      break;
    case "audience.reaction": {
      const { reaction } = message;
      const target = reaction.text || defaultReactionMessage(reaction.kind);
      showToast(target, "neutral", reaction.nickname);
      break;
    }
    case "audience.rejected":
      showToast(message.message, "bad");
      break;
    case "presence.sync":
    case "presence.join":
    case "presence.leave":
    case "pong":
      break;
    default:
      assertNever(message);
  }
}

identityForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const nickname = nicknameInput.value.trim();
  const wasEditing = editingIdentity;
  const wasLoggingIn = !wasEditing && identityMode === "login";
  void (async () => {
    try {
      if (wasLoggingIn) {
        await loginPlayer(nickname);
      } else {
        await identifyPlayer(nickname || undefined, avatarBuilder.recipe());
      }
      editingIdentity = false;
      socket.reconnect();
      await refresh();
      showToast(
        wasEditing
          ? "Your bleacher character is updated."
          : wasLoggingIn
            ? `Welcome back, ${nickname}.`
            : "Your betting sheet is ready.",
        "good",
      );
    } catch (error: unknown) {
      showToast(
        error instanceof Error ? error.message : "Could not save that identity.",
        "bad",
      );
    }
  })();
});

function selectIdentityMode(mode: IdentityMode): void {
  if (
    editingIdentity ||
    (state?.player !== null && state?.player !== undefined)
  ) {
    return;
  }
  identityMode = mode;
  identityToast.hidden = true;
  renderIdentity(null);
  nicknameInput.focus();
}

identityModeSignup.addEventListener("click", () => {
  selectIdentityMode("signup");
});

identityModeLogin.addEventListener("click", () => {
  selectIdentityMode("login");
});

editIdentityButton.addEventListener("click", () => {
  const player = state?.player;
  if (player === null || player === undefined) {
    return;
  }
  closeGameMenu();
  editingIdentity = true;
  nicknameInput.value = player.nickname;
  avatarBuilder.setRecipe(player.avatar_recipe);
  renderIdentity(player);
  window.scrollTo({ top: 0, behavior: "smooth" });
  window.requestAnimationFrame(() => nicknameInput.focus());
});

identityCancel.addEventListener("click", () => {
  editingIdentity = false;
  renderIdentity(state?.player ?? null);
  gameMenuButton.focus();
});

randomNameButton.addEventListener("click", () => {
  void (async () => {
    try {
      nicknameInput.value = (await suggestNickname()).nickname;
      nicknameInput.focus();
    } catch {
      showToast("The nickname goblins are busy. Try your own!", "bad");
    }
  })();
});

randomAvatarButton.addEventListener("click", () => {
  avatarBuilder.randomize();
});

itemTargetCancel.addEventListener("click", () => {
  const cancelledInventoryItemId = targetingInventoryItemId;
  targetingInventoryItemId = null;
  if (state !== null) {
    render(state);
    window.requestAnimationFrame(() => {
      if (cancelledInventoryItemId !== null) {
        itemInventoryGrid
          .querySelector<HTMLButtonElement>(
            `[data-inventory-id="${cancelledInventoryItemId}"] .inventory-item-use-button`,
          )
          ?.focus();
      }
    });
  }
});

customStake.addEventListener("input", () => {
  const dollars = Number(customStake.value);
  selectedStakeCents =
    Number.isSafeInteger(dollars) && dollars >= 1 ? dollars * 100 : 0;
  if (state !== null) {
    render(state);
  }
});

function sendCrowdReaction(kind: AudienceReactionKind): void {
  if (Date.now() < reactionCooldownUntil) {
    return;
  }
  if (kind === "shout") {
    const text = crowdShout.value.trim();
    if (text.length === 0) {
      showToast("Type a shout first (24 characters max).", "bad");
      return;
    }
    socket.sendReaction("shout", { text });
    crowdShout.value = "";
  } else {
    socket.sendReaction(kind);
  }
  startReactionCooldown();
}

crowdCheer.addEventListener("click", () => {
  sendCrowdReaction("cheer");
});
crowdBoo.addEventListener("click", () => {
  sendCrowdReaction("boo");
});
crowdCry.addEventListener("click", () => {
  sendCrowdReaction("cry");
});
crowdShoutSend.addEventListener("click", () => {
  sendCrowdReaction("shout");
});
crowdShout.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    sendCrowdReaction("shout");
  }
});

gameMenuButton.addEventListener("click", () => {
  openGameMenu();
});
gameMenuClose.addEventListener("click", closeGameMenu);
gameMenuBackdrop.addEventListener("click", (event) => {
  if (event.target === gameMenuBackdrop) {
    closeGameMenu();
  }
});
menuTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    selectMenuPanel(tab.dataset.menuPanel ?? "shop");
  });
  tab.addEventListener("keydown", (event) => {
    const currentIndex = menuTabs.indexOf(tab);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % menuTabs.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + menuTabs.length) % menuTabs.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = menuTabs.length - 1;
    }
    if (nextIndex === null) {
      return;
    }
    event.preventDefault();
    const nextTab = menuTabs[nextIndex];
    if (nextTab !== undefined) {
      selectMenuPanel(nextTab.dataset.menuPanel ?? "shop");
      nextTab.focus();
    }
  });
});
document.addEventListener("keydown", (event) => {
  if (gameMenuBackdrop.hidden) {
    return;
  }
  if (event.key === "Escape") {
    closeGameMenu();
  } else if (event.key === "Tab") {
    trapGameMenuFocus(event);
  }
});

const socket = new LiveSocket({
  role: "bet",
  onMessage: handleMessage,
  onStatus: setConnection,
});
socket.start();
window.setInterval(updateClock, 250);
void refresh();
