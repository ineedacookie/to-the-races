import { racerPortraitPath } from "../shared/assets";
import { renderEmptyState } from "../shared/dom";
import { formatMoney } from "../shared/format";
import {
  isTonicKind,
  itemArtPath,
  itemShopSection,
  type ItemKind,
  type ItemShopSection,
} from "../shared/itemCatalog";
import { loadingActionLabel, purchaseActionLabel } from "../shared/liveUi";
import {
  type InventoryItem,
  type ItemDefinition,
  type ItemUse,
  type LivePlayer,
  type LiveRound,
  type LiveState,
  type RacerEntry,
} from "../shared/types";
import { trackLaneLabel, trackPositionLabel } from "./raceSheet";

const ITEM_SHOP_SECTIONS: ReadonlyArray<{
  key: ItemShopSection;
  title: string;
  copy: string;
}> = [
  {
    key: "positive",
    title: "Positive potions",
    copy: "Help your racer. Assign during betting; drinks take effect at the next start and may fizzle.",
  },
  {
    key: "negative",
    title: "Negative potions",
    copy: "Hurt a rival. Assign during betting; tough racers may resist at the next start.",
  },
  {
    key: "neutral",
    title: "Neutral potions",
    copy: "Big changes with a downside. Assign during betting; drinks take effect at the next start and may fizzle.",
  },
  {
    key: "live",
    title: "Live race items",
    copy: "Use only while racers are moving. Choose a portrait to place it ahead.",
  },
];

export type ItemPromotion = "clearance" | "sale" | null;

export function itemPromotion(discountPct: number): ItemPromotion {
  if (discountPct >= 40) {
    return "clearance";
  }
  return discountPct > 0 ? "sale" : null;
}

export function promotionalItems(items: readonly ItemDefinition[]): {
  clearance: ItemDefinition[];
  sale: ItemDefinition[];
  regular: ItemDefinition[];
} {
  return {
    clearance: sortItemsByPrice(
      items.filter((item) => itemPromotion(item.discount_pct) === "clearance"),
    ),
    sale: sortItemsByPrice(
      items.filter((item) => itemPromotion(item.discount_pct) === "sale"),
    ),
    regular: items.filter((item) => itemPromotion(item.discount_pct) === null),
  };
}

export interface ItemShopElements {
  itemMarket: HTMLElement;
  itemCapText: HTMLElement;
  mySchemesList: HTMLElement;
  inventorySummary: HTMLElement;
  itemInventoryGrid: HTMLElement;
  itemTargetStep: HTMLElement;
  itemTargetCopy: HTMLElement;
  itemTargetGrid: HTMLElement;
}

export interface ItemShopContext {
  room: LiveState["room"] | undefined;
  bettingRound: LiveState["round"] | null | undefined;
  showRound: LiveState["show_round"] | null | undefined;
  pendingPurchases: ReadonlySet<string>;
  pendingItemUses: ReadonlySet<number>;
  pendingDiscards: ReadonlySet<number>;
  targetingInventoryItemId: number | null;
  playerInventoryCapacity: (player: LivePlayer) => number;
  buyItem: (item: ItemDefinition) => void;
  deployInventoryItem: (inventoryItem: InventoryItem, entry: RacerEntry) => void;
  trashInventoryItem: (inventoryItem: InventoryItem) => void;
  beginTargeting: (inventoryItemId: number) => void;
  cancelTargeting: () => void;
}

export function itemTargetRound(
  kind: ItemKind,
  bettingRound: LiveRound | null | undefined,
  showRound: LiveRound | null | undefined,
): LiveRound | null | undefined {
  return isTonicKind(kind) ? bettingRound : showRound;
}

function itemRound(
  kind: ItemKind,
  context: ItemShopContext,
): LiveRound | null | undefined {
  return itemTargetRound(kind, context.bettingRound, context.showRound);
}

function playerRoundItemUses(
  player: LivePlayer,
  kind: ItemKind,
  context: ItemShopContext,
): ItemUse[] {
  if (isTonicKind(kind)) {
    return player.item_uses;
  }
  return (context.showRound?.item_uses ?? []).filter(
    (use) => use.buyer === player.nickname,
  );
}

export function sortItemsByPrice(items: readonly ItemDefinition[]): ItemDefinition[] {
  return [...items].sort(
    (left, right) =>
      left.effective_price_cents - right.effective_price_cents ||
      left.name.localeCompare(right.name),
  );
}

