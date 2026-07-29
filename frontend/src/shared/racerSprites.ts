import type { RacerFrame } from "./types";

export interface RacerSheetMetadata {
  frameWidth: number;
  frameHeight: number;
  frames: number;
  frameRate: number;
}

export const RACER_SHEETS = {
  skeleton: { frameWidth: 45, frameHeight: 51, frames: 4, frameRate: 7 },
  mushroom: { frameWidth: 26, frameHeight: 39, frames: 8, frameRate: 10 },
  goblin: { frameWidth: 38, frameHeight: 38, frames: 8, frameRate: 10 },
  "flying-eye": { frameWidth: 42, frameHeight: 33, frames: 8, frameRate: 10 },
  mimic: { frameWidth: 47, frameHeight: 34, frames: 6, frameRate: 10 },
  rat: { frameWidth: 59, frameHeight: 20, frames: 8, frameRate: 10 },
  slime: { frameWidth: 46, frameHeight: 20, frames: 6, frameRate: 10 },
  bat: { frameWidth: 67, frameHeight: 55, frames: 11, frameRate: 10 },
} as const satisfies Record<string, RacerSheetMetadata>;

export type RacerSpriteKey = keyof typeof RACER_SHEETS;

export function racerSheetMetadata(spriteKey: string): RacerSheetMetadata | null {
  return RACER_SHEETS[spriteKey as RacerSpriteKey] ?? null;
}

export function racerSheetPath(spriteKey: string): string {
  return `/static/assets/racers/sheets/${spriteKey}.png`;
}

export function racerAnimationFrame(
  spriteKey: string,
  elapsedMs: number,
  state: RacerFrame["state"],
): number {
  const metadata = racerSheetMetadata(spriteKey);
  if (metadata === null || (state !== "running" && state !== "backwards")) {
    return 0;
  }
  return Math.floor((elapsedMs / 1_000) * metadata.frameRate) % metadata.frames;
}
