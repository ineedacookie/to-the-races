import { renderEmptyState } from "../shared/dom";
import { formatMoney } from "../shared/format";
import { purchaseActionLabel } from "../shared/liveUi";
import type { LivePlayer, UpgradeDefinition } from "../shared/types";

export interface UpgradeMarketElements {
  upgradeGrid: HTMLElement;
}

export interface UpgradeMarketContext {
  pendingUpgrades: ReadonlySet<string>;
  buyUpgrade: (upgrade: UpgradeDefinition) => void;
}

function makeUpgradeCard(
  upgrade: UpgradeDefinition,
  player: LivePlayer,
  ownedSlugs: ReadonlySet<string>,
  context: UpgradeMarketContext,
): HTMLElement {
  const card = document.createElement("article");
  card.className = "upgrade-card";
  const owned = ownedSlugs.has(upgrade.slug);
  const missingPrerequisite =
    upgrade.prerequisite_slug !== null &&
    !ownedSlugs.has(upgrade.prerequisite_slug);
  const canAfford = player.balance_cents >= upgrade.price_cents;

  const icon = document.createElement("span");
  icon.className = "upgrade-card__icon";
  icon.textContent = "🎒";
  icon.setAttribute("aria-hidden", "true");

  const title = document.createElement("h3");
  title.textContent = upgrade.name;
  const perk = document.createElement("span");
  perk.className = "upgrade-card__perk";
  perk.textContent =
    upgrade.inventory_capacity === null
      ? "Permanent upgrade"
      : `${upgrade.inventory_capacity} item slots`;
  const desc = document.createElement("p");
  desc.textContent = upgrade.description;
  const price = document.createElement("p");
  price.className = "upgrade-card__price";
  price.textContent = owned ? "Owned permanently" : formatMoney(upgrade.price_cents);

  const buyButton = document.createElement("button");
  buyButton.type = "button";
  buyButton.className = "upgrade-buy-btn";
  buyButton.textContent = purchaseActionLabel({
    pending: context.pendingUpgrades.has(upgrade.slug),
    pendingAction: "Buying",
    blockedLabel: owned ? "Owned" : missingPrerequisite ? "Requires prior tier" : undefined,
    requiredCents: canAfford ? undefined : upgrade.price_cents,
    actionLabel: `Buy · ${formatMoney(upgrade.price_cents)}`,
  });
  buyButton.disabled =
    owned || missingPrerequisite || !canAfford || context.pendingUpgrades.has(upgrade.slug);
  buyButton.setAttribute("aria-label", `Buy ${upgrade.name}`);
  buyButton.addEventListener("click", () => {
    context.buyUpgrade(upgrade);
  });

  card.append(icon, title, perk, desc, price, buyButton);
  return card;
}

export function renderUpgradeMarket(
  elements: UpgradeMarketElements,
  player: LivePlayer,
  catalog: UpgradeDefinition[],
  context: UpgradeMarketContext,
): void {
  elements.upgradeGrid.replaceChildren();
  if (catalog.length === 0) {
    renderEmptyState(elements.upgradeGrid, "Permanent upgrades will appear here soon.");
    return;
  }
  const ownedSlugs = new Set(player.owned_upgrades.map((upgrade) => upgrade.slug));
  for (const upgrade of catalog) {
    elements.upgradeGrid.append(makeUpgradeCard(upgrade, player, ownedSlugs, context));
  }
}
