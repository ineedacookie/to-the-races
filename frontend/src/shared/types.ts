export type RoundState = "open" | "locked" | "racing" | "results";

export interface RacerEntry {
  id: number;
  racer_id: number;
  name: string;
  slug: string;
  sprite_key: string;
  color: string;
  lane: number;
  odds: string;
  tagline: string;
  backstory: string;
  total_staked_cents: number;
  finish_place: number | null;
  dnf_reason: string;
}

export interface RacerFrame {
  id: number;
  x: number;
  y: number;
  state:
    | "running"
    | "backwards"
    | "fallen"
    | "finished"
    | "knocked_out"
    | "destroyed"
    | "dnf";
  facing: 1 | -1;
  rotation: number;
  scale: number;
  sprite_key: string;
  place: number | null;
}

export interface TimelineFrame {
  tick: number;
  racers: RacerFrame[];
}

export type RaceEventKind =
  | "start"
  | "stumble"
  | "wrong_way"
  | "lane_drift"
  | "body_check"
  | "stomp"
  | "pileup"
  | "recover"
  | "knockout"
  | "finish"
  | "timeout"
  | "potion_used"
  | "potion_triggered"
  | "potion_fizzled"
  | "obstacle_hit"
  | "destroyed"
  | "showboat"
  | "portal_hop"
  | "second_wind"
  | "evasive_juke"
  | "panic_sprint"
  | "turn_around";

export interface RaceEvent {
  tick: number;
  kind: RaceEventKind;
  racer_id: number;
  target_id?: number;
  effect_id?: number;
  message: string;
}

export interface RaceEffect {
  id: number;
  kind: ItemKind;
  item_name: string;
  item_icon: string;
  item_color: string;
  buyer: string;
  target_racer_id?: number;
  lane?: number;
  position?: number;
  activation_tick: number;
  strength: number;
}

export interface RacePlayback {
  seed: number;
  tick_rate: number;
  duration_ticks: number;
  timeline: TimelineFrame[];
  events: RaceEvent[];
  effects?: RaceEffect[];
  successful_effect_ids?: number[];
  failed_effect_ids?: number[];
}

export interface RaceResult {
  finish_order?: number[];
  physical_finish_order?: number[];
  finish_ticks?: Record<string, number>;
  identity_racer_ids?: Record<string, number>;
  first_finish_tick?: number | null;
  finish_deadline_tick?: number | null;
  dnf?: Array<{ racer_id: number; reason: string }>;
  house_wins?: boolean;
}

export type ItemKind =
  | "speed_tonic"
  | "guard_tonic"
  | "trip_tonic"
  | "confusion_tonic"
  | "growth_tonic"
  | "shrink_tonic"
  | "transform_tonic"
  | "banana"
  | "pothole"
  | "oil_slick"
  | "boost_pad"
  | "boxing_glove";

export type TonicKind = Extract<ItemKind, `${string}_tonic`>;

export type ItemTarget = "racer" | "track";

export interface ItemDefinition {
  slug: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  price_cents: number;
  payout_bonus_bps: number;
  effect_strength: number;
  kind: ItemKind;
  target: ItemTarget;
}

export interface InventoryItem {
  id: number;
  item_slug: string;
  item_name: string;
  description: string;
  item_icon: string;
  item_color: string;
  kind: ItemKind;
  target: ItemTarget;
  price_paid_cents: number;
  purchased_at: string;
}

export interface ItemUse {
  id: number;
  buyer: string;
  item_slug: string;
  item_name: string;
  item_icon: string;
  item_color: string;
  kind: ItemKind;
  target_entry_id: number | null;
  target_racer_id: number | null;
  target_racer_name: string | null;
  track_lane: number | null;
  track_position: number | null;
  activation_tick: number;
  price_paid_cents: number;
  created_at: string;
}

export interface SeatDefinition {
  slug: string;
  name: string;
  description: string;
  sprite_key: string;
  color: string;
  price_cents: number;
  payout_bonus_bps: number;
}

