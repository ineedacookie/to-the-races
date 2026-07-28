import Phaser from "phaser";

import {
  isTonicKind,
  shouldDespawnTrackItemOnHit,
  type ItemKind,
  type TonicKind,
  type TrackItemKind,
} from "../shared/itemCatalog";
import {
  assertNever,
  type RaceEffect,
  type RaceEvent,
  type RaceEventKind,
} from "../shared/types";

export interface FinishLineCell {
  sprite: Phaser.GameObjects.Rectangle;
  baseColor: number;
}

interface RacerVfxAnchor {
  container: Phaser.GameObjects.Container;
}

export interface TrackPropAnchor {
  sprite: Phaser.GameObjects.Image;
  effectId: number;
  kind: TrackItemKind;
}

const ACTION_VFX: Partial<Record<RaceEventKind, { label: string; color: number }>> = {
  showboat: { label: "AIR AUTOGRAPH!", color: 0xffd85c },
  portal_hop: { label: "SUBSPACE HOP!", color: 0xc98cff },
  evasive_juke: { label: "IMPOSSIBLE JUKE!", color: 0x7ec8ff },
  panic_sprint: { label: "SNACK SPRINT!", color: 0xff9f43 },
  turn_around: { label: "RIGHT WAY!", color: 0x7dff9a },
};

const EVENT_KIND_TO_ITEM: Partial<Record<RaceEventKind, ItemKind>> = {
  portal_hop: "portal_gate",
  second_wind: "second_wind",
};

function resolveItemKindFromEvent(
  event: RaceEvent,
  effects: readonly RaceEffect[],
): ItemKind | null {
  if (event.effect_id !== undefined) {
    const effect = effects.find((candidate) => candidate.id === event.effect_id);
    if (effect !== undefined) {
      return effect.kind;
    }
  }
  return EVENT_KIND_TO_ITEM[event.kind] ?? null;
}

export function createFireAnimation(scene: Phaser.Scene): void {
  if (scene.anims.exists("fire-loop")) {
    return;
  }
  scene.anims.create({
    key: "fire-loop",
    frames: scene.anims.generateFrameNumbers("fire-particles", {
      start: 8,
      end: 11,
    }),
    frameRate: 9,
    repeat: -1,
  });
}

export function createFinishFireworksAnimation(scene: Phaser.Scene): void {
  if (scene.anims.exists("finish-fireworks")) {
    return;
  }
  scene.anims.create({
    key: "finish-fireworks",
    frames: scene.anims.generateFrameNumbers("finish-fireworks-sheet", {
      start: 0,
      end: 29,
    }),
    frameRate: 20,
    repeat: 0,
  });
}

export function spawnActionVfx(
  scene: Phaser.Scene,
  event: RaceEvent,
  runners: ReadonlyMap<number, RacerVfxAnchor>,
  reducedMotion: boolean,
): void {
  const style = ACTION_VFX[event.kind];
  const visual = runners.get(event.racer_id);
  if (style === undefined || visual === undefined) {
    return;
  }

  const ring = scene.add.ellipse(0, 10, 76, 38, style.color, 0.16);
  ring.setStrokeStyle(4, style.color, 0.95);
  const label = scene.add
    .text(0, -28, style.label, {
      backgroundColor: "#18212b",
      color: "#fff8e7",
      fontFamily: "Arial Rounded MT Bold, sans-serif",
      fontSize: "16px",
      fontStyle: "bold",
      padding: { x: 7, y: 4 },
    })
    .setOrigin(0.5);
  const marker = scene.add.container(visual.container.x, visual.container.y - 42, [
    ring,
    label,
  ]);
  marker.setDepth(90);

  if (reducedMotion) {
    scene.time.delayedCall(650, () => marker.destroy(true));
    return;
  }
  scene.tweens.add({
    targets: ring,
    scaleX: 1.65,
    scaleY: 1.65,
    alpha: 0,
    duration: 850,
    ease: "Quad.Out",
  });
  scene.tweens.add({
    targets: marker,
    y: marker.y - 34,
    alpha: 0,
    duration: 900,
    ease: "Quad.Out",
    onComplete: () => marker.destroy(true),
  });
}