export function itemUseWindowOpen(
  kind: ItemKind,
  potionWindowOpen: boolean,
  roundState: Pick<LiveRound, "state"> | null | undefined,
  roomPaused: boolean,
): boolean {
  return isTonicKind(kind)
    ? potionWindowOpen
    : roundState?.state === "racing" && !roomPaused;
}

function canPurchaseItem(
  player: LivePlayer,
  item: ItemDefinition,
  context: ItemShopContext,
): boolean {
  if (context.pendingPurchases.has(item.slug)) {
    return false;
  }
  if (context.room === undefined) {
    return false;
  }
  return (
    item.effective_price_cents <= player.balance_cents &&
    player.inventory.length < context.playerInventoryCapacity(player)
  );
}

function makeItemIcon(kind: ItemKind, fallback: string): HTMLElement {
  const icon = document.createElement("span");
  icon.className = "item-icon item-icon--art";
  icon.setAttribute("aria-hidden", "true");
  const artPath = itemArtPath(kind);
  const image = document.createElement("img");
  image.src = artPath;
  image.alt = "";
  image.width = 48;
  image.height = 48;
  icon.append(image);
  if (fallback.length > 0) {
    icon.title = fallback;
  }
  return icon;
}

function makeItemCard(
  item: ItemDefinition,
  player: LivePlayer,
  context: ItemShopContext,
): HTMLElement {
  const card = document.createElement("article");
  card.className = "item-card";
  card.style.setProperty("--item-color", item.color);
  const promotion = itemPromotion(item.discount_pct);
  if (promotion !== null) {
    card.classList.add(`item-card--${promotion}`);
    const badge = document.createElement("span");
    badge.className = `item-discount-badge item-discount-badge--${promotion}`;
    badge.textContent = `${promotion === "clearance" ? "CLEARANCE" : "SALE"} · ${item.discount_pct}% OFF`;
    card.append(badge);
  }

  const header = document.createElement("div");
  header.className = "item-card__header";
  const icon = makeItemIcon(item.kind, item.icon);
  const titleWrap = document.createElement("div");
  const title = document.createElement("h3");
  title.textContent = item.name;
  const desc = document.createElement("p");
  desc.textContent = item.description;
  titleWrap.append(title, desc);
  const priceWrap = document.createElement("div");
  priceWrap.className = "item-price-wrap";
  const effectivePrice = document.createElement("strong");
  effectivePrice.className = "item-price";
  effectivePrice.textContent = formatMoney(item.effective_price_cents);
  priceWrap.append(effectivePrice);
  if (item.discount_pct > 0) {
    const originalPrice = document.createElement("span");
    originalPrice.className = "item-price item-price--original";
    originalPrice.textContent = formatMoney(item.price_cents);
    priceWrap.append(originalPrice);
  }
  header.append(icon, titleWrap, priceWrap);
  card.append(header);

  const buyButton = document.createElement("button");
  buyButton.type = "button";
  buyButton.className = "item-buy-btn";
  buyButton.textContent = purchaseActionLabel({
    pending: context.pendingPurchases.has(item.slug),
    pendingAction: "Buying",
    blockedLabel:
      player.inventory.length >= context.playerInventoryCapacity(player)
        ? "Bag full"
        : undefined,
    requiredCents:
      item.effective_price_cents > player.balance_cents
        ? item.effective_price_cents
        : undefined,
    actionLabel: "Buy",
  });
  buyButton.disabled = !canPurchaseItem(player, item, context);
  buyButton.setAttribute(
    "aria-label",
    `Buy ${item.name} for ${formatMoney(item.effective_price_cents)}`,
  );
  buyButton.addEventListener("click", () => {
    context.buyItem(item);
  });
  card.append(buyButton);
  return card;
}

export function canUseInventoryItem(
  player: LivePlayer,
  inventoryItem: InventoryItem,
  potionWindowOpen: boolean,
  context: ItemShopContext,
): boolean {
  const room = context.room;
  if (
    room === undefined ||
    !itemUseWindowOpen(
      inventoryItem.kind,
      potionWindowOpen,
      itemRound(inventoryItem.kind, context),
      room.is_paused,
    ) ||
    context.pendingItemUses.has(inventoryItem.id) ||
    context.pendingDiscards.has(inventoryItem.id)
  ) {
    return false;
  }
  const roundUses = playerRoundItemUses(player, inventoryItem.kind, context);
  const spentCents = roundUses.reduce(
    (total, use) => total + use.price_paid_cents,
    0,
  );
  return (
    roundUses.length < room.max_round_item_uses &&
    spentCents + inventoryItem.price_paid_cents <= room.max_round_item_spend_cents
  );
}

