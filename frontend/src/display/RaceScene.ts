import Phaser from "phaser";

import {
  potionArtPath,
  potionLabel,
  WATER_POTION_ART_PATH,
} from "../shared/itemArt";
import {
  assertNever,
  isTonicKind,
  type ItemKind,
  type ItemUse,
  type LiveState,
  type RaceEffect,
  type RaceEvent,
  type RaceEventKind,
  type RacerEntry,
  type RacerFrame,
  type TimelineFrame,
  type TonicKind,
} from "../shared/types";

const WIDTH = 1280;
const HEIGHT = 720;
export const RACER_NAME_TAGS_EVENT = "racer-name-tags";

export interface RacerNameTag {
  racerId: number;
  name: string;
  x: number;
  y: number;
}

const TRACK_LEFT = 88;
const TRACK_RIGHT = 1192;
const TRACK_TOP = 310;
const TRACK_BOTTOM = 646;
const START_POSITION = 0.055;
const FINISH_POSITION = 0.945;
const DEFAULT_LANE_COUNT = 4;
const TONIC_KINDS: readonly TonicKind[] = [
  "speed_tonic",
  "guard_tonic",
  "trip_tonic",
  "confusion_tonic",
  "growth_tonic",
  "shrink_tonic",
  "transform_tonic",
];
const PERSISTENT_TONIC_KINDS = new Set<TonicKind>([
  "speed_tonic",
  "guard_tonic",
  "growth_tonic",
  "shrink_tonic",
  "transform_tonic",
]);

const ACTION_VFX: Partial<Record<RaceEventKind, { label: string; color: number }>> = {
  showboat: { label: "AIR AUTOGRAPH!", color: 0xffd85c },
  portal_hop: { label: "SUBSPACE HOP!", color: 0xc98cff },
  second_wind: { label: "SECOND WIND!", color: 0x7dff9a },
  evasive_juke: { label: "IMPOSSIBLE JUKE!", color: 0x7ec8ff },
  panic_sprint: { label: "SNACK SPRINT!", color: 0xff9f43 },
  turn_around: { label: "RIGHT WAY!", color: 0x7dff9a },
  potion_triggered: { label: "POTION POP!", color: 0xffd85c },
  potion_fizzled: { label: "FIZZLE!", color: 0xb8b8c8 },
};

type TrackItemKind = Exclude<ItemKind, TonicKind>;

const RACER_SHEETS = {
  skeleton: { frameWidth: 45, frameHeight: 51, frames: 4 },
  mushroom: { frameWidth: 26, frameHeight: 39, frames: 8 },
  goblin: { frameWidth: 38, frameHeight: 38, frames: 8 },
  "flying-eye": { frameWidth: 42, frameHeight: 33, frames: 8 },
  mimic: { frameWidth: 47, frameHeight: 34, frames: 6 },
  rat: { frameWidth: 59, frameHeight: 20, frames: 8 },
  slime: { frameWidth: 46, frameHeight: 20, frames: 6 },
  bat: { frameWidth: 67, frameHeight: 55, frames: 11 },
} as const;

interface RunnerVisual {
  entry: RacerEntry;
  container: Phaser.GameObjects.Container;
  shadow: Phaser.GameObjects.Ellipse;
  sprite: Phaser.GameObjects.Sprite;
  label: Phaser.GameObjects.Text;
  aura: Phaser.GameObjects.Ellipse;
  fallbackTexture: string;
  baseScale: number;
  activeSpriteKey: string;
}

interface PotionStaging {
  container: Phaser.GameObjects.Container;
  bottle: Phaser.GameObjects.Image;
  targetRacerId: number;
  slotOffset: number;
}

interface TrackProp {
  sprite: Phaser.GameObjects.Image;
  effectId: number;
}

function colorNumber(hex: string): number {
  return Number.parseInt(hex.replace("#", ""), 16);
}

function tonicTint(kind: ItemKind): number {
  switch (kind) {
    case "speed_tonic":
      return 0x7dff9a;
    case "guard_tonic":
      return 0x7ec8ff;
    case "trip_tonic":
      return 0xffb347;
    case "confusion_tonic":
      return 0xd98cff;
    case "growth_tonic":
      return 0xf5a340;
    case "shrink_tonic":
      return 0x73d9d0;
    case "transform_tonic":
      return 0xef79c5;
    case "banana":
    case "pothole":
    case "oil_slick":
    case "boost_pad":
    case "boxing_glove":
      return 0xffffff;
    default:
      return assertNever(kind);
  }
}

