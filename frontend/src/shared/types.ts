import type { ItemKind } from "./itemCatalog";

type RoundState = "open" | "locked" | "racing" | "results";
export type ReplayPreference = "ask" | "always_watch" | "always_skip";

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
  record: RacerPerformanceRecord;
}

interface RacerPerformanceRecord {
  starts: number;
  wins: number;
  losses: number;
  dnfs: number;
  win_rate: number;
}

export interface PlayerBettingRecord {
  winning_bets: number;
  losing_bets: number;
  total_bets: number;
  total_staked_cents: number;
  total_returned_cents: number;
  net_cents: number;
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
  track_items?: TrackItemFrame[];
}

export interface TrackItemFrame {
  id: number;
  x: number;
  y: number;
  active: boolean;
}

export type RaceEventKind =
  | "stumble"
  | "wrong_way"
  | "lane_drift"
  | "body_check"
  | "pileup"
  | "recover"
  | "knockout"
  | "finish"
  | "timeout"
  | "potion_used"
  | "potion_triggered"
  | "potion_fizzled"
  | "obstacle_hit"
  | "obstacle_removed"
  | "item_cleared"
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
  finish_place?: number | null;
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
  generated_at?: string | null;
  tick_rate: number;
  duration_ticks: number;
  timeline: TimelineFrame[];
  events: RaceEvent[];
  effects?: RaceEffect[];
  successful_effect_ids?: number[];
  failed_effect_ids?: number[];
}

export type ReplayClipKind = "incident" | "finish" | "house_win";

export interface ReplayMontageClip {
  id: string;
  kind: ReplayClipKind;
  anchor_tick: number;
  start_tick: number;
  end_tick: number;
  playback_rate: number;
  caption: string;
  focus_racer_ids: number[];
  event_kind: RaceEventKind | null;
  effect_id: number | null;
  consumed_effect_ids_at_start: number[];
  timeline: TimelineFrame[];
  events: RaceEvent[];
}

export type ReplayShowStageKind =
  | "intro"
  | "clip"
  | "betting_spotlight"
  | "world_record_celebration"
  | "podium"
  | "interview_question"
  | "interview_answer"
  | "potion_callout"
  | "potion_response"
  | "outro";

export interface ReplayShowSpeaker {
  kind: "host" | "racer";
  name: string;
  racer_id: number | null;
  sprite_key: string | null;
}

export interface ReplayShowRacer {
  racer_id: number;
  name: string;
  slug: string;
  sprite_key: string;
  color: string;
  finish_place: number | null;
  dnf_reason: string;
}

export interface BettingSpotlightPerson {
  player_id: number;
  nickname: string;
  avatar_url: string;
  bet_count: number;
  staked_cents: number;
  returned_cents: number;
  net_cents: number;
}

export interface RoundBettingSpotlight {
  bet_count: number;
  player_count: number;
  highest_gain: BettingSpotlightPerson | null;
  highest_loss: BettingSpotlightPerson | null;
  host_focus: "gain" | "loss" | "both" | "none";
}

export interface NewWorldRecord {
  metric: string;
  label: string;
  description: string;
  value: number;
  display_value: string;
  racer_id: number;
  racer_name: string;
  racer_slug: string;
  sprite_key: string;
  color: string;
  round_number: number;
  previous_racer_name: string | null;
  previous_display_value: string | null;
}

export interface WinnerPotion {
  effect_id: number;
  kind: ItemKind;
  item_name: string;
  item_icon: string;
  item_color: string;
  buyer: string;
  activation_tick: number | null;
  trigger_event_kind: string | null;
  trigger_tick: number | null;
  successful: true;
}

export interface ReplayShowStage {
  id: string;
  kind: ReplayShowStageKind;
  offset_ms: number;
  duration_ms: number;
  visual_duration_ms: number;
  speaker: ReplayShowSpeaker;
  caption: string;
  detail: string;
  clip_id?: string;
  clip_index?: number;
  clip_count?: number;
  record_beat?: "intro" | "shoutout" | "finale";
  record_index?: number;
  record_count?: number;
  betting_spotlight?: RoundBettingSpotlight;
  world_record?: NewWorldRecord;
  winner?: ReplayShowRacer | null;
  question_kind?: string;
  potion?: WinnerPotion;
}

export interface ReplayStageManifest {
  id: string;
  kind: ReplayShowStageKind;
  offset_ms: number;
  duration_ms: number;
  clip_id?: string;
  clip_index?: number;
  record_beat?: "intro" | "shoutout" | "finale";
}

