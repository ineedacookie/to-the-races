import { itemArtPath } from "../shared/itemCatalog";
import {
  interpolatedRacerFrame,
  interpolatedTrackItemFrame,
} from "../shared/racePlayback";
import {
  racerAnimationFrame,
  racerSheetMetadata,
  racerSheetPath,
} from "../shared/racerSprites";
import type {
  RaceEffect,
  RaceEvent,
  RaceEventKind,
  RacerEntry,
  RacerFrame,
  ReplayMontage,
  ReplayMontageClip,
} from "../shared/types";

const WIDTH = 960;
const HEIGHT = 540;
const TRACK_LEFT = 52;
const TRACK_RIGHT = 908;
const TRACK_TOP = 112;
const TRACK_BOTTOM = 448;
const START_POSITION = 0.055;
const FINISH_POSITION = 0.945;
const BASE_RACER_WIDTH = 72;
const BASE_RACER_HEIGHT = 64;

const TERMINAL_ALPHA: Record<RacerFrame["state"], number> = {
  running: 1,
  backwards: 1,
  fallen: 1,
  finished: 0.78,
  knocked_out: 0.48,
  destroyed: 0.32,
  dnf: 0.4,
};

const SHAKE_STRENGTH: Partial<Record<RaceEventKind, number>> = {
  body_check: 7,
  pileup: 11,
  knockout: 12,
  destroyed: 14,
  obstacle_hit: 9,
  stumble: 5,
  finish: 4,
};

interface LoadedAssets {
  racers: Map<string, HTMLImageElement>;
  items: Map<number, HTMLImageElement>;
}

export interface ReplayCanvasRenderer {
  load: (montage: ReplayMontage, entries: readonly RacerEntry[]) => Promise<void>;
  play: (
    clip: ReplayMontageClip,
    montage: ReplayMontage,
    entries: readonly RacerEntry[],
    reducedMotion: boolean,
    options?: {
      offsetMs?: number;
      durationMs?: number;
    },
  ) => Promise<void>;
  stop: () => void;
  dispose: () => void;
}

function loadImage(source: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const image = new Image();
    image.decoding = "async";
    image.addEventListener("load", () => resolve(image), { once: true });
    image.addEventListener("error", () => resolve(null), { once: true });
    image.src = source;
  });
}

function trackX(normalized: number): number {
  return TRACK_LEFT + normalized * (TRACK_RIGHT - TRACK_LEFT);
}

function trackY(normalized: number): number {
  return TRACK_TOP + normalized * (TRACK_BOTTOM - TRACK_TOP);
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
}

export function replayTickForOffset(
  clip: ReplayMontageClip,
  tickRate: number,
  offsetMs: number,
  reducedMotion = false,
): number {
  if (reducedMotion) {
    return clip.anchor_tick;
  }
  const playbackDurationMs =
    ((clip.end_tick - clip.start_tick) /
      tickRate /
      clip.playback_rate) *
    1_000;
  const progress = clamp(
    offsetMs / Math.max(playbackDurationMs, 1),
    0,
    1,
  );
  return (
    clip.start_tick +
    (clip.end_tick - clip.start_tick) * progress
  );
}

function smoothstep(value: number): number {
  const clamped = clamp(value, 0, 1);
  return clamped * clamped * (3 - 2 * clamped);
}

function hexColor(value: string): string {
  return /^#[0-9a-f]{6}$/iu.test(value) ? value : "#f3bc3e";
}

function eventEffect(
  event: RaceEvent,
  effects: readonly RaceEffect[],
): RaceEffect | undefined {
  return event.effect_id === undefined
    ? undefined
    : effects.find((effect) => effect.id === event.effect_id);
}

function eventPosition(
  event: RaceEvent,
  clip: ReplayMontageClip,
): { x: number; y: number } | null {
  const frame = interpolatedRacerFrame(clip.timeline, event.racer_id, event.tick);
  return frame === null ? null : { x: trackX(frame.x), y: trackY(frame.y) };
}

function deterministicUnit(seed: number): number {
  const value = Math.sin(seed * 12.9898) * 43_758.5453;
  return value - Math.floor(value);
}