function frameForRacer(frame: TimelineFrame, racerId: number): RacerFrame | undefined {
  return frame.racers.find((racer) => racer.id === racerId);
}

export class RaceScene extends Phaser.Scene {
  private liveState: LiveState | null = null;
  private runners = new Map<number, RunnerVisual>();
  private trackProps = new Map<number, TrackProp>();
  private potionStagings: PotionStaging[] = [];
  private laneCount = DEFAULT_LANE_COUNT;
  private laneGraphics: Phaser.GameObjects.Rectangle[] = [];
  private playbackKey = "";
  private nextEventIndex = 0;
  private serverOffsetMs = 0;
  private reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  private trackLayer: Phaser.GameObjects.Container | null = null;

  constructor() {
    super("race");
  }

  preload(): void {
    this.load.image("track-arrow", "/static/assets/track/tile-0088.png");
    this.load.image("item-water-tonic", WATER_POTION_ART_PATH);
    this.load.spritesheet("fire-particles", "/static/assets/fire/smoke-fire.png", {
      frameWidth: 16,
      frameHeight: 16,
      endFrame: 15,
    });
    for (const kind of TONIC_KINDS) {
      const artPath = potionArtPath(kind);
      if (artPath !== null) {
        this.load.image(`item-${kind}`, artPath);
      }
    }
    for (const [key, metadata] of Object.entries(RACER_SHEETS)) {
      this.load.spritesheet(`sheet-${key}`, `/static/assets/racers/sheets/${key}.png`, {
        frameWidth: metadata.frameWidth,
        frameHeight: metadata.frameHeight,
        endFrame: metadata.frames - 1,
      });
    }
  }

