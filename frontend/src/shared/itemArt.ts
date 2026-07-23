import { assertNever, type ItemKind, type TonicKind } from "./types";

const POTION_ROOT = "/static/assets/items/potions";

export const EMPTY_POTION_ART_PATH = `${POTION_ROOT}/empty.png`;

export function potionArtPath(kind: ItemKind): string | null {
  switch (kind) {
    case "speed_tonic":
      return `${POTION_ROOT}/blue.png`;
    case "guard_tonic":
      return `${POTION_ROOT}/green.png`;
    case "trip_tonic":
      return `${POTION_ROOT}/red.png`;
    case "confusion_tonic":
      return `${POTION_ROOT}/purple.png`;
    case "banana":
    case "pothole":
      return null;
    default:
      return assertNever(kind);
  }
}

export function potionLabel(kind: TonicKind): string {
  switch (kind) {
    case "speed_tonic":
      return "SPEED";
    case "guard_tonic":
      return "GUARD";
    case "trip_tonic":
      return "TRIP";
    case "confusion_tonic":
      return "CONFUSION";
    default:
      return assertNever(kind);
  }
}