export interface SeatClaim {
  id: number;
  player_id: number;
  seat_slug: string;
  seat_name: string;
  seat_description: string;
  sprite_key: string;
  seat_color: string;
  payout_bonus_bps: number;
  price_paid_cents: number;
  nickname: string;
  created_at: string;
}

export interface LeaderboardRow {
  rank: number;
  nickname: string;
  balance_cents: number;
  wins: number;
  total_bets: number;
}

export interface LedgerRow {
  id: number;
  kind: string;
  amount_cents: number;
  balance_after_cents: number;
  description: string;
  created_at: string;
}

export interface LiveRound {
  id: number;
  number: number;
  state: RoundState;
  opened_at: string;
  locks_at: string;
  race_starts_at: string;
  race_ends_at: string;
  results_end_at: string;
  finish_countdown_starts_at: string | null;
  finish_countdown_ends_at: string | null;
  entries: RacerEntry[];
  item_uses: ItemUse[];
  seats: SeatClaim[];
  result: RaceResult;
  race?: RacePlayback;
}

export interface PlayerBet {
  id: number;
  racer_name: string;
  racer_id: number;
  amount_cents: number;
  odds: string;
  status: "pending" | "won" | "lost" | "void";
  payout_cents: number;
}

export type AvatarLayer = "skin" | "eyes" | "bottoms" | "tops" | "shoes" | "hair";
export type AvatarRecipe = Record<AvatarLayer, number>;

export interface LivePlayer {
  id: number;
  nickname: string;
  avatar_recipe: AvatarRecipe;
  avatar_version: string;
  avatar_url: string;
  balance_cents: number;
  round_staked_cents: number;
  round_item_spent_cents: number;
  bets: PlayerBet[];
  inventory: InventoryItem[];
  item_uses: ItemUse[];
  seat_claim: SeatClaim | null;
  recent_ledger: LedgerRow[];
}

export interface LiveState {
  protocol_version: 10;
  server_time: string;
  room: {
    name: string;
    is_paused: boolean;
    max_inventory_items: number;
    max_round_item_spend_cents: number;
    max_round_item_uses: number;
    item_catalog: ItemDefinition[];
    seat_catalog: SeatDefinition[];
  };
  round: LiveRound | null;
  player: LivePlayer | null;
  leaderboard: LeaderboardRow[];
  debt_board: LeaderboardRow[];
}

export type StateEventName =
  | "round.opened"
  | "round.locked"
  | "race.started"
  | "race.finished"
  | "bets.updated"
  | "items.updated"
  | "seats.updated";

export type AudienceReactionKind = "cheer" | "boo" | "cry" | "shout";

export interface ConnectedSpectator {
  player_id: number;
  nickname: string;
  avatar_version: string;
}

export interface AudienceReaction {
  player_id: number;
  kind: AudienceReactionKind;
  nickname: string;
  text: string;
  racer_id: number | null;
  seat_name: string;
  seat_color: string;
  display_ms?: number;
  at: string;
}

export type ServerMessage =
  | { type: "state.sync"; state: LiveState }
  | { type: StateEventName; state: LiveState }
  | { type: "balance.updated"; balance_cents: number }
  | { type: "presence.sync"; spectators: ConnectedSpectator[] }
  | { type: "presence.join"; spectator: ConnectedSpectator }
  | { type: "presence.leave"; player_id: number }
  | { type: "audience.reaction"; reaction: AudienceReaction }
  | { type: "audience.rejected"; message: string }
  | { type: "pong" };

export function assertNever(value: never): never {
  throw new Error(`Unhandled variant: ${String(value)}`);
}

export function isTonicKind(kind: ItemKind): kind is TonicKind {
  switch (kind) {
    case "speed_tonic":
    case "guard_tonic":
    case "trip_tonic":
    case "confusion_tonic":
    case "growth_tonic":
    case "shrink_tonic":
    case "transform_tonic":
      return true;
    case "banana":
    case "pothole":
    case "oil_slick":
    case "boost_pad":
    case "boxing_glove":
      return false;
    default:
      return assertNever(kind);
  }
}