function drawVenue(context: CanvasRenderingContext2D, laneCount: number): void {
  const gradient = context.createLinearGradient(0, 0, 0, HEIGHT);
  gradient.addColorStop(0, "#82c8dc");
  gradient.addColorStop(0.5, "#bfe4e8");
  gradient.addColorStop(1, "#73afbd");
  context.fillStyle = gradient;
  context.fillRect(0, 0, WIDTH, HEIGHT);

  context.fillStyle = "#18212b";
  context.fillRect(TRACK_LEFT - 5, TRACK_TOP - 5, TRACK_RIGHT - TRACK_LEFT + 10, TRACK_BOTTOM - TRACK_TOP + 10);
  context.fillStyle = "#b97947";
  context.fillRect(TRACK_LEFT, TRACK_TOP, TRACK_RIGHT - TRACK_LEFT, TRACK_BOTTOM - TRACK_TOP);

  context.fillStyle = "#351315";
  context.fillRect(TRACK_LEFT, TRACK_TOP, TRACK_RIGHT - TRACK_LEFT, 34);
  context.fillRect(TRACK_LEFT, TRACK_BOTTOM - 34, TRACK_RIGHT - TRACK_LEFT, 34);

  context.strokeStyle = "rgba(255, 239, 208, 0.7)";
  context.lineWidth = 2;
  for (let boundary = 0; boundary <= laneCount; boundary += 1) {
    const normalized = (boundary + 0.5) / (laneCount + 1);
    const y = trackY(normalized);
    context.beginPath();
    context.moveTo(TRACK_LEFT, y);
    context.lineTo(TRACK_RIGHT, y);
    context.stroke();
  }

  context.strokeStyle = "#fff8e7";
  context.lineWidth = 4;
  context.setLineDash([12, 9]);
  context.beginPath();
  context.moveTo(trackX(START_POSITION), TRACK_TOP);
  context.lineTo(trackX(START_POSITION), TRACK_BOTTOM);
  context.stroke();
  context.setLineDash([]);

  const finishX = trackX(FINISH_POSITION);
  const cellSize = 10;
  for (let row = 0; row < Math.ceil((TRACK_BOTTOM - TRACK_TOP) / cellSize); row += 1) {
    for (let column = 0; column < 2; column += 1) {
      context.fillStyle = (row + column) % 2 === 0 ? "#fff8e7" : "#18212b";
      context.fillRect(finishX - cellSize + column * cellSize, TRACK_TOP + row * cellSize, cellSize, cellSize);
    }
  }

  context.fillStyle = "rgba(24, 33, 43, 0.76)";
  context.font = "900 22px Arial Rounded MT Bold, sans-serif";
  context.textAlign = "left";
  context.fillText("INSTANT REPLAY", TRACK_LEFT + 14, 78);
}

function consumedDuringClip(
  clip: ReplayMontageClip,
  montage: ReplayMontage,
  currentTick: number,
): Set<number> {
  const consumed = new Set(clip.consumed_effect_ids_at_start);
  const oneShotKinds = new Set(["boxing_glove", "stop_sign", "magnet_mine", "portal_gate"]);
  for (const event of clip.events) {
    if (event.tick > currentTick || event.effect_id === undefined) {
      continue;
    }
    const effect = eventEffect(event, montage.effects);
    if (
      event.kind === "obstacle_removed" ||
      event.kind === "item_cleared" ||
      event.kind === "destroyed" ||
      (event.kind === "obstacle_hit" && effect !== undefined && oneShotKinds.has(effect.kind))
    ) {
      consumed.add(event.effect_id);
    }
  }
  return consumed;
}

function drawTrackItems(
  context: CanvasRenderingContext2D,
  clip: ReplayMontageClip,
  montage: ReplayMontage,
  assets: LoadedAssets,
  currentTick: number,
  laneCount: number,
): void {
  const consumed = consumedDuringClip(clip, montage, currentTick);
  for (const effect of montage.effects) {
    if (
      effect.lane === undefined ||
      effect.position === undefined ||
      effect.activation_tick > currentTick ||
      consumed.has(effect.id)
    ) {
      continue;
    }
    const image = assets.items.get(effect.id);
    const movingFrame = interpolatedTrackItemFrame(clip.timeline, effect.id, currentTick);
    if (movingFrame?.active === false) {
      continue;
    }
    const x = trackX(movingFrame?.x ?? effect.position);
    const normalizedLane = effect.lane / (Math.max(laneCount, 4) + 1);
    const y = trackY(movingFrame?.y ?? normalizedLane);
    if (image !== undefined) {
      context.drawImage(image, x - 25, y - 25, 50, 50);
    } else {
      context.fillStyle = hexColor(effect.item_color);
      context.beginPath();
      context.arc(x, y, 18, 0, Math.PI * 2);
      context.fill();
    }
  }
}