function inventoryUseLabel(
  player: LivePlayer,
  inventoryItem: InventoryItem,
  potionWindowOpen: boolean,
  context: ItemShopContext,
): string {
  if (context.pendingItemUses.has(inventoryItem.id)) {
    return loadingActionLabel("Using");
  }
  const useWindowOpen =
    context.room !== undefined &&
    itemUseWindowOpen(
      inventoryItem.kind,
      potionWindowOpen,
      itemRound(inventoryItem.kind, context),
      context.room.is_paused,
    );
  if (isTonicKind(inventoryItem.kind) && !useWindowOpen) {
    return "Use during betting";
  }
  if (!isTonicKind(inventoryItem.kind) && !useWindowOpen) {
    return context.showRound?.state === "racing" ? "Paused" : "Use during race";
  }
  const roundUses = playerRoundItemUses(player, inventoryItem.kind, context);
  if (roundUses.length >= (context.room?.max_round_item_uses ?? 0)) {
    return "Use limit reached";
  }
  const spentCents = roundUses.reduce(
    (total, use) => total + use.price_paid_cents,
    0,
  );
  if (
    spentCents + inventoryItem.price_paid_cents >
    (context.room?.max_round_item_spend_cents ?? 0)
  ) {
    return "Use budget reached";
  }
  return "Use";
}

function renderItemUse(
  use: ItemUse,
  racerCount: number,
): HTMLElement {
  const item = document.createElement("li");
  item.style.setProperty("--item-color", use.item_color);
  const icon = makeItemIcon(use.kind, use.item_icon);
  const label = document.createElement("span");
  if (use.target_racer_name) {
    label.textContent = `${use.item_name} → ${use.target_racer_name}`;
  } else if (use.track_lane !== null && use.track_position !== null) {
    label.textContent = `${use.item_name} → ${trackLaneLabel(use.track_lane, racerCount)}, ${trackPositionLabel(use.track_position)}`;
  } else {
    label.textContent = use.item_name;
  }
  item.append(icon, label);
  return item;
}

export function renderItemMarket(
  elements: ItemShopElements,
  player: LivePlayer,
  context: ItemShopContext,
): void {
  elements.itemMarket.replaceChildren();
  const catalog = context.room?.item_catalog ?? [];
  if (catalog.length === 0) {
    renderEmptyState(elements.itemMarket, "The black market is closed—no schemes listed.");
    return;
  }
  const promoted = promotionalItems(catalog);
  const appendSection = (
    key: string,
    titleText: string,
    copyText: string,
    sectionItems: readonly ItemDefinition[],
  ): void => {
    if (sectionItems.length === 0) {
      return;
    }
    const group = document.createElement("section");
    group.className = `item-market__section item-market__section--${key}`;
    const heading = document.createElement("div");
    heading.className = "item-market__heading";
    const title = document.createElement("h3");
    title.textContent = titleText;
    const copy = document.createElement("p");
    copy.textContent = copyText;
    heading.append(title, copy);
    const grid = document.createElement("div");
    grid.className = "item-market__grid";
    for (const item of sectionItems) {
      grid.append(makeItemCard(item, player, context));
    }
    group.append(heading, grid);
    elements.itemMarket.append(group);
  };

  const dealRound = context.bettingRound?.number;
  appendSection(
    "clearance",
    "Clearance",
    dealRound === undefined
      ? "The deepest markdowns—40% off or more."
      : `The deepest markdowns—40% off or more in Round ${dealRound}.`,
    promoted.clearance,
  );
  appendSection(
    "sale",
    "On sale",
    dealRound === undefined
      ? "Fresh round-specific deals while they last."
      : `Fresh Round ${dealRound} deals while they last.`,
    promoted.sale,
  );
  for (const section of ITEM_SHOP_SECTIONS) {
    const sectionItems = sortItemsByPrice(
      promoted.regular.filter((item) => itemShopSection(item.kind) === section.key),
    );
    appendSection(section.key, section.title, section.copy, sectionItems);
  }

  const spent = player.round_item_spent_cents;
  const maxSpend = context.room?.max_round_item_spend_cents ?? 0;
  const uses = player.item_uses.length;
  const maxUses = context.room?.max_round_item_uses ?? 0;
  const maxInventory = context.playerInventoryCapacity(player);
  elements.itemCapText.textContent = `Bag ${player.inventory.length}/${maxInventory} · this round ${uses}/${maxUses} uses · ${formatMoney(spent)}/${formatMoney(maxSpend)}`;

  elements.mySchemesList.replaceChildren();
  if (player.item_uses.length === 0) {
    renderEmptyState(elements.mySchemesList, "No schemes deployed yet.", "li");
  } else {
    const racerCount = context.bettingRound?.entries.length ?? 4;
    for (const use of player.item_uses) {
      elements.mySchemesList.append(renderItemUse(use, racerCount));
    }
  }
}