function burstAt(
  scene: Phaser.Scene,
  x: number,
  y: number,
  color: number,
  reducedMotion: boolean,
  count = 10,
): void {
  for (let index = 0; index < count; index += 1) {
    const size = Phaser.Math.Between(3, 7);
    const particle = scene.add
      .rectangle(x, y, size, size, color)
      .setDepth(88);
    if (reducedMotion) {
      scene.time.delayedCall(420, () => particle.destroy());
      continue;
    }
    scene.tweens.add({
      targets: particle,
      x: x + Phaser.Math.Between(-36, 36),
      y: y + Phaser.Math.Between(-36, 36),
      alpha: 0,
      duration: Phaser.Math.Between(350, 650),
      onComplete: () => particle.destroy(),
    });
  }
}

function ringPulse(
  scene: Phaser.Scene,
  x: number,
  y: number,
  color: number,
  reducedMotion: boolean,
  size = 64,
): void {
  const ring = scene.add.ellipse(x, y, size, size * 0.55, color, 0.2).setDepth(87);
  ring.setStrokeStyle(3, color, 0.9);
  if (reducedMotion) {
    scene.time.delayedCall(500, () => ring.destroy());
    return;
  }
  scene.tweens.add({
    targets: ring,
    scaleX: 2,
    scaleY: 2,
    alpha: 0,
    duration: 700,
    onComplete: () => ring.destroy(),
  });
}

function spawnDeployVfx(
  scene: Phaser.Scene,
  prop: TrackPropAnchor,
  reducedMotion: boolean,
): void {
  const { x, y } = prop.sprite;
  switch (prop.kind) {
    case "detour_sign":
    case "stop_sign":
    case "rock_wall":
      ringPulse(scene, x, y, 0xf3bc3e, reducedMotion);
      break;
    case "glass_door":
    case "portal_gate":
    case "magnet_mine":
    case "springboard":
    case "speed_bump":
    case "roomba_vacuum":
    case "banana":
    case "pothole":
    case "oil_slick":
    case "boost_pad":
    case "boxing_glove":
      ringPulse(scene, x, y, 0xffffff, reducedMotion, 48);
      break;
    default:
      assertNever(prop.kind);
  }
}

function spawnTrackHitVfx(
  scene: Phaser.Scene,
  kind: TrackItemKind,
  x: number,
  y: number,
  reducedMotion: boolean,
): void {
  switch (kind) {
    case "glass_door":
      burstAt(scene, x, y, 0xc8e8ff, reducedMotion, reducedMotion ? 6 : 14);
      burstAt(scene, x, y, 0xffffff, reducedMotion, reducedMotion ? 4 : 8);
      break;
    case "magnet_mine":
      ringPulse(scene, x, y, 0x4080ff, reducedMotion);
      for (let index = 0; index < (reducedMotion ? 2 : 5); index += 1) {
        const spark = scene.add.circle(x, y, 4, 0xff4040).setDepth(88);
        if (reducedMotion) {
          scene.time.delayedCall(400, () => spark.destroy());
          continue;
        }
        scene.tweens.add({
          targets: spark,
          x: x + Phaser.Math.Between(-28, 28),
          y: y + Phaser.Math.Between(-28, 28),
          alpha: 0,
          duration: 450,
          onComplete: () => spark.destroy(),
        });
      }
      break;
    case "portal_gate":
      ringPulse(scene, x, y, 0xc98cff, reducedMotion, 72);
      break;
    case "springboard":
      ringPulse(scene, x, y, 0x7dff9a, reducedMotion);
      break;
    case "roomba_vacuum":
      ringPulse(scene, x, y, 0xb8b8c8, reducedMotion, 80);
      break;
    case "detour_sign":
    case "stop_sign":
    case "rock_wall":
    case "speed_bump":
    case "banana":
    case "pothole":
    case "oil_slick":
    case "boost_pad":
    case "boxing_glove":
      burstAt(scene, x, y, 0xfff8e7, reducedMotion, reducedMotion ? 4 : 8);
      break;
    default:
      assertNever(kind);
  }
}

