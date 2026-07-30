import {
  claimSeat,
  discardItem,
  fetchState,
  identifyPlayer,
  loginPlayer,
  purchaseItem,
  purchaseUpgrade,
  submitBet,
  suggestNickname,
  useItem,
} from "../shared/api";
import { required } from "../shared/dom";
import { formatMoney } from "../shared/format";
import { isTonicKind } from "../shared/itemCatalog";
import {
  applyConnectionStatus,
  bettingPhaseLabel,
  createLiveClockController,
  presentationRound,
  userFacingApiError,
} from "../shared/liveUi";
import { runPendingAction } from "../shared/pendingAction";
import { defaultReactionMessage } from "../shared/reactions";
import { LiveSocket } from "../shared/socket";
import {
  assertNever,
  type InventoryItem,
  type ItemDefinition,
  type LivePlayer,
  type LiveState,
  type RacerEntry,
  type SeatDefinition,
  type ServerMessage,
  type UpgradeDefinition,
} from "../shared/types";
import {
  renderAccountAndInventory,
  renderBets,
  renderBettingResults,
  renderBoards,
  renderLedger,
  type AccountRecordsContext,
  type AccountRecordsElements,
} from "./accountRecords";
import { createAccountDrawerController } from "./accountDrawer";
import { createAvatarBuilder } from "./avatarBuilder";
import { createBetSheetController } from "./betSheets";
import {
  bettingOptionCanSubmit,
  deriveBettingOptions,
  type BettingOptions,
} from "./bettingOptions";
import { createCrowdReactionController } from "./crowdReactions";
import {
  renderInventory,
  renderItemMarket,
  renderTuneInInventory,
  type ItemShopContext,
  type ItemShopElements,
  type TuneInInventoryElements,
} from "./itemShop";
import { updateSeatPresence } from "./liveState";
import { renderRaceSheet, type RaceSheetContext, type RaceSheetElements } from "./raceSheet";
import { renderSeatMarket, type SeatMarketContext, type SeatMarketElements } from "./seatMarket";
import {
  parseStakeCents,
  stakeBlockReason,
  stakeDraftMaxCents,
} from "./stakeLimits";
import { createTrackMedicController, type TrackMedicUiState } from "./trackMedicUi";
import { renderUpgradeMarket, type UpgradeMarketContext, type UpgradeMarketElements } from "./upgrades";

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
const accountButton = required<HTMLButtonElement>("#account-button");
const inventoryTabCount = required<HTMLElement>("#inventory-tab-count");
const accountDrawerBackdrop = required<HTMLElement>("#account-drawer-backdrop");
const accountDrawerPanel = required<HTMLElement>("#account-drawer");
const accountDrawerClose = required<HTMLButtonElement>("#account-drawer-close");
const betSheetTabs = Array.from(
  document.querySelectorAll<HTMLButtonElement>("[data-bet-sheet]"),
);
const betSheetPanels = Array.from(
  document.querySelectorAll<HTMLElement>("[data-bet-sheet-content]"),
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
const tuneInInventorySummary = required<HTMLElement>("#tune-in-inventory-summary");
const tuneInInventoryGrid = required<HTMLElement>("#tune-in-inventory-grid");
const mySchemesList = required<HTMLElement>("#my-schemes-list");
const seatGrid = required<HTMLElement>("#seat-grid");
const upgradeGrid = required<HTMLElement>("#upgrade-grid");
const leaderboardList = required<HTMLElement>("#leaderboard-list");
const debtList = required<HTMLElement>("#debt-list");
const ledgerList = required<HTMLElement>("#ledger-list");
const inventorySeat = required<HTMLElement>("#inventory-seat");
const accountName = required<HTMLElement>("#account-name");
const accountAvatar = required<HTMLImageElement>("#account-avatar");
const editIdentityButton = required<HTMLButtonElement>("#edit-identity");
const accountBalance = required<HTMLElement>("#account-balance");
const accountStaked = required<HTMLElement>("#account-staked");
const accountBettingRecord = required<HTMLElement>("#account-betting-record");
const accountInventory = required<HTMLElement>("#account-inventory");
const resultsPanel = required<HTMLElement>("#results-panel");
const resultsTitle = required<HTMLElement>("#results-title");
const resultsList = required<HTMLElement>("#results-list");
const customStake = required<HTMLInputElement>("#custom-stake");
const stakeAddFive = required<HTMLButtonElement>("#stake-add-five");
const stakeAddTen = required<HTMLButtonElement>("#stake-add-ten");
const stakeMax = required<HTMLButtonElement>("#stake-max");
const stakeHint = required<HTMLElement>("#stake-hint");
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
const trackMedicCallout = required<HTMLElement>("#track-medic-callout");
const trackMedicCalloutTitle = required<HTMLElement>("#track-medic-callout-title");
const trackMedicCalloutCopyEl = required<HTMLElement>("#track-medic-callout-copy");
const trackMedicOpen = required<HTMLButtonElement>("#track-medic-open");
const trackMedicBackdrop = required<HTMLElement>("#track-medic-backdrop");
const trackMedicClose = required<HTMLButtonElement>("#track-medic-close");
const trackMedicTitle = required<HTMLElement>("#track-medic-title");
const trackMedicCopy = required<HTMLElement>("#track-medic-copy");
const trackMedicPortrait = required<HTMLImageElement>("#track-medic-portrait");
const trackMedicWounds = required<HTMLElement>("#track-medic-wounds");
const trackMedicProgress = required<HTMLElement>("#track-medic-progress");
const trackMedicReward = required<HTMLElement>("#track-medic-reward");

const accountRecordsElements: AccountRecordsElements = {
  accountName,
  accountAvatar,
  accountBalance,
  accountStaked,
  accountBettingRecord,
  accountInventory,
  inventorySeat,
  inventoryTabCount,
  leaderboardList,
  debtList,
  ledgerList,
  betsList,
  resultsPanel,
  resultsTitle,
  resultsList,
};

const raceSheetElements: RaceSheetElements = {
  racerGrid,
};

const itemShopElements: ItemShopElements = {
  itemMarket,
  itemCapText,
  mySchemesList,
  inventorySummary,
  itemInventoryGrid,
  itemTargetStep,
  itemTargetCopy,
  itemTargetGrid,
};

const tuneInInventoryElements: TuneInInventoryElements = {
  summary: tuneInInventorySummary,
  grid: tuneInInventoryGrid,
};

const seatMarketElements: SeatMarketElements = { seatGrid };
const upgradeMarketElements: UpgradeMarketElements = { upgradeGrid };

let state: LiveState | null = null;
type IdentityMode = "signup" | "login";
let identityMode: IdentityMode = "signup";
let editingIdentity = false;
let selectedStakeCents = 500;
let identityToastTimer: number | null = null;
let refreshGeneration = 0;
let renderedRoundId: number | null = null;
let notifiedResultRoundId: number | null = null;
const pendingEntries = new Set<number>();
const pendingPurchases = new Set<string>();
const pendingItemUses = new Set<number>();
const pendingDiscards = new Set<number>();
const pendingSeats = new Set<string>();
const pendingUpgrades = new Set<string>();
let targetingInventoryItemId: number | null = null;
const liveClock = createLiveClockController({
  clockLabel,
  countdown,
  getRound: () => (state === null ? null : presentationRound(state)),
  isPaused: () => state?.room.is_paused ?? false,
  onTransitionOverdue: () => socket.requestSync(),
});

type NoticeTone = "good" | "bad" | "neutral";

const accountDrawer = createAccountDrawerController({
  bettingHeader,
  bettingMain,
  accountButton,
  backdrop: accountDrawerBackdrop,
  drawer: accountDrawerPanel,
  closeButton: accountDrawerClose,
});
const betSheets = createBetSheetController({
  tabs: betSheetTabs,
  panels: betSheetPanels,
});

const trackMedicState: TrackMedicUiState = {
  panelOpen: false,
  pendingStarts: new Set<number>(),
  pendingPatches: new Set<string>(),
};

function playerInventoryCapacity(player: LivePlayer): number {
  return player.effective_inventory_capacity;
}

const accountRecordsContext: AccountRecordsContext = { playerInventoryCapacity };

function selectedBetFor(entry: RacerEntry, player: LivePlayer): number {
  return player.bets
    .filter((bet) => bet.racer_id === entry.racer_id)
    .reduce((total, bet) => total + bet.amount_cents, 0);
}

function appendTrackNotice(message: string, tone: NoticeTone, author?: string): void {
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

  const notices = Array.from(
    messageFeed.querySelectorAll<HTMLLIElement>("li:not(#message-feed-empty)"),
  );
  for (const staleNotice of notices.slice(8)) {
    staleNotice.remove();
  }
}

function showToast(message: string, tone: NoticeTone = "neutral", author?: string): void {
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

function setConnection(status: Parameters<LiveSocket["options"]["onStatus"]>[0]): void {
  applyConnectionStatus(connectionText, status);
}

function renderIdentity(player: LivePlayer | null): void {
  const identified = player !== null;
  const showingEditor = !identified || editingIdentity;
  const loggingIn = !identified && !editingIdentity && identityMode === "login";
  identityPanel.hidden = !showingEditor;
  identityPanel.classList.toggle("identity-card--login", loggingIn);
  gamePanel.hidden = showingEditor;
  accountToolbar.hidden = showingEditor;
  accountButton.hidden = showingEditor;
  identityModeSelector.hidden = editingIdentity;
  identityModeSignup.setAttribute("aria-pressed", String(!loggingIn));
  identityModeLogin.setAttribute("aria-pressed", String(loggingIn));
  avatarBuilderRoot.classList.toggle("avatar-builder--login", loggingIn);
  randomNameButton.hidden = loggingIn;
  nicknameInput.required = loggingIn;
  nicknameLabel.textContent = loggingIn ? "Existing username" : "Nickname";
  identityTitle.textContent = editingIdentity
    ? "Change your trackside identity"
    : loggingIn
      ? "Welcome back, troublemaker"
      : "What should the bookie call you?";
  identityCopy.textContent = editingIdentity
    ? "Update your username or look. Every device logged into this account will share the change."
    : loggingIn
      ? "Enter an existing username to reclaim its balance, inventory, bets, and bleacher character. No password required."
      : "Pick a nickname and build your bleacher self. This device will remember both next time. No password, no real money, no sensible financial decisions.";
  identityCancel.hidden = !editingIdentity;
  identitySubmit.textContent = editingIdentity
    ? "Save name & look"
    : loggingIn
      ? "Log in"
      : "Get my sheet";
  if (player === null) {
    accountDrawer.close();
    return;
  }
  if (!editingIdentity) {
    identityToast.hidden = true;
  }
  playerName.textContent = player.nickname;
  balance.textContent = formatMoney(player.balance_cents);
}

function currentBettingOptions(
  currentState: LiveState,
  player: LivePlayer,
): BettingOptions {
  return deriveBettingOptions(
    currentState,
    player,
    selectedStakeCents,
    pendingEntries.size,
    liveClock.offsetMs(),
  );
}

function syncStakeInput(
  player: LivePlayer,
  room: LiveState["room"],
  bettingOpen: boolean,
): void {
  const maxStake = stakeDraftMaxCents(
    bettingOpen,
    player.balance_cents,
    player.round_staked_cents,
    room.max_round_stake_cents,
  );
  customStake.max = String(maxStake / 100);
  if (selectedStakeCents > maxStake) {
    selectedStakeCents = maxStake;
    customStake.value = maxStake > 0 ? String(maxStake / 100) : "";
  }
  const canIncrease = selectedStakeCents < maxStake;
  stakeAddFive.disabled = !canIncrease;
  stakeAddTen.disabled = !canIncrease;
  stakeMax.disabled = !canIncrease;
  if (!bettingOpen) {
    stakeHint.textContent =
      `Betting closed · prepare up to ${formatMoney(maxStake)} for when it opens.`;
    return;
  }
  const blockReason = stakeBlockReason(
    selectedStakeCents,
    player.balance_cents,
    player.round_staked_cents,
    room.max_round_stake_cents,
  );
  stakeHint.textContent =
    blockReason ??
    `Up to ${formatMoney(maxStake)} per bet · ${formatMoney(
      player.round_stake_remaining_cents,
    )} left this round (${formatMoney(room.max_round_stake_cents)} cap).`;
}

function setStakeCents(nextStakeCents: number): void {
  if (state?.player === null || state?.player === undefined) {
    return;
  }
  const maximum = stakeDraftMaxCents(
    currentBettingOptions(state, state.player).marketOpen,
    state.player.balance_cents,
    state.player.round_staked_cents,
    state.room.max_round_stake_cents,
  );
  selectedStakeCents = Math.min(Math.max(nextStakeCents, 0), maximum);
  customStake.value =
    selectedStakeCents > 0 ? String(selectedStakeCents / 100) : "";
  render(state);
}

function setMaximumStake(): void {
  if (state?.player === null || state?.player === undefined) {
    return;
  }
  setStakeCents(
    stakeDraftMaxCents(
      currentBettingOptions(state, state.player).marketOpen,
      state.player.balance_cents,
      state.player.round_staked_cents,
      state.room.max_round_stake_cents,
    ),
  );
}

function buildItemShopContext(
  focusGrid = itemTargetGrid,
  selectInventorySheet = true,
): ItemShopContext {
  return {
    room: state?.room,
    bettingRound: state?.round,
    showRound: state?.show_round,
    pendingPurchases,
    pendingItemUses,
    pendingDiscards,
    targetingInventoryItemId,
    playerInventoryCapacity,
    buyItem: (item) => {
      void buyItem(item);
    },
    deployInventoryItem: (inventoryItem, entry) => {
      void deployInventoryItem(inventoryItem, entry);
    },
    trashInventoryItem: (inventoryItem) => {
      void trashInventoryItem(inventoryItem);
    },
    beginTargeting: (inventoryItemId) => {
      targetingInventoryItemId = inventoryItemId;
      if (selectInventorySheet) {
        betSheets.select("inventory");
      }
      if (state !== null) {
        render(state);
        window.requestAnimationFrame(() => {
          const inlineSelect = focusGrid.querySelector<HTMLSelectElement>(
            `[data-inventory-id="${inventoryItemId}"] .tune-in-item-target-select`,
          );
          if (inlineSelect !== null) {
            inlineSelect.focus();
          } else {
            focusGrid.querySelector<HTMLButtonElement>("button")?.focus();
          }
        });
      }
    },
    cancelTargeting: () => {
      const cancelledInventoryItemId = targetingInventoryItemId;
      targetingInventoryItemId = null;
      if (state !== null) {
        render(state);
        window.requestAnimationFrame(() => {
          if (cancelledInventoryItemId !== null) {
            focusGrid
              .querySelector<HTMLButtonElement>(
                `[data-inventory-id="${cancelledInventoryItemId}"] .inventory-item-use-button`,
              )
              ?.focus();
          }
        });
      }
    },
  };
}

function buildSeatMarketContext(): SeatMarketContext {
  return {
    round: state?.round,
    room: state?.room,
    pendingSeats,
    buySeat: (seat, expectedPriceCents) => {
      void buySeat(seat, expectedPriceCents);
    },
  };
}

function buildUpgradeMarketContext(): UpgradeMarketContext {
  return {
    pendingUpgrades,
    buyUpgrade: (upgrade) => {
      void buyUpgrade(upgrade);
    },
  };
}

function buildRaceSheetContext(options: BettingOptions): RaceSheetContext {
  return {
    options,
    pendingEntries,
    selectedBetFor,
    placeBet: (entry) => {
      void placeBet(entry);
    },
  };
}

function render(currentState: LiveState): void {
  const nextRoundId = currentState.round?.id ?? null;
  if (renderedRoundId !== null && nextRoundId !== renderedRoundId) {
    targetingInventoryItemId = null;
    trackMedicController.close();
  }
  renderedRoundId = nextRoundId;
  state = currentState;
  document.body.dataset.roundState = presentationRound(currentState)?.state ?? "waiting";
  liveClock.sync(currentState.server_time);
  renderIdentity(currentState.player);
  phaseLabel.textContent = bettingPhaseLabel(currentState.round, currentState.room.is_paused, currentState.show_round);
  roundLabel.textContent = currentState.round ? `Round ${currentState.round.number}` : "Next round";
  renderBoards(accountRecordsElements, currentState);

  if (currentState.player === null) {
    return;
  }

  const player = currentState.player;
  const marketOpen = currentBettingOptions(currentState, player).marketOpen;
  renderAccountAndInventory(accountRecordsElements, accountRecordsContext, player);
  syncStakeInput(player, currentState.room, marketOpen);
  const bettingOptions = currentBettingOptions(currentState, player);
  const entries = currentState.round?.entries ?? [];
  crowdBar.hidden = false;

  renderRaceSheet(
    raceSheetElements,
    entries,
    player,
    buildRaceSheetContext(bettingOptions),
  );
  renderItemMarket(itemShopElements, player, buildItemShopContext());
  renderUpgradeMarket(
    upgradeMarketElements,
    player,
    currentState.room.upgrade_catalog,
    buildUpgradeMarketContext(),
  );
  targetingInventoryItemId = renderInventory(
    itemShopElements,
    player,
    bettingOptions.marketOpen,
    buildItemShopContext(),
  );
  renderTuneInInventory(
    tuneInInventoryElements,
    player,
    bettingOptions.marketOpen,
    buildItemShopContext(tuneInInventoryGrid, false),
  );
  renderSeatMarket(
    seatMarketElements,
    player,
    bettingOptions.marketOpen,
    buildSeatMarketContext(),
  );
  renderLedger(accountRecordsElements, player);
  renderBets(accountRecordsElements, player);
  renderBettingResults(accountRecordsElements, currentState, (roundId, title) => {
    if (notifiedResultRoundId !== roundId) {
      notifiedResultRoundId = roundId;
      showToast(`Official: ${title}`, "good");
    }
  });
  trackMedicController.render(player, currentState);
}

function notifySeatEviction(
  previousSeat: LivePlayer["seat_claim"],
  nextSeat: LivePlayer["seat_claim"],
): void {
  if (previousSeat !== null && nextSeat === null) {
    showToast(
      `You were bumped from ${previousSeat.seat_name}. 50% of your purchase was refunded.`,
      "bad",
    );
  }
}

async function refresh(): Promise<void> {
  const generation = ++refreshGeneration;
  try {
    const nextState = await fetchState();
    if (generation === refreshGeneration) {
      const previousSeat = state?.player?.seat_claim;
      const nextSeat = nextState.player?.seat_claim;
      render(nextState);
      notifySeatEviction(previousSeat ?? null, nextSeat ?? null);
    }
  } catch (error: unknown) {
    if (generation === refreshGeneration) {
      showToast(userFacingApiError(error, "Could not refresh the race."), "bad");
    }
  }
}

const trackMedicController = createTrackMedicController(
  {
    bettingHeader,
    bettingMain,
    trackMedicCallout,
    trackMedicCalloutTitle,
    trackMedicCalloutCopyEl,
    trackMedicOpen,
    trackMedicBackdrop,
    trackMedicClose,
    trackMedicTitle,
    trackMedicCopy,
    trackMedicPortrait,
    trackMedicWounds,
    trackMedicProgress,
    trackMedicReward,
    returnFocusFallback: customStake,
  },
  {
    getState: () => state,
    refresh,
    showToast,
  },
  trackMedicState,
);

function renderCurrentState(): void {
  if (state !== null) {
    render(state);
  }
}

async function placeBet(entry: RacerEntry): Promise<void> {
  if (pendingEntries.size > 0 || state === null || state.player === null) {
    return;
  }
  const options = currentBettingOptions(state, state.player);
  if (!options.marketOpen) {
    showToast("Betting is closed for this race.", "bad");
    return;
  }
  if (!options.entryIds.has(entry.id)) {
    showToast("The lineup changed. Choose a racer from the current options.", "bad");
    await refresh();
    return;
  }
  if (options.stakeError !== null) {
    showToast(options.stakeError, "bad");
    customStake.focus();
    return;
  }
  if (!bettingOptionCanSubmit(options, entry.id)) {
    return;
  }
  await runPendingAction({
    key: entry.id,
    pending: pendingEntries,
    onPendingChange: renderCurrentState,
    action: async () => {
      const receipt = await submitBet(entry.id, selectedStakeCents);
      showToast(
        `${formatMoney(receipt.bet.amount_cents)} on ${receipt.bet.racer_name}. Good luck!`,
        "good",
      );
      await refresh();
    },
    onError: (error) => {
      showToast(userFacingApiError(error, "That bet did not go through."), "bad");
    },
  });
}

async function buyItem(item: ItemDefinition): Promise<void> {
  await runPendingAction({
    key: item.slug,
    pending: pendingPurchases,
    onPendingChange: renderCurrentState,
    action: async () => {
      const receipt = await purchaseItem(item.slug);
      showToast(
        `${item.name} is in your bag. ${formatMoney(receipt.balance_cents)} left.`,
        "good",
      );
      await refresh();
    },
    onError: (error) => {
      showToast(userFacingApiError(error, "Purchase failed."), "bad");
    },
  });
}

async function buyUpgrade(upgrade: UpgradeDefinition): Promise<void> {
  await runPendingAction({
    key: upgrade.slug,
    pending: pendingUpgrades,
    onPendingChange: renderCurrentState,
    action: async () => {
      const receipt = await purchaseUpgrade(upgrade.slug);
      const capacity =
        receipt.player_upgrade.inventory_capacity === null
          ? ""
          : ` Bag capacity is now ${receipt.player_upgrade.inventory_capacity} slots.`;
      showToast(
        `${upgrade.name} unlocked.${capacity} ${formatMoney(receipt.balance_cents)} left.`,
        "good",
      );
      await refresh();
    },
    onError: (error) => {
      showToast(userFacingApiError(error, "Upgrade purchase failed."), "bad");
    },
  });
}

async function deployInventoryItem(
  inventoryItem: InventoryItem,
  entry: RacerEntry,
): Promise<void> {
  if (state?.round === null || state?.round === undefined) {
    return;
  }
  const roundId = isTonicKind(inventoryItem.kind)
    ? state.round.id
    : (state.show_round?.id ?? state.round.id);
  await runPendingAction({
    key: inventoryItem.id,
    pending: pendingItemUses,
    onPendingChange: renderCurrentState,
    action: async () => {
      await useItem(roundId, inventoryItem.id, entry.id);
      targetingInventoryItemId = null;
      showToast(
        isTonicKind(inventoryItem.kind)
          ? `${entry.name} will drink ${inventoryItem.item_name} at the next start.`
          : `${inventoryItem.item_name} is live in ${entry.name}'s path!`,
        "good",
      );
      await refresh();
    },
    onError: (error) => {
      showToast(userFacingApiError(error, "Item use failed."), "bad");
    },
  });
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
  if (targetingInventoryItemId === inventoryItem.id) {
    targetingInventoryItemId = null;
  }
  await runPendingAction({
    key: inventoryItem.id,
    pending: pendingDiscards,
    onPendingChange: renderCurrentState,
    action: async () => {
      await discardItem(inventoryItem.id);
      showToast(`${inventoryItem.item_name} was thrown away. No refund.`, "neutral");
      await refresh();
    },
    onError: (error) => {
      showToast(userFacingApiError(error, "Could not discard that item."), "bad");
    },
  });
}

async function buySeat(seat: SeatDefinition, expectedPriceCents: number): Promise<void> {
  if (state?.round === null || state?.round === undefined) {
    return;
  }
  const roundId = state.round.id;
  await runPendingAction({
    key: seat.slug,
    pending: pendingSeats,
    onPendingChange: renderCurrentState,
    action: async () => {
      const receipt = await claimSeat(roundId, seat.slug, expectedPriceCents);
      showToast(`You took over ${receipt.seat_claim.seat_name}!`, "good");
      await refresh();
    },
    onError: async (error) => {
      showToast(userFacingApiError(error, "Seat takeover failed."), "bad");
      await refresh();
    },
  });
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
      render(message.state);
      showToast(
        message.state.show_round === null
          ? "A fresh betting sheet is open."
          : `Round ${message.state.round?.number ?? "next"} betting is open during the highlights.`,
        "good",
      );
      break;
    case "round.locked":
      render(message.state);
      showToast("Pencils down—bets are locked.");
      break;
    case "race.started":
      render(message.state);
      showToast("They're off!");
      break;
    case "race.finished":
      render(message.state);
      break;
    case "broadcast.finished":
      render(message.state);
      showToast("Broadcast complete—15 seconds left to bet.");
      break;
    case "bets.updated":
    case "items.updated":
    case "upgrades.updated":
    case "bailout.updated":
      render(message.state);
      break;
    case "seats.updated": {
      const previousSeat = state?.player?.seat_claim ?? null;
      render(message.state);
      notifySeatEviction(previousSeat, message.state.player?.seat_claim ?? null);
      break;
    }
    case "balance.updated":
      if (state?.player !== null && state?.player !== undefined) {
        state.player.balance_cents = message.balance_cents;
        render(state);
      }
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
    case "presence.join":
      if (state !== null) {
        render(updateSeatPresence(state, message.spectator.player_id, true));
      }
      break;
    case "presence.leave":
      if (state !== null) {
        render(updateSeatPresence(state, message.player_id, false));
      }
      break;
    case "presence.sync":
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
      window.scrollTo({ top: 0 });
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: 0 });
      });
      showToast(
        wasEditing
          ? "Your bleacher character is updated."
          : wasLoggingIn
            ? `Welcome back, ${nickname}.`
            : "Your betting sheet is ready.",
        "good",
      );
    } catch (error: unknown) {
      showToast(userFacingApiError(error, "Could not save that identity."), "bad");
    }
  })();
});