export interface TuneInInventoryElements {
  summary: HTMLElement;
  grid: HTMLElement;
}

function makeInventoryItemCard(
  inventoryItem: InventoryItem,
  activeTargetId: number | null,
  player: LivePlayer,
  potionWindowOpen: boolean,
  context: ItemShopContext,
  targetPresentation: "portraits" | "select" = "portraits",
): HTMLElement {
  const card = document.createElement("article");
  card.className = "inventory-item-card";
  card.dataset.inventoryId = String(inventoryItem.id);
  card.style.setProperty("--item-color", inventoryItem.item_color);
  card.setAttribute("role", "listitem");
  card.classList.toggle("is-targeting", inventoryItem.id === activeTargetId);

  const trashButton = document.createElement("button");
  trashButton.type = "button";
  trashButton.className = "inventory-item-trash-button";
  trashButton.textContent = "🗑";
  trashButton.title = `Throw away ${inventoryItem.item_name} — no refund`;
  trashButton.setAttribute("aria-label", `Throw away ${inventoryItem.item_name}`);
  trashButton.disabled =
    context.pendingDiscards.has(inventoryItem.id) ||
    context.pendingItemUses.has(inventoryItem.id);
  trashButton.addEventListener("click", () => {
    context.trashInventoryItem(inventoryItem);
  });

  const details = document.createElement("div");
  details.className = "inventory-item-card__details";
  const icon = makeItemIcon(inventoryItem.kind, inventoryItem.item_icon);
  const name = document.createElement("strong");
  name.textContent = inventoryItem.item_name;
  const price = document.createElement("span");
  price.textContent = formatMoney(inventoryItem.price_paid_cents);
  details.append(icon, name, price);

  const canUse = canUseInventoryItem(player, inventoryItem, potionWindowOpen, context);
  if (targetPresentation === "select" && inventoryItem.id === activeTargetId) {
    const targetControls = document.createElement("div");
    targetControls.className = "tune-in-item-target";

    const targetSelect = document.createElement("select");
    targetSelect.className = "tune-in-item-target-select";
    targetSelect.setAttribute("aria-label", `Choose a racer for ${inventoryItem.item_name}`);
    targetSelect.disabled = !canUse;

    const prompt = document.createElement("option");
    prompt.value = "";
    prompt.textContent = "Choose racer…";
    prompt.disabled = true;
    prompt.selected = true;
    targetSelect.append(prompt);

    for (const entry of itemRound(inventoryItem.kind, context)?.entries ?? []) {
      const option = document.createElement("option");
      option.value = String(entry.id);
      option.textContent = entry.name;
      targetSelect.append(option);
    }
    targetSelect.addEventListener("change", () => {
      const entry = (itemRound(inventoryItem.kind, context)?.entries ?? []).find(
        ({ id }) => String(id) === targetSelect.value,
      );
      if (entry !== undefined) {
        context.deployInventoryItem(inventoryItem, entry);
      }
    });

    const cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "tune-in-item-target-cancel";
    cancelButton.textContent = "×";
    cancelButton.setAttribute("aria-label", `Cancel using ${inventoryItem.item_name}`);
    cancelButton.addEventListener("click", context.cancelTargeting);
    targetControls.append(targetSelect, cancelButton);
    card.append(trashButton, details, targetControls);
  } else {
    const useButton = document.createElement("button");
    useButton.type = "button";
    useButton.className = "inventory-item-use-button";
    useButton.textContent = inventoryUseLabel(player, inventoryItem, potionWindowOpen, context);
    useButton.disabled = !canUse;
    useButton.setAttribute("aria-label", `Use ${inventoryItem.item_name}`);
    useButton.addEventListener("click", () => {
      context.beginTargeting(inventoryItem.id);
    });
    card.append(trashButton, details, useButton);
  }
  return card;
}