function spawnTonicVfx(
  scene: Phaser.Scene,
  kind: TonicKind,
  visual: RacerVfxAnchor,
  reducedMotion: boolean,
): void {
  const { x, y } = visual.container;
  switch (kind) {
    case "fireproof_tonic":
      ringPulse(scene, x, y - 8, 0xff9040, reducedMotion, 78);
      burstAt(scene, x, y - 8, 0xffd040, reducedMotion, reducedMotion ? 5 : 10);
      break;
    case "nitro_serum":
      ringPulse(scene, x, y, 0xfff040, reducedMotion);
      burstAt(scene, x, y, 0xff8040, reducedMotion, reducedMotion ? 6 : 12);
      break;
    case "recovery_brew":
      ringPulse(scene, x, y, 0xff90c0, reducedMotion);
      burstAt(scene, x, y, 0xffffff, reducedMotion, reducedMotion ? 4 : 8);
      break;
    case "ghost_draught":
      ringPulse(scene, x, y, 0xd0e8ff, reducedMotion, 70);
      if (!reducedMotion) {
        scene.tweens.add({
          targets: visual.container,
          alpha: 0.45,
          duration: 180,
          yoyo: true,
          repeat: 2,
        });
      }
      break;
    case "second_wind":
      ringPulse(scene, x, y, 0x7dff9a, reducedMotion, 82);
      burstAt(scene, x, y, 0x7ec8ff, reducedMotion, reducedMotion ? 4 : 8);
      break;
    case "phoenix_flask":
      ringPulse(scene, x, y, 0xff9040, reducedMotion, 90);
      burstAt(scene, x, y, 0xffd040, reducedMotion, reducedMotion ? 8 : 16);
      break;
    case "speed_tonic":
    case "guard_tonic":
    case "trip_tonic":
    case "confusion_tonic":
    case "growth_tonic":
    case "shrink_tonic":
    case "transform_tonic":
      ringPulse(scene, x, y, 0xffd85c, reducedMotion, 60);
      break;
    default:
      assertNever(kind);
  }
}

export function spawnItemEventVfx(
  scene: Phaser.Scene,
  event: RaceEvent,
  effects: readonly RaceEffect[],
  runners: ReadonlyMap<number, RacerVfxAnchor>,
  trackProps: ReadonlyMap<number, TrackPropAnchor>,
  reducedMotion: boolean,
): void {
  const itemKind = resolveItemKindFromEvent(event, effects);
  const visual = runners.get(event.racer_id);

  switch (event.kind) {
    case "obstacle_hit": {
      if (itemKind !== null && !isTonicKind(itemKind)) {
        const prop =
          event.effect_id !== undefined ? trackProps.get(event.effect_id) : undefined;
        const x = prop?.sprite.x ?? visual?.container.x ?? 0;
        const y = prop?.sprite.y ?? visual?.container.y ?? 0;
        spawnTrackHitVfx(scene, itemKind, x, y, reducedMotion);
      }
      break;
    }
    case "obstacle_removed":
    case "item_cleared":
    case "destroyed": {
      if (event.effect_id !== undefined) {
        const prop = trackProps.get(event.effect_id);
        if (prop !== undefined && prop.kind === "roomba_vacuum") {
          ringPulse(scene, prop.sprite.x, prop.sprite.y, 0xb8b8c8, reducedMotion, 96);
        }
      }
      break;
    }
    case "potion_triggered":
    case "potion_fizzled": {
      if (itemKind !== null && isTonicKind(itemKind) && visual !== undefined) {
        spawnTonicVfx(scene, itemKind, visual, reducedMotion);
      }
      break;
    }
    case "portal_hop": {
      if (visual !== undefined) {
        ringPulse(scene, visual.container.x, visual.container.y, 0xc98cff, reducedMotion, 86);
        burstAt(scene, visual.container.x, visual.container.y, 0xffffff, reducedMotion, reducedMotion ? 4 : 8);
      }
      break;
    }
    case "second_wind": {
      if (visual !== undefined) {
        spawnTonicVfx(scene, "second_wind", visual, reducedMotion);
      }
      break;
    }
    case "recover": {
      if (itemKind === "phoenix_flask" && visual !== undefined) {
        spawnTonicVfx(scene, "phoenix_flask", visual, reducedMotion);
      } else if (itemKind === "recovery_brew" && visual !== undefined) {
        spawnTonicVfx(scene, "recovery_brew", visual, reducedMotion);
      }
      break;
    }
    case "panic_sprint": {
      if (itemKind === "nitro_serum" && visual !== undefined) {
        spawnTonicVfx(scene, "nitro_serum", visual, reducedMotion);
      }
      break;
    }
    case "stumble":
    case "wrong_way":
    case "lane_drift":
    case "body_check":
    case "pileup":
    case "knockout":
    case "finish":
    case "timeout":
    case "potion_used":
    case "showboat":
    case "evasive_juke":
    case "turn_around":
      break;
    default:
      assertNever(event.kind);
  }
}

