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
  roundState: LiveState["round"] | null | undefined;
  pendingPurchases: ReadonlySet<string>;
  pendingItemUses: ReadonlySet<number>;
  pendingDiscards: ReadonlySet<number>;
  targetingInventoryItemId: number | null;
  playerInventoryCapacity: (player: LivePlayer) => number;
  buyItem: (item: ItemDefinition) => void;
  deployInventoryItem: (inventoryItem: InventoryItem, entry: RacerEntry) => void;
  trashInventoryItem: (inventoryItem: InventoryItem) => void;
  beginTargeting: (inventoryItemId: number) => void;
}

export function sortItemsByPrice(items: readonly ItemDefinition[]): ItemDefinition[] {
  return [...items].sort(
    (left, right) =>
      left.price_cents - right.price_cents || left.name.localeCompare(right.name),
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
    item.price_cents <= player.balance_cents &&
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
    requiredCents: item.price_cents > player.balance_cents ? item.price_cents : undefined,
    actionLabel: "Buy",
  });
  buyButton.disabled = !canPurchaseItem(player, item, context);
  buyButton.setAttribute("aria-label", `Buy ${item.name} for ${formatMoney(item.price_cents)}`);
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
      context.roundState,
      room.is_paused,
    ) ||
    context.pendingItemUses.has(inventoryItem.id) ||
    context.pendingDiscards.has(inventoryItem.id)
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
      context.roundState,
      context.room.is_paused,
    );
  if (isTonicKind(inventoryItem.kind) && !useWindowOpen) {
    return "Use during betting";
  }
  if (!isTonicKind(inventoryItem.kind) && !useWindowOpen) {
    return context.roundState?.state === "racing" ? "Paused" : "Use during race";
  }
  if (player.item_uses.length >= (context.room?.max_round_item_uses ?? 0)) {
    return "Use limit reached";
  }
  if (
    player.round_item_spent_cents + inventoryItem.price_paid_cents >
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
  for (const section of ITEM_SHOP_SECTIONS) {
    const sectionItems = sortItemsByPrice(
      catalog.filter((item) => itemShopSection(item.kind) === section.key),
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
      grid.append(makeItemCard(item, player, context));
    }
    group.append(heading, grid);
    elements.itemMarket.append(group);
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
    const racerCount = context.roundState?.entries.length ?? 4;
    for (const use of player.item_uses) {
      elements.mySchemesList.append(renderItemUse(use, racerCount));
    }
  }
}

export function renderInventory(
  elements: ItemShopElements,
  player: LivePlayer,
  entries: RacerEntry[],
  potionWindowOpen: boolean,
  context: ItemShopContext,
): number | null {
  const maxInventory = context.playerInventoryCapacity(player);
  const requestedTarget =
    player.inventory.find((item) => item.id === context.targetingInventoryItemId) ?? null;
  const targetItem =
    requestedTarget !== null &&
    canUseInventoryItem(player, requestedTarget, potionWindowOpen, context)
      ? requestedTarget
      : null;
  const activeTargetId = targetItem?.id ?? null;

  elements.inventorySummary.textContent = `${player.inventory.length} / ${maxInventory} items`;
  elements.itemInventoryGrid.replaceChildren();
  for (const inventoryItem of player.inventory) {
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

    const useButton = document.createElement("button");
    useButton.type = "button";
    useButton.className = "inventory-item-use-button";
    useButton.textContent = inventoryUseLabel(player, inventoryItem, potionWindowOpen, context);
    useButton.disabled = !canUseInventoryItem(player, inventoryItem, potionWindowOpen, context);
    useButton.setAttribute("aria-label", `Use ${inventoryItem.item_name}`);
    useButton.addEventListener("click", () => {
      context.beginTargeting(inventoryItem.id);
    });

    card.append(trashButton, details, useButton);
    elements.itemInventoryGrid.append(card);
  }
  for (let slot = player.inventory.length; slot < maxInventory; slot += 1) {
    const empty = document.createElement("div");
    empty.className = "inventory-item-card inventory-item-card--empty";
    empty.setAttribute("aria-hidden", "true");
    empty.textContent = "Empty slot";
    elements.itemInventoryGrid.append(empty);
  }

  elements.itemTargetStep.hidden = targetItem === null;
  elements.itemTargetGrid.replaceChildren();
  if (targetItem !== null) {
    elements.itemTargetCopy.textContent = isTonicKind(targetItem.kind)
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
      elements.itemTargetGrid.append(targetButton);
    }
  }
  return activeTargetId;
}