function drawFallbackRacer(
  context: CanvasRenderingContext2D,
  entry: RacerEntry,
  width: number,
  height: number,
): void {
  context.fillStyle = "#18212b";
  context.fillRect(-width / 2 - 3, -height / 2 - 3, width + 6, height + 6);
  context.fillStyle = hexColor(entry.color);
  context.fillRect(-width / 2, -height / 2, width, height);
  context.fillStyle = "#fff8e7";
  context.fillRect(-width * 0.22, -height * 0.18, width * 0.14, height * 0.16);
  context.fillRect(width * 0.08, -height * 0.18, width * 0.14, height * 0.16);
}

function drawRacer(
  context: CanvasRenderingContext2D,
  entry: RacerEntry,
  frame: RacerFrame,
  assets: LoadedAssets,
  elapsedMs: number,
): void {
  const image = assets.racers.get(frame.sprite_key);
  const metadata = racerSheetMetadata(frame.sprite_key);
  const scale = clamp(frame.scale, 0.55, 1.85);
  const width = BASE_RACER_WIDTH * scale;
  const height = BASE_RACER_HEIGHT * scale;
  const x = trackX(frame.x);
  const y = trackY(frame.y);

  context.save();
  context.globalAlpha = TERMINAL_ALPHA[frame.state];
  context.fillStyle = "rgba(24, 33, 43, 0.28)";
  context.beginPath();
  context.ellipse(x, y + height * 0.32, width * 0.42, height * 0.13, 0, 0, Math.PI * 2);
  context.fill();

  context.translate(x, y);
  context.rotate((frame.rotation * Math.PI) / 180);
  context.scale(frame.facing < 0 ? -1 : 1, 1);
  if (image !== undefined && metadata !== null) {
    const spriteFrame = racerAnimationFrame(frame.sprite_key, elapsedMs, frame.state);
    context.imageSmoothingEnabled = false;
    context.drawImage(
      image,
      spriteFrame * metadata.frameWidth,
      0,
      metadata.frameWidth,
      metadata.frameHeight,
      -width / 2,
      -height / 2,
      width,
      height,
    );
  } else {
    drawFallbackRacer(context, entry, width, height);
  }
  context.restore();

  context.save();
  context.font = "900 13px Arial Rounded MT Bold, sans-serif";
  const labelWidth = Math.max(context.measureText(entry.name).width + 16, 54);
  context.fillStyle = "#18212b";
  context.fillRect(x - labelWidth / 2, y - height / 2 - 24, labelWidth, 19);
  context.fillStyle = "#fff8e7";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(entry.name, x, y - height / 2 - 14);
  context.restore();
}