export function applyTrackItemLifecycle(
  event: RaceEvent,
  effects: readonly RaceEffect[],
  trackProps: Map<number, TrackPropAnchor>,
): void {
  const itemKind = resolveItemKindFromEvent(event, effects);
  const effectId = event.effect_id;

  if (effectId === undefined || itemKind === null || isTonicKind(itemKind)) {
    return;
  }

  if (event.kind === "obstacle_hit") {
    if (shouldDespawnTrackItemOnHit(itemKind)) {
      const prop = trackProps.get(effectId);
      prop?.sprite.destroy();
      trackProps.delete(effectId);
    }
    return;
  }
  if (
    event.kind === "obstacle_removed" ||
    event.kind === "item_cleared" ||
    event.kind === "destroyed"
  ) {
    const prop = trackProps.get(effectId);
    prop?.sprite.destroy();
    trackProps.delete(effectId);
  }
}

export function notifyTrackPropSpawned(
  scene: Phaser.Scene,
  prop: TrackPropAnchor,
  reducedMotion: boolean,
): void {
  if (
    prop.kind === "detour_sign" ||
    prop.kind === "stop_sign" ||
    prop.kind === "rock_wall" ||
    prop.kind === "glass_door"
  ) {
    spawnDeployVfx(scene, prop, reducedMotion);
  }
}

function spawnFinishFireworks(
  scene: Phaser.Scene,
  {
    finishX,
    trackTop,
    trackBottom,
    reducedMotion,
  }: {
    finishX: number;
    trackTop: number;
    trackBottom: number;
    reducedMotion: boolean;
  },
): void {
  const burstCount = reducedMotion ? 1 : 3;
  for (let index = 0; index < burstCount; index += 1) {
    const firework = scene.add
      .sprite(
        finishX + Phaser.Math.Between(-180, 40),
        Phaser.Math.Between(trackTop + 60, trackBottom - 60),
        "finish-fireworks-sheet",
      )
      .setDepth(100)
      .setScale(0.55);
    if (reducedMotion) {
      firework.setFrame(23);
      scene.time.delayedCall(500, () => firework.destroy());
      continue;
    }
    firework.once(Phaser.Animations.Events.ANIMATION_COMPLETE, () => firework.destroy());
    firework.play("finish-fireworks");
  }
}

function flashFinishLine(
  scene: Phaser.Scene,
  cells: FinishLineCell[],
  reducedMotion: boolean,
): void {
  const flashColor = 0xf3bc3e;
  for (const cell of cells) {
    cell.sprite.setFillStyle(flashColor);
  }
  const restore = (): void => {
    for (const cell of cells) {
      cell.sprite.setFillStyle(cell.baseColor);
    }
  };
  if (reducedMotion) {
    scene.time.delayedCall(220, restore);
    return;
  }
  scene.tweens.add({
    targets: cells.map((cell) => cell.sprite),
    alpha: { from: 1, to: 0.55 },
    duration: 120,
    yoyo: true,
    repeat: 2,
    onComplete: restore,
  });
}

export function playFirstFinisherVfx(
  scene: Phaser.Scene,
  options: {
    finishX: number;
    trackTop: number;
    trackBottom: number;
    finishLineCells: FinishLineCell[];
    reducedMotion: boolean;
  },
): void {
  spawnFinishFireworks(scene, options);
  flashFinishLine(scene, options.finishLineCells, options.reducedMotion);
}

export function trackItemScale(kind: TrackItemKind): number {
  switch (kind) {
    case "pothole":
      return 1.8;
    case "boxing_glove":
      return 1.65;
    case "rock_wall":
      return 1.75;
    case "glass_door":
      return 1.55;
    case "portal_gate":
      return 1.5;
    case "roomba_vacuum":
      return 1.45;
    case "banana":
    case "oil_slick":
    case "boost_pad":
    case "detour_sign":
    case "speed_bump":
    case "stop_sign":
    case "springboard":
    case "magnet_mine":
      return 1.4;
    default:
      return assertNever(kind);
  }
}
