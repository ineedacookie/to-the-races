import { isTonicKind, shouldDespawnTrackItemOnHit } from "../shared/itemCatalog";
import type { ItemUse, RaceEffect, RaceEvent } from "../shared/types";

function itemUseEffect(use: ItemUse): RaceEffect {
  return {
    id: use.id,
    kind: use.kind,
    item_name: use.item_name,
    item_icon: use.item_icon,
    item_color: use.item_color,
    buyer: use.buyer,
    lane: use.track_lane ?? undefined,
    position: use.track_position ?? undefined,
    activation_tick: use.activation_tick,
    strength: 1,
  };
}

export function activeTrackItemEffects(
  effects: readonly RaceEffect[],
  itemUses: readonly ItemUse[],
  currentTick: number,
  consumedEffectIds: ReadonlySet<number>,
): RaceEffect[] {
  const active = new Map<number, RaceEffect>();
  const candidates = [
    ...effects.filter((effect) => effect.lane !== undefined),
    ...itemUses.filter((use) => use.track_lane !== null).map(itemUseEffect),
  ];
  for (const effect of candidates) {
    if (
      effect.lane === undefined ||
      isTonicKind(effect.kind) ||
      effect.activation_tick > currentTick ||
      consumedEffectIds.has(effect.id) ||
      active.has(effect.id)
    ) {
      continue;
    }
    active.set(effect.id, effect);
  }
  return [...active.values()];
}

export function consumedTrackEffectId(
  event: RaceEvent,
  effects: readonly RaceEffect[],
): number | null {
  if (event.effect_id === undefined) {
    return null;
  }
  const effect = effects.find((candidate) => candidate.id === event.effect_id);
  if (effect === undefined || isTonicKind(effect.kind)) {
    return null;
  }
  if (event.kind === "obstacle_hit") {
    return shouldDespawnTrackItemOnHit(effect.kind) ? effect.id : null;
  }
  if (
    event.kind === "obstacle_removed" ||
    event.kind === "item_cleared" ||
    event.kind === "destroyed"
  ) {
    return effect.id;
  }
  return null;
}