function drawEventVfx(
  context: CanvasRenderingContext2D,
  clip: ReplayMontageClip,
  montage: ReplayMontage,
  assets: LoadedAssets,
  currentTick: number,
): void {
  const activeWindow = montage.tick_rate * 0.55;
  for (const event of clip.events) {
    const age = currentTick - event.tick;
    if (age < 0 || age > activeWindow) {
      continue;
    }
    const position = eventPosition(event, clip);
    if (position === null) {
      continue;
    }
    const progress = clamp(age / activeWindow, 0, 1);
    const radius = 24 + progress * 56;
    context.save();
    context.globalAlpha = 1 - progress;
    context.strokeStyle =
      event.kind === "destroyed" || event.kind === "knockout" ? "#ff5d4a" : "#fff1bd";
    context.lineWidth = 6 - progress * 3;
    context.beginPath();
    context.arc(position.x, position.y, radius, 0, Math.PI * 2);
    context.stroke();
    for (let index = 0; index < 12; index += 1) {
      const angle = deterministicUnit(event.tick + index * 17) * Math.PI * 2;
      const distance = 18 + progress * (42 + deterministicUnit(index + event.racer_id) * 30);
      const size = 3 + deterministicUnit(index * 31 + event.tick) * 5;
      context.fillStyle = index % 2 === 0 ? "#f3bc3e" : "#fff8e7";
      context.fillRect(
        position.x + Math.cos(angle) * distance - size / 2,
        position.y + Math.sin(angle) * distance - size / 2,
        size,
        size,
      );
    }
    const effect = eventEffect(event, montage.effects);
    const itemImage = effect === undefined ? undefined : assets.items.get(effect.id);
    if (itemImage !== undefined) {
      const iconSize = 42 + Math.sin(progress * Math.PI) * 12;
      context.drawImage(
        itemImage,
        position.x - iconSize / 2,
        position.y - 76 - iconSize / 2,
        iconSize,
        iconSize,
      );
    }
    context.restore();
  }
}

function cameraForTick(
  clip: ReplayMontageClip,
  entries: readonly RacerEntry[],
  currentTick: number,
): { x: number; y: number; zoom: number } {
  const focusFrames = clip.focus_racer_ids.flatMap((racerId) => {
    const frame = interpolatedRacerFrame(clip.timeline, racerId, currentTick);
    return frame === null ? [] : [frame];
  });
  const centerX =
    focusFrames.length === 0
      ? WIDTH / 2
      : focusFrames.reduce((total, frame) => total + trackX(frame.x), 0) / focusFrames.length;
  const centerY =
    focusFrames.length === 0
      ? (TRACK_TOP + TRACK_BOTTOM) / 2
      : focusFrames.reduce((total, frame) => total + trackY(frame.y), 0) / focusFrames.length;
  const anchorProgress =
    1 -
    clamp(
      Math.abs(currentTick - clip.anchor_tick) /
        Math.max((clip.end_tick - clip.start_tick) * 0.65, 1),
      0,
      1,
    );
  const focusZoom = clip.kind === "finish" ? 1.62 : 1.48;
  const zoom = 1.05 + (focusZoom - 1.05) * smoothstep(anchorProgress);
  const laneBias = entries.length <= 4 ? 0 : 8;
  return {
    x: clamp(centerX, WIDTH / (2 * zoom), WIDTH - WIDTH / (2 * zoom)),
    y: clamp(centerY + laneBias, HEIGHT / (2 * zoom), HEIGHT - HEIGHT / (2 * zoom)),
    zoom,
  };
}

function shakeForTick(
  clip: ReplayMontageClip,
  currentTick: number,
  reducedMotion: boolean,
): { x: number; y: number } {
  if (reducedMotion || clip.event_kind === null) {
    return { x: 0, y: 0 };
  }
  const strength = SHAKE_STRENGTH[clip.event_kind] ?? 0;
  const age = currentTick - clip.anchor_tick;
  const durationTicks = 7;
  if (strength === 0 || age < 0 || age > durationTicks) {
    return { x: 0, y: 0 };
  }
  const fade = 1 - age / durationTicks;
  return {
    x: Math.sin(age * 7.3) * strength * fade,
    y: Math.cos(age * 5.7) * strength * 0.65 * fade,
  };
}

function drawFrame(
  context: CanvasRenderingContext2D,
  clip: ReplayMontageClip,
  montage: ReplayMontage,
  entries: readonly RacerEntry[],
  assets: LoadedAssets,
  currentTick: number,
  elapsedMs: number,
  reducedMotion: boolean,
): void {
  context.clearRect(0, 0, WIDTH, HEIGHT);
  const camera = cameraForTick(clip, entries, currentTick);
  const shake = shakeForTick(clip, currentTick, reducedMotion);
  context.save();
  context.translate(WIDTH / 2 + shake.x, HEIGHT / 2 + shake.y);
  context.scale(camera.zoom, camera.zoom);
  context.translate(-camera.x, -camera.y);
  drawVenue(context, Math.max(entries.length, 4));
  drawTrackItems(context, clip, montage, assets, currentTick, entries.length);

  const frames = entries.flatMap((entry) => {
    const frame = interpolatedRacerFrame(clip.timeline, entry.racer_id, currentTick);
    return frame === null ? [] : [{ entry, frame }];
  });
  frames.sort((left, right) => left.frame.y - right.frame.y);
  for (const { entry, frame } of frames) {
    drawRacer(context, entry, frame, assets, elapsedMs);
  }
  drawEventVfx(context, clip, montage, assets, currentTick);
  context.restore();

  context.save();
  context.strokeStyle = "rgba(255, 248, 231, 0.88)";
  context.lineWidth = 5;
  context.strokeRect(2.5, 2.5, WIDTH - 5, HEIGHT - 5);
  context.restore();
}