  create(): void {
    this.generateItemTextures();
    this.createFireAnimation();
    this.drawVenue();
    this.game.events.on("live-state", this.receiveState, this);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      this.game.events.off("live-state", this.receiveState, this);
      this.game.events.emit(RACER_NAME_TAGS_EVENT, []);
    });
    const initial = this.registry.get("liveState") as LiveState | undefined;
    if (initial !== undefined) {
      this.receiveState(initial);
    }
  }

  update(time: number): void {
    const round = this.liveState?.round;
    if (round === null || round === undefined) {
      this.emitRacerNameTags();
      return;
    }

    if (round.state === "locked") {
      this.animateLocked(time);
      this.emitRacerNameTags();
      return;
    }

    if (round.state !== "racing" && round.state !== "results") {
      this.animateWaiting(time);
      this.clearTrackProps();
      this.clearPotionStagings();
      this.emitRacerNameTags();
      return;
    }

    const playback = round.race;
    if (playback === undefined || playback.timeline.length === 0) {
      this.emitRacerNameTags();
      return;
    }

    this.syncTrackEffects(playback.effects ?? [], round.item_uses);
    this.applyActiveAuras(
      playback.effects ?? [],
      new Set(playback.successful_effect_ids ?? []),
    );

    const elapsedMs =
      round.state === "results"
        ? (playback.duration_ticks / playback.tick_rate) * 1000
        : Math.max(0, Date.now() + this.serverOffsetMs - Date.parse(round.race_starts_at));
    const currentTick = Math.min(
      (elapsedMs / 1000) * playback.tick_rate,
      playback.duration_ticks,
    );
    const [currentFrame, nextFrame] = this.neighboringFrames(playback.timeline, currentTick);
    const frameDistance = Math.max(nextFrame.tick - currentFrame.tick, 1);
    const progress = Math.min(Math.max((currentTick - currentFrame.tick) / frameDistance, 0), 1);

    for (const entry of round.entries) {
      const current = frameForRacer(currentFrame, entry.racer_id);
      const next = frameForRacer(nextFrame, entry.racer_id) ?? current;
      const visual = this.runners.get(entry.racer_id);
      if (current === undefined || next === undefined || visual === undefined) {
        continue;
      }
      this.positionRunner(visual, current, next, progress, time);
    }
    this.emitRacerNameTags();
    this.emitReachedEvents(playback.events, currentTick);
  }

  private receiveState = (nextState: LiveState): void => {
    this.liveState = nextState;
    this.serverOffsetMs = Date.parse(nextState.server_time) - Date.now();
    const entries = nextState.round?.entries ?? [];
    const nextLaneCount = Math.max(entries.length, DEFAULT_LANE_COUNT);
    if (nextLaneCount !== this.laneCount) {
      this.laneCount = nextLaneCount;
      this.redrawLanes();
    }
    this.syncRunners(entries);
    this.emitRacerNameTags();

    const round = nextState.round;
    if (round?.state === "locked") {
      this.stageLockedPotions(round.item_uses, round.entries);
      this.syncTrackEffects([], round.item_uses);
    } else {
      this.clearPotionStagings();
    }

    const race = round?.race;
    const nextPlaybackKey =
      race === undefined || round === null ? "" : `${round.id}:${race.seed}`;
    if (nextPlaybackKey !== this.playbackKey) {
      this.playbackKey = nextPlaybackKey;
      this.nextEventIndex = 0;
      if (race !== undefined && round !== null) {
        const elapsedTicks =
          (Math.max(
            0,
            Date.now() + this.serverOffsetMs - Date.parse(round.race_starts_at),
          ) /
            1000) *
          race.tick_rate;
        this.nextEventIndex = race.events.findIndex((event) => event.tick >= elapsedTicks);
        if (this.nextEventIndex < 0) {
          this.nextEventIndex = race.events.length;
        }
      }
    }
  };

  private generateItemTextures(): void {
    const kinds: TrackItemKind[] = [
      "banana",
      "pothole",
      "oil_slick",
      "boost_pad",
      "boxing_glove",
    ];
    for (const kind of kinds) {
      const key = `item-${kind}`;
      if (this.textures.exists(key)) {
        continue;
      }
      const graphics = this.make.graphics({ x: 0, y: 0 });
      switch (kind) {
        case "banana": {
          graphics.fillStyle(0xf3bc3e);
          graphics.fillEllipse(16, 16, 24, 12);
          graphics.fillStyle(0xd4a017);
          graphics.fillEllipse(12, 18, 8, 6);
          graphics.fillStyle(0x18212b);
          graphics.fillRect(22, 10, 3, 6);
          break;
        }
        case "pothole": {
          graphics.fillStyle(0x3d2914);
          graphics.fillEllipse(16, 18, 28, 14);
          graphics.fillStyle(0x18212b);
          graphics.fillEllipse(16, 20, 18, 8);
          graphics.fillStyle(0x5a3d1e);
          graphics.fillRect(4, 8, 6, 4);
          graphics.fillRect(22, 6, 5, 4);
          break;
        }
        case "oil_slick": {
          graphics.fillStyle(0x18212b);
          graphics.fillEllipse(16, 19, 28, 12);
          graphics.fillStyle(0x526170);
          graphics.fillEllipse(11, 16, 10, 4);
          graphics.fillStyle(0x8a6ac8);
          graphics.fillEllipse(21, 21, 7, 3);
          break;
        }
        case "boost_pad": {
          graphics.fillStyle(0x1c6b45);
          graphics.fillRoundedRect(2, 8, 28, 18, 4);
          graphics.fillStyle(0x7dff9a);
          graphics.fillTriangle(6, 12, 15, 17, 6, 22);
          graphics.fillTriangle(15, 12, 25, 17, 15, 22);
          break;
        }
        case "boxing_glove": {
          graphics.fillStyle(0xef5b5b);
          graphics.fillCircle(13, 14, 8);
          graphics.fillCircle(21, 13, 7);
          graphics.fillRoundedRect(8, 16, 20, 10, 4);
          graphics.fillStyle(0x8f2630);
          graphics.fillRect(11, 25, 14, 5);
          break;
        }
        default:
          assertNever(kind);
      }
      graphics.generateTexture(key, 32, 32);
      graphics.destroy();
    }
  }

  private createFireAnimation(): void {
    if (this.anims.exists("fire-loop")) {
      return;
    }
    this.anims.create({
      key: "fire-loop",
      frames: this.anims.generateFrameNumbers("fire-particles", {
        start: 8,
        end: 11,
      }),
      frameRate: 9,
      repeat: -1,
    });
  }

  private drawVenue(): void {
    this.cameras.main.setBackgroundColor("#92c9d8");

    this.add.rectangle(
      WIDTH / 2,
      (TRACK_TOP + TRACK_BOTTOM) / 2,
      TRACK_RIGHT - TRACK_LEFT,
      TRACK_BOTTOM - TRACK_TOP,
      0xb97947,
    );
    this.add
      .rectangle(
        WIDTH / 2,
        (TRACK_TOP + TRACK_BOTTOM) / 2,
        TRACK_RIGHT - TRACK_LEFT,
        TRACK_BOTTOM - TRACK_TOP,
        0x000000,
        0,
      )
      .setStrokeStyle(5, 0x18212b);

    this.drawFirePits();
    this.trackLayer = this.add.container(0, 0);
    this.redrawLanes();

    this.drawDottedStartLine(this.trackX(START_POSITION));
    this.drawCheckeredFinishLine(this.trackX(FINISH_POSITION));
  }

  private drawFirePits(): void {
    const topEdge = this.trackY(0.1);
    const bottomEdge = this.trackY(0.9);
    const pitHeight = topEdge - TRACK_TOP;
    this.add
      .rectangle(
        WIDTH / 2,
        TRACK_TOP + pitHeight / 2,
        TRACK_RIGHT - TRACK_LEFT,
        pitHeight,
        0x351315,
      )
      .setDepth(3);
    this.add
      .rectangle(
        WIDTH / 2,
        bottomEdge + pitHeight / 2,
        TRACK_RIGHT - TRACK_LEFT,
        pitHeight,
        0x351315,
      )
      .setDepth(3);

    const flameCount = 34;
    for (let index = 0; index < flameCount; index += 1) {
      const x =
        TRACK_LEFT + 10 + index * ((TRACK_RIGHT - TRACK_LEFT - 20) / (flameCount - 1));
      const scale = 1.75 + (index % 3) * 0.16;
      const topFlame = this.add
        .sprite(x, topEdge - 13 + (index % 2) * 2, "fire-particles", 8)
        .setScale(scale)
        .setFlipX(index % 2 === 0)
        .setDepth(4);
      const bottomFlame = this.add
        .sprite(x, bottomEdge + 13 - (index % 2) * 2, "fire-particles", 8)
        .setScale(scale)
        .setFlipX(index % 2 !== 0)
        .setDepth(4);
      if (this.reducedMotion) {
        topFlame.setFrame(8 + (index % 4));
        bottomFlame.setFrame(8 + ((index + 2) % 4));
      } else {
        topFlame.play("fire-loop");
        bottomFlame.play("fire-loop");
        topFlame.anims.setProgress((index % 4) / 4);
        bottomFlame.anims.setProgress(((index + 2) % 4) / 4);
      }
    }

    for (const [y, label] of [
      [TRACK_TOP + pitHeight / 2, "FIRE PIT"],
      [bottomEdge + pitHeight / 2, "FIRE PIT"],
    ] as const) {
      this.add
        .text(WIDTH / 2, y, label, {
          color: "#fff1bd",
          fontFamily: "Arial Rounded MT Bold, sans-serif",
          fontSize: "18px",
          fontStyle: "bold",
          letterSpacing: 7,
          stroke: "#351315",
          strokeThickness: 4,
        })
        .setOrigin(0.5)
        .setDepth(5);
    }
  }

  private redrawLanes(): void {
    for (const line of this.laneGraphics) {
      line.destroy();
    }
    this.laneGraphics = [];
    if (this.trackLayer !== null) {
      this.trackLayer.removeAll(true);
    }

    for (let boundary = 0; boundary <= this.laneCount; boundary += 1) {
      const normalized = (boundary + 0.5) / (this.laneCount + 1);
      const y = this.trackY(normalized);
      const line = this.add.rectangle(
        WIDTH / 2,
        y,
        TRACK_RIGHT - TRACK_LEFT,
        boundary === 0 || boundary === this.laneCount ? 5 : 2,
        0xffefd0,
        boundary === 0 || boundary === this.laneCount ? 1 : 0.55,
      );
      line.setDepth(1);
      this.laneGraphics.push(line);
    }
    for (let lane = 0; lane < this.laneCount; lane += 1) {
      const arrow = this.add
        .image(WIDTH / 2, this.trackY(this.laneNormalized(lane + 1)), "track-arrow")
        .setScale(2)
        .setAlpha(0.24)
        .setDepth(2);
      this.trackLayer?.add(arrow);
    }
  }

  private drawDottedStartLine(x: number): void {
    const segmentHeight = 12;
    const gap = 10;
    for (let y = TRACK_TOP; y < TRACK_BOTTOM; y += segmentHeight + gap) {
      const height = Math.min(segmentHeight, TRACK_BOTTOM - y);
      this.add
        .rectangle(x, y + height / 2, 4, height, 0xfff8e7)
        .setDepth(2);
    }
  }

  private drawCheckeredFinishLine(x: number): void {
    const cellSize = 14;
    const rows = Math.ceil((TRACK_BOTTOM - TRACK_TOP) / cellSize);
    for (let row = 0; row < rows; row += 1) {
      for (let column = 0; column < 2; column += 1) {
        this.add
          .rectangle(
            x - cellSize / 2 + column * cellSize,
            TRACK_TOP + cellSize / 2 + row * cellSize,
            cellSize,
            cellSize,
            (row + column) % 2 === 0 ? 0xfff8e7 : 0x18212b,
          )
          .setDepth(2);
      }
    }
  }

  private syncRunners(entries: RacerEntry[]): void {
    const wanted = new Set(entries.map((entry) => entry.racer_id));
    for (const [racerId, visual] of this.runners) {
      if (!wanted.has(racerId)) {
        visual.container.destroy(true);
        this.textures.remove(visual.fallbackTexture);
        this.runners.delete(racerId);
      }
    }
    for (const entry of entries) {
      if (!this.runners.has(entry.racer_id)) {
        this.runners.set(entry.racer_id, this.createRunner(entry));
      }
    }
  }

  private emitRacerNameTags(): void {
    const tags: RacerNameTag[] = [];
    for (const [racerId, visual] of this.runners) {
      tags.push({
        racerId,
        name: visual.entry.name,
        x: visual.container.x / WIDTH,
        y: (visual.container.y + visual.label.y) / HEIGHT,
      });
    }
    this.game.events.emit(RACER_NAME_TAGS_EVENT, tags);
  }

  private createRunner(entry: RacerEntry): RunnerVisual {
    const fallbackTexture = `fallback-racer-${entry.racer_id}`;
    if (!this.textures.exists(fallbackTexture)) {
      const graphics = this.make.graphics({ x: 0, y: 0 });
      const color = colorNumber(entry.color);
      graphics.fillStyle(0x18212b);
      graphics.fillRect(10, 20, 44, 35);
      graphics.fillStyle(color);
      graphics.fillRect(13, 16, 38, 34);
      graphics.fillRect(20, 8, 24, 16);
      graphics.fillStyle(0xfff8e7);
      graphics.fillRect(24, 13, 6, 7);
      graphics.fillRect(36, 13, 6, 7);
      graphics.fillStyle(0x18212b);
      graphics.fillRect(26, 15, 3, 4);
      graphics.fillRect(38, 15, 3, 4);
      graphics.fillRect(15, 50, 12, 7);
      graphics.fillRect(38, 50, 12, 7);
      graphics.generateTexture(fallbackTexture, 64, 60);
      graphics.destroy();
    }

    const textureKey = this.textures.exists(`sheet-${entry.sprite_key}`)
      ? `sheet-${entry.sprite_key}`
      : fallbackTexture;
    const shadow = this.add.ellipse(0, 20, 64, 18, 0x18212b, 0.28);
    const aura = this.add.ellipse(0, -2, 72, 72, 0xffffff, 0);
    aura.setStrokeStyle(3, 0xffffff, 0);
    const sprite = this.add.sprite(0, -2, textureKey, 0);
    const sourceWidth = sprite.width || 64;
    const sourceHeight = sprite.height || 60;
    const baseScale = Math.min(82 / sourceWidth, 70 / sourceHeight);
    sprite.setScale(baseScale);
    const animationKey = this.ensureRunAnimation(entry.sprite_key);
    if (animationKey !== null) {
      sprite.play(animationKey);
    }
    const label = this.add
      .text(0, -54, entry.name, {
        backgroundColor: "#18212b",
        color: "#fff8e7",
        fontFamily: "Arial Rounded MT Bold, sans-serif",
        fontSize: "13px",
        fontStyle: "bold",
        padding: { x: 6, y: 3 },
      })
      .setOrigin(0.5, 1)
      .setVisible(false);
    const laneNorm = this.laneNormalized(entry.lane);
    const container = this.add.container(this.trackX(0.055), this.trackY(laneNorm), [
      shadow,
      aura,
      sprite,
      label,
    ]);
    container.setDepth(10 + entry.lane);
    return {
      entry,
      container,
      shadow,
      sprite,
      label,
      aura,
      fallbackTexture,
      baseScale,
      activeSpriteKey: entry.sprite_key,
    };
  }

  private laneNormalized(lane: number): number {
    return lane / (this.laneCount + 1);
  }

  private ensureRunAnimation(spriteKey: string): string | null {
    const metadata = RACER_SHEETS[spriteKey as keyof typeof RACER_SHEETS];
    const textureKey = `sheet-${spriteKey}`;
    if (metadata === undefined || !this.textures.exists(textureKey)) {
      return null;
    }
    const animationKey = `run-${spriteKey}`;
    if (!this.anims.exists(animationKey)) {
      this.anims.create({
        key: animationKey,
        frames: this.anims.generateFrameNumbers(textureKey, {
          start: 0,
          end: metadata.frames - 1,
        }),
        frameRate: spriteKey === "skeleton" ? 7 : 10,
        repeat: -1,
      });
    }
    return animationKey;
  }

  private setRunnerAppearance(visual: RunnerVisual, spriteKey: string): void {
    if (visual.activeSpriteKey === spriteKey) {
      return;
    }
    const textureKey = `sheet-${spriteKey}`;
    if (!this.textures.exists(textureKey)) {
      return;
    }
    visual.sprite.stop();
    visual.sprite.setTexture(textureKey, 0);
    visual.baseScale = Math.min(
      82 / (visual.sprite.width || 64),
      70 / (visual.sprite.height || 60),
    );
    visual.activeSpriteKey = spriteKey;
    const animationKey = this.ensureRunAnimation(spriteKey);
    if (animationKey !== null) {
      visual.sprite.play(animationKey);
    }
  }

  private animateWaiting(time: number): void {
    for (const visual of this.runners.values()) {
      this.setRunnerAppearance(visual, visual.entry.sprite_key);
      const laneNorm = this.laneNormalized(visual.entry.lane);
      visual.container.x = this.trackX(0.055);
      visual.container.y =
        this.trackY(laneNorm) +
        (this.reducedMotion ? 0 : Math.sin(time / 240 + visual.entry.lane) * 3);
      visual.sprite.setAngle(0);
      visual.sprite.setFlipX(false);
      visual.sprite.setTint(0xffffff);
      visual.sprite.setAlpha(1);
      visual.sprite.x = 0;
      visual.sprite.y = -2;
      visual.sprite.setScale(visual.baseScale);
      visual.label.y = -54;
      visual.aura.setAlpha(0);
      const animationKey = `run-${visual.activeSpriteKey}`;
      if (this.anims.exists(animationKey)) {
        if (visual.sprite.anims.currentAnim?.key !== animationKey) {
          visual.sprite.play(animationKey);
        } else if (visual.sprite.anims.isPaused) {
          visual.sprite.anims.resume();
        }
      }
      visual.shadow.setScale(1, 1);
      visual.shadow.setAlpha(1);
    }
  }

  private animateLocked(time: number): void {
    this.animateWaiting(time);
    for (const staging of this.potionStagings) {
      const visual = this.runners.get(staging.targetRacerId);
      if (visual === undefined) {
        continue;
      }
      const sip = this.reducedMotion ? 0.5 : (Math.sin(time / 260) + 1) / 2;
      staging.container.x =
        visual.container.x + 36 - sip * 22 + staging.slotOffset;
      staging.container.y = visual.container.y - 8 - sip * 10;
      const bob = this.reducedMotion ? 0 : Math.sin(time / 180) * 4;
      staging.bottle.y = bob;
      staging.bottle.setAngle(15 + sip * 55);
      visual.sprite.setScale(visual.baseScale * (1 + sip * 0.04));
    }
  }

  private stageLockedPotions(itemUses: ItemUse[], entries: RacerEntry[]): void {
    this.clearPotionStagings();
    for (const entry of entries) {
      const tonicKinds: TonicKind[] = [];
      for (const use of itemUses) {
        if (use.target_racer_id === entry.racer_id && isTonicKind(use.kind)) {
          tonicKinds.push(use.kind);
        }
      }
      const stagedKinds: Array<TonicKind | null> =
        tonicKinds.length === 0 ? [null] : tonicKinds.slice(-3);
      stagedKinds.forEach((kind, index) => {
        const textureKey = kind === null ? "item-water-tonic" : `item-${kind}`;
        const bottle = this.add.image(0, 0, textureKey).setScale(2.8);
        const label = this.add
          .text(0, -32, kind === null ? "WATER" : potionLabel(kind), {
            backgroundColor: "#18212b",
            color: "#fff8e7",
            fontFamily: "Arial Rounded MT Bold, sans-serif",
            fontSize: "14px",
            fontStyle: "bold",
            padding: { x: 5, y: 3 },
          })
          .setOrigin(0.5);
        const container = this.add.container(0, 0, [bottle, label]);
        container.setDepth(50 + index);
        this.potionStagings.push({
          container,
          bottle,
          targetRacerId: entry.racer_id,
          slotOffset: (index - (stagedKinds.length - 1) / 2) * 28,
        });
      });
    }
  }

  private clearPotionStagings(): void {
    for (const staging of this.potionStagings) {
      staging.container.destroy(true);
    }
    this.potionStagings = [];
  }

  private syncTrackEffects(effects: RaceEffect[], itemUses: ItemUse[]): void {
    const trackItems = [
      ...effects.filter((effect) => effect.lane !== undefined),
      ...itemUses
        .filter((use) => use.track_lane !== null)
        .map(
          (use): RaceEffect => ({
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
          }),
        ),
    ];

    const wantedIds = new Set(trackItems.map((item) => item.id));
    for (const [id, prop] of this.trackProps) {
      if (!wantedIds.has(id)) {
        prop.sprite.destroy();
        this.trackProps.delete(id);
      }
    }

    for (const effect of trackItems) {
      if (effect.lane === undefined) {
        continue;
      }
      if (this.trackProps.has(effect.id)) {
        continue;
      }
      const textureKey = `item-${effect.kind}`;
      const sprite = this.add
        .image(
          this.trackX(effect.position ?? 0.55),
          this.trackY(effect.lane),
          textureKey,
        )
        .setScale(
          effect.kind === "pothole"
            ? 1.8
            : effect.kind === "boxing_glove"
              ? 1.65
              : 1.4,
        )
        .setDepth(5);
      sprite.setTint(colorNumber(effect.item_color || "#ffffff"));
      this.trackProps.set(effect.id, { sprite, effectId: effect.id });
    }
  }

  private clearTrackProps(): void {
    for (const prop of this.trackProps.values()) {
      prop.sprite.destroy();
    }
    this.trackProps.clear();
  }

  private applyActiveAuras(effects: RaceEffect[], successfulEffectIds: Set<number>): void {
    const auraByRacer = new Map<number, ItemKind>();
    for (const effect of effects) {
      if (
        effect.target_racer_id !== undefined &&
        successfulEffectIds.has(effect.id) &&
        isTonicKind(effect.kind) &&
        PERSISTENT_TONIC_KINDS.has(effect.kind)
      ) {
        auraByRacer.set(effect.target_racer_id, effect.kind);
      }
    }

    for (const visual of this.runners.values()) {
      const kind = auraByRacer.get(visual.entry.racer_id);
      if (kind === undefined) {
        visual.aura.setAlpha(0);
        visual.sprite.setTint(0xffffff);
        continue;
      }
      const tint = tonicTint(kind);
      visual.sprite.setTint(tint);
      visual.aura.setFillStyle(tint, 0.18);
      visual.aura.setStrokeStyle(2, tint, 0.55);
      visual.aura.setAlpha(1);
    }
  }

  private positionRunner(
    visual: RunnerVisual,
    current: RacerFrame,
    next: RacerFrame,
    progress: number,
    time: number,
  ): void {
    const x = Phaser.Math.Linear(current.x, next.x, progress);
    const y = Phaser.Math.Linear(current.y, next.y, progress);
    const visualScale = Phaser.Math.Linear(current.scale, next.scale, progress);
    this.setRunnerAppearance(visual, current.sprite_key);
    visual.container.x = this.trackX(x);
    visual.container.y = this.trackY(y);
    visual.sprite.setFlipX(current.facing < 0);
    visual.sprite.setAlpha(1);
    visual.sprite.setScale(visual.baseScale * visualScale);
    visual.sprite.setAngle(current.rotation);
    visual.sprite.x = 0;
    visual.label.y = -54 - Math.max(visualScale - 1, 0) * 34;
    visual.shadow.setScale(visualScale, visualScale);
    visual.shadow.setAlpha(1);
    const animationKey = `run-${visual.activeSpriteKey}`;

    switch (current.state) {
      case "running":
      case "backwards": {
        if (this.anims.exists(animationKey)) {
          if (visual.sprite.anims.currentAnim?.key !== animationKey) {
            visual.sprite.play(animationKey);
          } else if (visual.sprite.anims.isPaused) {
            visual.sprite.anims.resume();
          }
        }
        const bob = this.reducedMotion ? 0 : Math.sin(time / 65 + visual.entry.lane) * 4;
        visual.sprite.y = -2 + bob;
        visual.sprite.setAngle(current.rotation + (this.reducedMotion ? 0 : bob * 0.7));
        break;
      }
      case "fallen":
        visual.sprite.anims.pause();
        visual.sprite.y = 13;
        visual.sprite.x = this.reducedMotion ? 0 : Math.sin(time / 95) * 3;
        visual.sprite.setAngle(
          current.rotation + (this.reducedMotion ? 0 : Math.sin(time / 110) * 5),
        );
        visual.shadow.setScale(1.25 * visualScale, 0.75 * visualScale);
        break;
      case "finished": {
        if (this.anims.exists(animationKey)) {
          if (visual.sprite.anims.currentAnim?.key !== animationKey) {
            visual.sprite.play(animationKey);
          } else if (visual.sprite.anims.isPaused) {
            visual.sprite.anims.resume();
          }
        }
        const bounce = this.reducedMotion ? 0 : Math.abs(Math.sin(time / 120)) * 10;
        visual.sprite.y = -2 - bounce;
        break;
      }
      case "knocked_out":
        visual.sprite.anims.pause();
        visual.sprite.y = 13;
        visual.sprite.setAngle(current.rotation);
        visual.sprite.setTint(0x9da4aa);
        break;
      case "destroyed":
        visual.sprite.anims.pause();
        visual.sprite.y = 14;
        visual.sprite.setAngle(current.rotation);
        visual.sprite.setTint(0x2c1714);
        visual.sprite.setAlpha(0.3);
        visual.sprite.setScale(visual.baseScale * visualScale * 0.5);
        visual.shadow.setScale(0.55 * visualScale, 0.4 * visualScale);
        visual.shadow.setAlpha(0.25);
        break;
      case "dnf":
        visual.sprite.anims.pause();
        visual.sprite.y = 10;
        visual.sprite.setAngle(current.rotation || 90);
        visual.sprite.setAlpha(0.65);
        break;
      default:
        assertNever(current.state);
    }
  }

  private neighboringFrames(
    timeline: TimelineFrame[],
    tick: number,
  ): [TimelineFrame, TimelineFrame] {
    let low = 0;
    let high = timeline.length - 1;
    while (low < high) {
      const middle = Math.ceil((low + high) / 2);
      const candidate = timeline[middle];
      if (candidate !== undefined && candidate.tick <= tick) {
        low = middle;
      } else {
        high = middle - 1;
      }
    }
    const current = timeline[low] ?? timeline[0];
    const next = timeline[Math.min(low + 1, timeline.length - 1)] ?? current;
    if (current === undefined || next === undefined) {
      throw new Error("Race timeline cannot be empty.");
    }
    return [current, next];
  }

  private spawnActionVfx(event: RaceEvent): void {
    const style = ACTION_VFX[event.kind];
    const visual = this.runners.get(event.racer_id);
    if (style === undefined || visual === undefined) {
      return;
    }

    const ring = this.add.ellipse(0, 10, 76, 38, style.color, 0.16);
    ring.setStrokeStyle(4, style.color, 0.95);
    const label = this.add
      .text(0, -28, style.label, {
        backgroundColor: "#18212b",
        color: "#fff8e7",
        fontFamily: "Arial Rounded MT Bold, sans-serif",
        fontSize: "16px",
        fontStyle: "bold",
        padding: { x: 7, y: 4 },
      })
      .setOrigin(0.5);
    const marker = this.add.container(visual.container.x, visual.container.y - 42, [
      ring,
      label,
    ]);
    marker.setDepth(90);

    if (this.reducedMotion) {
      this.time.delayedCall(650, () => marker.destroy(true));
      return;
    }
    this.tweens.add({
      targets: ring,
      scaleX: 1.65,
      scaleY: 1.65,
      alpha: 0,
      duration: 850,
      ease: "Quad.Out",
    });
    this.tweens.add({
      targets: marker,
      y: marker.y - 34,
      alpha: 0,
      duration: 900,
      ease: "Quad.Out",
      onComplete: () => marker.destroy(true),
    });
  }

  private emitReachedEvents(events: RaceEvent[], currentTick: number): void {
    while (this.nextEventIndex < events.length) {
      const event = events[this.nextEventIndex];
      if (event === undefined || event.tick > currentTick) {
        break;
      }
      this.spawnActionVfx(event);
      this.game.events.emit("race-event", event);
      this.nextEventIndex += 1;
    }
  }

  private trackX(normalized: number): number {
    return Phaser.Math.Linear(TRACK_LEFT, TRACK_RIGHT, normalized);
  }

  private trackY(normalized: number): number {
    return Phaser.Math.Linear(TRACK_TOP, TRACK_BOTTOM, normalized);
  }
}
