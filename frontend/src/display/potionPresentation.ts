import { isTonicKind, type TonicKind } from "../shared/itemCatalog";
import type {
  ItemUse,
  RaceEffect,
  RaceEvent,
  RaceEventKind,
} from "../shared/types";

const TONIC_COLORS: Record<TonicKind, number> = {
  speed_tonic: 0x7dff9a,
  guard_tonic: 0x7ec8ff,
  trip_tonic: 0xffb347,
  confusion_tonic: 0xd98cff,
  growth_tonic: 0xf5a340,
  shrink_tonic: 0x73d9d0,
  transform_tonic: 0xef79c5,
  fireproof_tonic: 0xff9040,
  nitro_serum: 0xfff040,
  recovery_brew: 0xff90c0,
  ghost_draught: 0xd0e8ff,
  second_wind: 0x7dff9a,
  phoenix_flask: 0xffb040,
  invincibility_tonic: 0xf8f2a0,
  berserk_tonic: 0xff4050,
};

const AURA_TONIC_KINDS = new Set<TonicKind>([
  "speed_tonic",
  "guard_tonic",
  "growth_tonic",
  "shrink_tonic",
  "transform_tonic",
  "fireproof_tonic",
  "ghost_draught",
  "nitro_serum",
  "invincibility_tonic",
  "berserk_tonic",
]);

const PRIVATE_POTION_EVENT_KINDS = new Set<RaceEventKind>([
  "potion_used",
  "potion_triggered",
  "potion_fizzled",
]);

export function mixedTonicColor(kinds: readonly TonicKind[]): number | null {
  if (kinds.length === 0) {
    return null;
  }
  const totals = kinds.reduce(
    (color, kind) => {
      const tint = TONIC_COLORS[kind];
      color.red += (tint >> 16) & 0xff;
      color.green += (tint >> 8) & 0xff;
      color.blue += tint & 0xff;
      return color;
    },
    { red: 0, green: 0, blue: 0 },
  );
  const red = Math.round(totals.red / kinds.length);
  const green = Math.round(totals.green / kinds.length);
  const blue = Math.round(totals.blue / kinds.length);
  return (red << 16) | (green << 8) | blue;
}

export function mixedDrinkColor(itemUses: readonly ItemUse[], racerId: number): number | null {
  const kinds = itemUses.flatMap((use) =>
    use.target_racer_id === racerId && isTonicKind(use.kind) ? [use.kind] : [],
  );
  return mixedTonicColor(kinds);
}

export function activeAuraColors(
  effects: readonly RaceEffect[],
  successfulEffectIds: ReadonlySet<number>,
): Map<number, number> {
  const kindsByRacer = new Map<number, TonicKind[]>();
  for (const effect of effects) {
    if (
      effect.target_racer_id === undefined ||
      !successfulEffectIds.has(effect.id) ||
      !isTonicKind(effect.kind) ||
      !AURA_TONIC_KINDS.has(effect.kind)
    ) {
      continue;
    }
    const kinds = kindsByRacer.get(effect.target_racer_id) ?? [];
    kinds.push(effect.kind);
    kindsByRacer.set(effect.target_racer_id, kinds);
  }

  const colors = new Map<number, number>();
  for (const [racerId, kinds] of kindsByRacer) {
    const color = mixedTonicColor(kinds);
    if (color !== null) {
      colors.set(racerId, color);
    }
  }
  return colors;
}

export function shouldAnnounceRaceEvent(
  event: RaceEvent,
  effects: readonly RaceEffect[],
): boolean {
  if (PRIVATE_POTION_EVENT_KINDS.has(event.kind)) {
    return false;
  }
  if (event.effect_id === undefined) {
    return true;
  }
  const effect = effects.find((candidate) => candidate.id === event.effect_id);
  return effect === undefined || !isTonicKind(effect.kind);
}