export function createReplayCanvasRenderer(canvas: HTMLCanvasElement): ReplayCanvasRenderer {
  const availableContext = canvas.getContext("2d");
  if (availableContext === null) {
    throw new Error("Canvas rendering is unavailable.");
  }
  const context: CanvasRenderingContext2D = availableContext;
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  const assets: LoadedAssets = {
    racers: new Map(),
    items: new Map(),
  };
  let frameRequest: number | null = null;
  let activeResolve: (() => void) | null = null;
  let playGeneration = 0;

  function stop(): void {
    playGeneration += 1;
    if (frameRequest !== null) {
      cancelAnimationFrame(frameRequest);
      frameRequest = null;
    }
    activeResolve?.();
    activeResolve = null;
  }

  async function load(
    montage: ReplayMontage,
    entries: readonly RacerEntry[],
  ): Promise<void> {
    const spriteKeys = new Set([
      ...entries.map((entry) => entry.sprite_key),
      ...montage.clips.flatMap((clip) =>
        clip.timeline.flatMap((frame) => frame.racers.map((racer) => racer.sprite_key)),
      ),
    ]);
    const racerLoads = [...spriteKeys].map(async (spriteKey) => {
      if (assets.racers.has(spriteKey)) {
        return;
      }
      const image = await loadImage(racerSheetPath(spriteKey));
      if (image !== null) {
        assets.racers.set(spriteKey, image);
      }
    });
    const itemLoads = montage.effects.map(async (effect) => {
      if (assets.items.has(effect.id)) {
        return;
      }
      const image = await loadImage(itemArtPath(effect.kind));
      if (image !== null) {
        assets.items.set(effect.id, image);
      }
    });
    await Promise.all([...racerLoads, ...itemLoads]);
  }

  function play(
    clip: ReplayMontageClip,
    montage: ReplayMontage,
    entries: readonly RacerEntry[],
    reducedMotion: boolean,
    options: {
      offsetMs?: number;
      durationMs?: number;
    } = {},
  ): Promise<void> {
    stop();
    const generation = playGeneration;
    const playbackDurationMs =
      ((clip.end_tick - clip.start_tick) / montage.tick_rate / clip.playback_rate) *
      1_000;
    const authoredDurationMs = Math.max(
      options.durationMs ?? playbackDurationMs,
      playbackDurationMs,
    );
    const offsetMs = clamp(options.offsetMs ?? 0, 0, authoredDurationMs);
    const startedAt = performance.now() - offsetMs;
    return new Promise((resolve) => {
      activeResolve = resolve;
      const render = (now: number): void => {
        if (generation !== playGeneration) {
          return;
        }
        const elapsed = now - startedAt;
        const authoredProgress = clamp(elapsed / authoredDurationMs, 0, 1);
        const currentTick = replayTickForOffset(
          clip,
          montage.tick_rate,
          elapsed,
          reducedMotion,
        );
        drawFrame(
          context,
          clip,
          montage,
          entries,
          assets,
          currentTick,
          elapsed,
          reducedMotion,
        );
        if (authoredProgress >= 1) {
          frameRequest = null;
          activeResolve = null;
          resolve();
          return;
        }
        frameRequest = requestAnimationFrame(render);
      };
      frameRequest = requestAnimationFrame(render);
    });
  }

  function dispose(): void {
    stop();
    assets.racers.clear();
    assets.items.clear();
    context.clearRect(0, 0, WIDTH, HEIGHT);
  }

  return { load, play, stop, dispose };
}