export interface ReplayMontage {
  version: number;
  playback_key: string;
  tick_rate: number;
  duration_ticks: number;
  prompt_seconds: number;
  total_playback_ms: number;
  total_show_ms: number;
  show_started_at: string;
  show_ends_at: string;
  prompt_ends_at: string;
  playback_ends_at: string;
  podium_ends_at: string;
  clips: ReplayMontageClip[];
  effects: RaceEffect[];
  successful_effect_ids: number[];
  failed_effect_ids: number[];
  stages: ReplayShowStage[];
  betting_spotlight: RoundBettingSpotlight | null;
  new_world_records: NewWorldRecord[];
  winner_potion: WinnerPotion | null;
}

export interface ReplayManifest {
  available: boolean;
  version?: number;
  playback_key?: string;
  clip_count?: number;
  prompt_seconds?: number;
  total_playback_ms?: number;
  total_show_ms?: number;
  show_started_at?: string | null;
  show_ends_at?: string | null;
  stages?: ReplayStageManifest[];
  prompt_ends_at?: string | null;
  playback_ends_at?: string | null;
  podium_ends_at?: string | null;
}

interface RaceResult {
  finish_order?: number[];
  physical_finish_order?: number[];
  finish_ticks?: Record<string, number>;
  identity_racer_ids?: Record<string, number>;
  first_finish_tick?: number | null;
  finish_deadline_tick?: number | null;
  dnf?: Array<{ racer_id: number; reason: string }>;
  house_wins?: boolean;
}

type ItemTarget = "racer" | "track";

export interface ItemDefinition {
  slug: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  price_cents: number;
  discount_pct: number;
  effective_price_cents: number;
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

type UpgradeKind = "inventory_capacity";

export interface UpgradeDefinition {
  slug: string;
  name: string;
  description: string;
  kind: UpgradeKind;
  inventory_capacity: number | null;
  price_cents: number;
  prerequisite_slug: string | null;
}

interface OwnedUpgrade {
  slug: string;
  name: string;
  kind: UpgradeKind;
  inventory_capacity: number | null;
  price_paid_cents: number;
  purchased_at: string;
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
  current_price_cents: number;
  takeover_count: number;
  nickname: string;
  is_online: boolean;
  acquired_at: string;
}

export interface SeatMarket {
  seat_slug: string;
  current_price_cents: number;
  takeover_count: number;
}

export interface LeaderboardRow {
  rank: number;
  nickname: string;
  balance_cents: number;
  wins: number;
  total_bets: number;
  betting_record: PlayerBettingRecord;
}

interface LedgerRow {
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
  seat_markets: SeatMarket[];
  result: RaceResult;
  replay?: ReplayManifest;
  display_replay?: ReplayMontage;
  race?: RacePlayback;
}

interface PlayerBet {
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

interface TrackMedicWound {
  index: number;
  x: number;
  y: number;
  patched: boolean;
}

interface TrackMedicSession {
  id: number;
  round_id: number;
  completed: boolean;
  target: {
    race_entry_id: number;
    racer_id: number;
    racer_name: string;
    sprite_key: string;
    portrait_url: string;
  };
  wounds: TrackMedicWound[];
  patched_count: number;
  wound_count: number;
  reward_cents: number;
}

export interface TrackMedicState {
  eligible: boolean;
  session: TrackMedicSession | null;
  stale: boolean;
}

export interface LivePlayer {
  id: number;
  nickname: string;
  avatar_recipe: AvatarRecipe;
  avatar_version: string;
  avatar_url: string;
  replay_preference: ReplayPreference;
  balance_cents: number;
  round_staked_cents: number;
  round_stake_remaining_cents: number;
  round_item_spent_cents: number;
  bets: PlayerBet[];
  inventory: InventoryItem[];
  item_uses: ItemUse[];
  seat_claim: SeatClaim | null;
  owned_upgrades: OwnedUpgrade[];
  effective_inventory_capacity: number;
  next_inventory_upgrade: UpgradeDefinition | null;
  recent_ledger: LedgerRow[];
  betting_record: PlayerBettingRecord;
  track_medic: TrackMedicState;
}

export interface LiveState {
  protocol_version: 18;
  server_time: string;
  room: {
    name: string;
    is_paused: boolean;
    broadcast_enabled: boolean;
    betting_seconds: number;
    max_round_stake_cents: number;
    max_inventory_items: number;
    max_round_item_spend_cents: number;
    max_round_item_uses: number;
    item_catalog: ItemDefinition[];
    seat_catalog: SeatDefinition[];
    upgrade_catalog: UpgradeDefinition[];
  };
  round: LiveRound | null;
  show_round: LiveRound | null;
  player: LivePlayer | null;
  leaderboard: LeaderboardRow[];
  debt_board: LeaderboardRow[];
}

type StateEventName =
  | "round.opened"
  | "round.locked"
  | "race.started"
  | "race.finished"
  | "broadcast.finished"
  | "bets.updated"
  | "items.updated"
  | "seats.updated"
  | "upgrades.updated"
  | "bailout.updated";

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
