import {
  ApiError,
  claimSeat,
  deployItem,
  fetchState,
  identifyPlayer,
  submitBet,
  suggestNickname,
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
import { createClientRequestId } from "../shared/requestId";
import { LiveSocket, type ConnectionStatus } from "../shared/socket";
import {
  assertNever,
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

function required<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (element === null) {
    throw new Error(`Missing required element: ${selector}`);
  }
  return element;
}

const identityPanel = required<HTMLElement>("#identity-panel");
const identityForm = required<HTMLFormElement>("#identity-form");
const nicknameInput = required<HTMLInputElement>("#nickname");
const randomNameButton = required<HTMLButtonElement>("#random-name");
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
const capText = required<HTMLElement>("#cap-text");
const capMeter = required<HTMLProgressElement>("#cap-meter");
const itemCapText = required<HTMLElement>("#item-cap-text");
const itemMarket = required<HTMLElement>("#item-market");
const mySchemesList = required<HTMLElement>("#my-schemes-list");
const seatGrid = required<HTMLElement>("#seat-grid");
const leaderboardList = required<HTMLElement>("#leaderboard-list");
const debtList = required<HTMLElement>("#debt-list");
const ledgerList = required<HTMLElement>("#ledger-list");
const inventorySeat = required<HTMLElement>("#inventory-seat");
const accountName = required<HTMLElement>("#account-name");
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
const customStakeControl = required<HTMLElement>("#custom-stake-control");
const applyCustomStake = required<HTMLButtonElement>("#apply-custom-stake");
const toast = required<HTMLElement>("#toast");
const messageFeed = required<HTMLOListElement>("#message-feed");
const messageFeedEmpty = required<HTMLElement>("#message-feed-empty");
const connectionText = required<HTMLElement>("#connection-text");
const crowdBar = required<HTMLElement>("#crowd-bar");
const crowdCheer = required<HTMLButtonElement>("#crowd-cheer");
const crowdBoo = required<HTMLButtonElement>("#crowd-boo");
const crowdShout = required<HTMLInputElement>("#crowd-shout");
const crowdTarget = required<HTMLSelectElement>("#crowd-target");
const crowdShoutSend = required<HTMLButtonElement>("#crowd-shout-send");
const quickStakeButtons = Array.from(
  document.querySelectorAll<HTMLButtonElement>("[data-stake-cents]"),
);

let state: LiveState | null = null;
let selectedStakeCents = 500;
let customStakeSelected = false;
let serverOffsetMs = 0;
let identityToastTimer: number | null = null;
let refreshGeneration = 0;
let renderedRoundId: number | null = null;
let notifiedResultRoundId: number | null = null;
const pendingEntries = new Set<number>();
const pendingItems = new Set<string>();
const pendingSeats = new Set<string>();
const itemTargets = new Map<string, { entryId?: number; lane?: number; position?: number }>();
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
  crowdShoutSend.disabled = coolingDown;
  crowdBar.classList.toggle("is-cooling-down", coolingDown);
  const title = coolingDown
    ? `Ready in ${Math.max(Math.ceil(remainingMs / 1_000), 1)} seconds`
    : "";
  crowdCheer.title = title;
  crowdBoo.title = title;
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

function appendTrackNotice(message: string, tone: NoticeTone): void {
  messageFeedEmpty.hidden = true;
  const item = document.createElement("li");
  item.dataset.tone = tone;
  const marker = document.createElement("span");
  marker.setAttribute("aria-hidden", "true");
  marker.textContent = tone === "good" ? "✓" : tone === "bad" ? "!" : "•";
  const copy = document.createElement("span");
  copy.textContent = message;
  item.append(marker, copy);
  messageFeed.prepend(item);

  const notices = Array.from(messageFeed.querySelectorAll<HTMLLIElement>("li:not(#message-feed-empty)"));
  for (const staleNotice of notices.slice(8)) {
    staleNotice.remove();
  }
}

function showToast(message: string, tone: NoticeTone = "neutral"): void {
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

  toast.textContent = message;
  toast.dataset.tone = tone;
  toast.hidden = false;
  appendTrackNotice(message, tone);
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
  identityPanel.hidden = identified;
  gamePanel.hidden = !identified;
  accountToolbar.hidden = !identified;
  gameMenuButton.hidden = !identified;
  if (player === null) {
    closeGameMenu();
    return;
  }
  identityToast.hidden = true;
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
  const remainingCap = Math.max(
    (state?.room.max_round_stake_cents ?? 0) - player.round_staked_cents,
    0,
  );
  button.disabled =
    !bettingOpen || pendingEntries.has(entry.id) || selectedStakeCents > remainingCap;
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

function itemTargetKey(item: ItemDefinition): string {
  return item.slug;
}

function getItemTarget(item: ItemDefinition, entries: RacerEntry[]): {
  entryId?: number;
  lane?: number;
  position?: number;
} {
  const stored = itemTargets.get(itemTargetKey(item));
  if (stored !== undefined) {
    return stored;
  }
  if (item.target === "racer" && entries.length > 0) {
    return { entryId: entries[0]?.id };
  }
  return { lane: 1 / (entries.length + 1), position: 0.55 };
}

function canDeployItem(player: LivePlayer, item: ItemDefinition, marketOpen: boolean): boolean {
  if (!marketOpen || pendingItems.has(item.slug)) {
    return false;
  }
  const room = state?.room;
  const round = state?.round;
  if (room === undefined || round === null || round === undefined) {
    return false;
  }
  const itemCapLeft = room.max_round_item_spend_cents - player.round_item_spent_cents;
  const usesLeft = room.max_round_item_uses - player.item_uses.length;
  const alreadyUsed = player.item_uses.some((use) => use.item_slug === item.slug);
  return (
    item.price_cents <= player.balance_cents &&
    item.price_cents <= itemCapLeft &&
    usesLeft > 0 &&
    !alreadyUsed
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
  entries: RacerEntry[],
  marketOpen: boolean,
): HTMLElement {
  const card = document.createElement("article");
  card.className = "item-card";
  card.style.setProperty("--item-color", item.color);

  const header = document.createElement("div");
  header.className = "item-card__header";
  const icon = makeItemIcon(item.kind, item.icon);
  const titleWrap = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = item.name;
  const desc = document.createElement("p");
  desc.textContent = item.description;
  titleWrap.append(title, desc);
  const price = document.createElement("strong");
  price.className = "item-price";
  price.textContent = formatMoney(item.price_cents);
  header.append(icon, titleWrap, price);
  card.append(header);

  const targetWrap = document.createElement("div");
  targetWrap.className = "item-target";
  const target = getItemTarget(item, entries);

  if (item.target === "racer") {
    const label = document.createElement("label");
    label.textContent = "Target racer";
    label.htmlFor = `target-racer-${item.slug}`;
    const select = document.createElement("select");
    select.id = `target-racer-${item.slug}`;
    select.setAttribute("aria-label", `Target racer for ${item.name}`);
    for (const entry of entries) {
      const option = document.createElement("option");
      option.value = String(entry.id);
      option.textContent = entry.name;
      if (target.entryId === entry.id) {
        option.selected = true;
      }
      select.append(option);
    }
    select.addEventListener("change", () => {
      itemTargets.set(itemTargetKey(item), {
        entryId: Number.parseInt(select.value, 10),
      });
    });
    targetWrap.append(label, select);
  } else {
    const laneLabel = document.createElement("label");
    laneLabel.textContent = "Lane";
    laneLabel.htmlFor = `target-lane-${item.slug}`;
    const laneSelect = document.createElement("select");
    laneSelect.id = `target-lane-${item.slug}`;
    laneSelect.setAttribute("aria-label", `Target lane for ${item.name}`);
    const laneCount = entries.length || 4;
    for (let lane = 1; lane <= laneCount; lane += 1) {
      const normalizedLane = lane / (laneCount + 1);
      const option = document.createElement("option");
      option.value = String(normalizedLane);
      option.textContent = `Lane ${lane}`;
      if (Math.abs((target.lane ?? 0) - normalizedLane) < 0.01) {
        option.selected = true;
      }
      laneSelect.append(option);
    }
    laneSelect.addEventListener("change", () => {
      const current = getItemTarget(item, entries);
      itemTargets.set(itemTargetKey(item), {
        ...current,
        lane: Number.parseFloat(laneSelect.value),
      });
    });

    const posFieldset = document.createElement("fieldset");
    posFieldset.className = "track-position-picker";
    const legend = document.createElement("legend");
    legend.textContent = "Track position";
    posFieldset.append(legend);
    const posGroup = document.createElement("div");
    posGroup.setAttribute("role", "group");
    posGroup.setAttribute("aria-label", `Track position for ${item.name}`);
    for (const [position, label] of [
      [0.3, "Start"],
      [0.55, "Middle"],
      [0.78, "Final"],
    ] as const) {
      const posId = `pos-${item.slug}-${label.toLowerCase()}`;
      const input = document.createElement("input");
      input.type = "radio";
      input.name = `track-pos-${item.slug}`;
      input.id = posId;
      input.value = String(position);
      input.checked = Math.abs((target.position ?? 0.55) - position) < 0.01;
      input.addEventListener("change", () => {
        const current = getItemTarget(item, entries);
        itemTargets.set(itemTargetKey(item), { ...current, position });
      });
      const posLabel = document.createElement("label");
      posLabel.htmlFor = posId;
      posLabel.textContent = label;
      posGroup.append(input, posLabel);
    }
    posFieldset.append(posGroup);
    targetWrap.append(laneLabel, laneSelect, posFieldset);
  }
  card.append(targetWrap);

  const deployBtn = document.createElement("button");
  deployBtn.type = "button";
  deployBtn.className = "item-deploy-btn";
  deployBtn.textContent = pendingItems.has(item.slug)
    ? "Deploying…"
    : item.price_cents > player.balance_cents
      ? `Need ${formatMoney(item.price_cents)}`
      : "Buy & deploy";
  deployBtn.disabled = !canDeployItem(player, item, marketOpen);
  deployBtn.setAttribute("aria-label", `Deploy ${item.name} for ${formatMoney(item.price_cents)}`);
  deployBtn.addEventListener("click", () => {
    void buyItem(item, entries);
  });
  card.append(deployBtn);
  return card;
}

function renderItemMarket(player: LivePlayer, entries: RacerEntry[], marketOpen: boolean): void {
  itemMarket.replaceChildren();
  const catalog = state?.room.item_catalog ?? [];
  if (catalog.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "The black market is closed—no schemes listed.";
    itemMarket.append(empty);
    return;
  }
  for (const item of catalog) {
    itemMarket.append(makeItemCard(item, player, entries, marketOpen));
  }

  const spent = player.round_item_spent_cents;
  const maxSpend = state?.room.max_round_item_spend_cents ?? 0;
  const uses = player.item_uses.length;
  const maxUses = state?.room.max_round_item_uses ?? 0;
  itemCapText.textContent = `Scheme cap: ${formatMoney(spent)} of ${formatMoney(maxSpend)} · ${uses}/${maxUses} uses`;

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

  card.append(crown, mascot, title, desc, owner, claimBtn);
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
  accountBalance.textContent = formatMoney(player.balance_cents);
  accountBalance.classList.toggle("is-negative", player.balance_cents < 0);
  accountStaked.textContent = formatMoney(player.round_staked_cents);
  const inventoryCount = player.item_uses.length + (player.seat_claim === null ? 0 : 1);
  accountInventory.textContent = `${player.item_uses.length} scheme${
    player.item_uses.length === 1 ? "" : "s"
  }${player.seat_claim === null ? "" : " · 1 seat"}`;
  inventorySeat.textContent =
    player.seat_claim === null
      ? "No prestige seat claimed."
      : `Seat: ${player.seat_claim.seat_name}`;
  gameMenuCount.textContent = String(player.bets.length + inventoryCount);
}

function renderCrowdTargets(entries: RacerEntry[]): void {
  const current = crowdTarget.value;
  crowdTarget.replaceChildren();
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "Whole track";
  crowdTarget.append(allOption);
  for (const entry of entries) {
    const option = document.createElement("option");
    option.value = String(entry.racer_id);
    option.textContent = entry.name;
    crowdTarget.append(option);
  }
  if ([...crowdTarget.options].some((opt) => opt.value === current)) {
    crowdTarget.value = current;
  }
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
    itemTargets.clear();
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
  const used = player.round_staked_cents;
  capText.textContent = `${formatMoney(used)} of ${formatMoney(
    currentState.room.max_round_stake_cents,
  )}`;
  capMeter.max = currentState.room.max_round_stake_cents;
  capMeter.value = used;
  customStake.max = String(Math.max(Math.floor(currentState.room.max_round_stake_cents / 100), 1));

  quickStakeButtons.forEach((button) => {
    const selected =
      !customStakeSelected &&
      Number.parseInt(button.dataset.stakeCents ?? "", 10) === selectedStakeCents;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  customStakeControl.classList.toggle("is-selected", customStakeSelected);
  applyCustomStake.setAttribute("aria-pressed", String(customStakeSelected));

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
  renderItemMarket(player, entries, marketOpen);
  renderSeatMarket(player, marketOpen);
  renderLedger(player);
  renderCrowdTargets(entries);
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
  if (pendingEntries.has(entry.id)) {
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

async function buyItem(item: ItemDefinition, entries: RacerEntry[]): Promise<void> {
  if (pendingItems.has(item.slug) || state?.round === null || state?.round === undefined) {
    return;
  }
  pendingItems.add(item.slug);
  if (state !== null) {
    render(state);
  }
  const target = getItemTarget(item, entries);
  try {
    const payload: Parameters<typeof deployItem>[0] = {
      round_id: state.round.id,
      item_slug: item.slug,
      client_request_id: createClientRequestId(),
    };
    if (item.target === "racer" && target.entryId !== undefined) {
      payload.target_entry_id = target.entryId;
    } else if (item.target === "track") {
      payload.track_lane = target.lane ?? 0;
      payload.track_position = target.position ?? 1;
    }
    const receipt = await deployItem(payload);
    showToast(`${item.name} deployed! ${formatMoney(receipt.balance_cents)} left.`, "good");
    await refresh();
  } catch (error: unknown) {
    showToast(error instanceof ApiError ? error.message : "Scheme failed.", "bad");
  } finally {
    pendingItems.delete(item.slug);
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

function handleMessage(message: ServerMessage): void {
  if (
    message.type !== "audience.reaction" &&
    message.type !== "audience.rejected" &&
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
      const target =
        reaction.text ||
        (reaction.kind === "cheer" ? "Cheer!" : reaction.kind === "boo" ? "Boo!" : "Shout!");
      showToast(`${reaction.nickname}: ${target}`, "neutral");
      break;
    }
    case "audience.rejected":
      showToast(message.message, "bad");
      break;
    case "pong":
      break;
    default:
      assertNever(message);
  }
}

identityForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const nickname = nicknameInput.value.trim();
  void (async () => {
    try {
      await identifyPlayer(nickname || undefined);
      socket.reconnect();
      await refresh();
      showToast("Your betting sheet is ready.", "good");
    } catch (error: unknown) {
      showToast(error instanceof Error ? error.message : "Could not save that nickname.", "bad");
    }
  })();
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

quickStakeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    selectedStakeCents = Number.parseInt(button.dataset.stakeCents ?? "500", 10);
    customStakeSelected = false;
    customStake.value = String(selectedStakeCents / 100);
    if (state !== null) {
      render(state);
    }
  });
});

applyCustomStake.addEventListener("click", () => {
  const dollars = Number.parseInt(customStake.value, 10);
  if (!Number.isFinite(dollars) || dollars < 1) {
    showToast("Enter a whole-dollar stake of at least $1.", "bad");
    return;
  }
  const maximumStake = state?.room.max_round_stake_cents ?? 10_000;
  if (dollars * 100 > maximumStake) {
    showToast(`Custom stake cannot exceed ${formatMoney(maximumStake)}.`, "bad");
    return;
  }
  selectedStakeCents = dollars * 100;
  customStakeSelected = true;
  if (state !== null) {
    render(state);
  }
});
customStake.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    applyCustomStake.click();
  }
});

function sendCrowdReaction(kind: "cheer" | "boo" | "shout"): void {
  if (Date.now() < reactionCooldownUntil) {
    return;
  }
  const racerId = crowdTarget.value ? Number.parseInt(crowdTarget.value, 10) : undefined;
  if (kind === "shout") {
    const text = crowdShout.value.trim();
    if (text.length === 0) {
      showToast("Type a shout first (24 characters max).", "bad");
      return;
    }
    socket.sendReaction("shout", { text, racer_id: racerId });
    crowdShout.value = "";
  } else {
    socket.sendReaction(kind, { racer_id: racerId });
  }
  startReactionCooldown();
}

crowdCheer.addEventListener("click", () => {
  sendCrowdReaction("cheer");
});
crowdBoo.addEventListener("click", () => {
  sendCrowdReaction("boo");
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
