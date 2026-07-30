const POTION_ROOT = "/static/assets/items/potions";
const TRACK_ROOT = "/static/assets/items/track";

export type ItemShopSection = "positive" | "negative" | "neutral" | "live";

const ITEM_METADATA = {
  speed_tonic: {
    family: "tonic",
    section: "positive",
    artPath: `${POTION_ROOT}/blue.png`,
  },
  guard_tonic: {
    family: "tonic",
    section: "positive",
    artPath: `${POTION_ROOT}/green.png`,
  },
  trip_tonic: {
    family: "tonic",
    section: "negative",
    artPath: `${POTION_ROOT}/red.png`,
  },
  confusion_tonic: {
    family: "tonic",
    section: "negative",
    artPath: `${POTION_ROOT}/purple.png`,
  },
  growth_tonic: {
    family: "tonic",
    section: "neutral",
    artPath: `${POTION_ROOT}/growth.png`,
  },
  shrink_tonic: {
    family: "tonic",
    section: "neutral",
    artPath: `${POTION_ROOT}/shrink.png`,
  },
  transform_tonic: {
    family: "tonic",
    section: "neutral",
    artPath: `${POTION_ROOT}/transform.png`,
  },
  fireproof_tonic: {
    family: "tonic",
    section: "positive",
    artPath: `${POTION_ROOT}/fireproof.png`,
  },
  nitro_serum: {
    family: "tonic",
    section: "neutral",
    artPath: `${POTION_ROOT}/nitro.png`,
  },
  recovery_brew: {
    family: "tonic",
    section: "positive",
    artPath: `${POTION_ROOT}/recovery.png`,
  },
  ghost_draught: {
    family: "tonic",
    section: "positive",
    artPath: `${POTION_ROOT}/ghost.png`,
  },
  second_wind: {
    family: "tonic",
    section: "positive",
    artPath: `${POTION_ROOT}/second_wind.png`,
  },
  phoenix_flask: {
    family: "tonic",
    section: "positive",
    artPath: `${POTION_ROOT}/phoenix.png`,
  },
  invincibility_tonic: {
    family: "tonic",
    section: "positive",
    artPath: `${POTION_ROOT}/fireproof.png`,
  },
  berserk_tonic: {
    family: "tonic",
    section: "negative",
    artPath: `${POTION_ROOT}/red.png`,
  },
  banana: { family: "track", section: "live", artPath: `${TRACK_ROOT}/banana.png` },
  pothole: { family: "track", section: "live", artPath: `${TRACK_ROOT}/pothole.png` },
  oil_slick: { family: "track", section: "live", artPath: `${TRACK_ROOT}/oil_slick.png` },
  boost_pad: { family: "track", section: "live", artPath: `${TRACK_ROOT}/boost_pad.png` },
  boxing_glove: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/boxing_glove.png`,
    despawnOnHit: true,
  },
  detour_sign: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/detour_sign.png`,
  },
  speed_bump: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/speed_bump.png`,
  },
  stop_sign: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/stop_sign.png`,
    despawnOnHit: true,
  },
  glass_door: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/glass_door.png`,
  },
  rock_wall: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/rock_wall.png`,
  },
  roomba_vacuum: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/roomba_vacuum.png`,
  },
  springboard: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/springboard.png`,
  },
  magnet_mine: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/magnet_mine.png`,
    despawnOnHit: true,
  },
  portal_gate: {
    family: "track",
    section: "live",
    artPath: `${TRACK_ROOT}/portal_gate.png`,
    despawnOnHit: true,
  },
} as const;

export type ItemKind = keyof typeof ITEM_METADATA;
export type TonicKind = {
  [Kind in ItemKind]: (typeof ITEM_METADATA)[Kind]["family"] extends "tonic" ? Kind : never;
}[ItemKind];
export type TrackItemKind = Exclude<ItemKind, TonicKind>;

export const ALL_ITEM_KINDS = Object.keys(ITEM_METADATA) as ItemKind[];

export function isTonicKind(kind: ItemKind): kind is TonicKind {
  return ITEM_METADATA[kind].family === "tonic";
}

export function itemShopSection(kind: ItemKind): ItemShopSection {
  return ITEM_METADATA[kind].section;
}

export function itemArtPath(kind: ItemKind): string {
  return ITEM_METADATA[kind].artPath;
}

export function shouldDespawnTrackItemOnHit(kind: TrackItemKind): boolean {
  const metadata = ITEM_METADATA[kind];
  return "despawnOnHit" in metadata && metadata.despawnOnHit;
}

export const WATER_POTION_ART_PATH = `${POTION_ROOT}/water.png`;