function selectIdentityMode(mode: IdentityMode): void {
  if (editingIdentity || (state?.player !== null && state?.player !== undefined)) {
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
  accountDrawer.close();
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
  accountButton.focus();
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
  selectedStakeCents = parseStakeCents(customStake.value);
  if (state !== null) {
    render(state);
  }
});

stakeAddFive.addEventListener("click", () => {
  setStakeCents(selectedStakeCents + 500);
});

stakeAddTen.addEventListener("click", () => {
  setStakeCents(selectedStakeCents + 1_000);
});

stakeMax.addEventListener("click", () => {
  setMaximumStake();
});

const socket = new LiveSocket({
  role: "bet",
  onMessage: handleMessage,
  onStatus: setConnection,
});
const crowdReactions = createCrowdReactionController(
  {
    cheer: crowdCheer,
    boo: crowdBoo,
    cry: crowdCry,
    shout: crowdShout,
    shoutSend: crowdShoutSend,
  },
  {
    sendReaction: (kind, options) => {
      socket.sendReaction(kind, options);
    },
    showError: (message) => {
      showToast(message, "bad");
    },
  },
);

accountDrawer.wireEvents();
betSheets.wireEvents();
trackMedicController.wireEvents();
crowdReactions.wireEvents();
socket.start();
liveClock.start();
void refresh();