function renderItemTargetStep(
  targetItem: InventoryItem | null,
  player: LivePlayer,
  potionWindowOpen: boolean,
  context: ItemShopContext,
  targetStep: HTMLElement,
  targetCopy: HTMLElement,
  targetGrid: HTMLElement,
): void {
  targetStep.hidden = targetItem === null;
  targetGrid.replaceChildren();
  if (targetItem !== null) {
    const entries = itemRound(targetItem.kind, context)?.entries ?? [];
    targetCopy.textContent = isTonicKind(targetItem.kind)
      ? `Choose who drinks ${targetItem.item_name} at the next race start.`
      : `Choose whose path receives ${targetItem.item_name} right now.`;
    for (const entry of entries) {
      const targetButton = document.createElement("button");
      targetButton.type = "button";
      targetButton.className = "item-target-portrait";
      targetButton.disabled = !canUseInventoryItem(
        player,
        targetItem,
        potionWindowOpen,
        context,
      );
      targetButton.setAttribute("aria-label", `Use ${targetItem.item_name} on ${entry.name}`);
      const portrait = document.createElement("img");
      portrait.src = racerPortraitPath(entry.sprite_key);
      portrait.alt = "";
      portrait.width = 72;
      portrait.height = 72;
      const name = document.createElement("strong");
      name.textContent = entry.name;
      targetButton.append(portrait, name);
      targetButton.addEventListener("click", () => {
        context.deployInventoryItem(targetItem, entry);
      });
      targetGrid.append(targetButton);
    }
  }
}

function resolveTargetItem(
  player: LivePlayer,
  potionWindowOpen: boolean,
  context: ItemShopContext,
): InventoryItem | null {
  const requestedTarget =
    player.inventory.find((item) => item.id === context.targetingInventoryItemId) ?? null;
  if (
    requestedTarget !== null &&
    canUseInventoryItem(player, requestedTarget, potionWindowOpen, context)
  ) {
    return requestedTarget;
  }
  return null;
}

export function renderInventory(
  elements: ItemShopElements,
  player: LivePlayer,
  potionWindowOpen: boolean,
  context: ItemShopContext,
): number | null {
  const maxInventory = context.playerInventoryCapacity(player);
  const targetItem = resolveTargetItem(player, potionWindowOpen, context);
  const activeTargetId = targetItem?.id ?? null;

  elements.inventorySummary.textContent = `${player.inventory.length} / ${maxInventory} items`;
  elements.itemInventoryGrid.replaceChildren();
  for (const inventoryItem of player.inventory) {
    elements.itemInventoryGrid.append(
      makeInventoryItemCard(inventoryItem, activeTargetId, player, potionWindowOpen, context),
    );
  }
  for (let slot = player.inventory.length; slot < maxInventory; slot += 1) {
    const empty = document.createElement("div");
    empty.className = "inventory-item-card inventory-item-card--empty";
    empty.setAttribute("aria-hidden", "true");
    empty.textContent = "Empty slot";
    elements.itemInventoryGrid.append(empty);
  }

  renderItemTargetStep(
    targetItem,
    player,
    potionWindowOpen,
    context,
    elements.itemTargetStep,
    elements.itemTargetCopy,
    elements.itemTargetGrid,
  );
  return activeTargetId;
}

export function renderTuneInInventory(
  elements: TuneInInventoryElements,
  player: LivePlayer,
  potionWindowOpen: boolean,
  context: ItemShopContext,
): number | null {
  const targetItem = resolveTargetItem(player, potionWindowOpen, context);
  const activeTargetId = targetItem?.id ?? null;

  elements.summary.textContent = `${player.inventory.length} items`;
  elements.grid.replaceChildren();
  if (player.inventory.length === 0) {
    renderEmptyState(elements.grid, "No items in your bag.");
  } else {
    for (const inventoryItem of player.inventory) {
      elements.grid.append(
        makeInventoryItemCard(
          inventoryItem,
          activeTargetId,
          player,
          potionWindowOpen,
          context,
          "select",
        ),
      );
    }
  }
  return activeTargetId;
}
