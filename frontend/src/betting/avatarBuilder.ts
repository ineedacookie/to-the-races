import type { AvatarLayer, AvatarRecipe } from "../shared/types";

const CELL_WIDTH = 64;
const CELL_HEIGHT = 112;
const CELL_GAP_X = 4;
const CELL_GAP_Y = 4;

const AVATAR_LAYERS = [
  "skin",
  "eyes",
  "bottoms",
  "tops",
  "shoes",
  "hair",
] as const satisfies readonly AvatarLayer[];

interface LayerMeta {
  columns: number;
  count: number;
}

const LAYER_META: Record<AvatarLayer, LayerMeta> = {
  skin: { columns: 12, count: 12 },
  eyes: { columns: 17, count: 17 },
  bottoms: { columns: 25, count: 150 },
  tops: { columns: 23, count: 253 },
  shoes: { columns: 17, count: 34 },
  hair: { columns: 13, count: 65 },
};

function isAvatarLayer(value: string | undefined): value is AvatarLayer {
  return value !== undefined && AVATAR_LAYERS.some((layer) => layer === value);
}

function randomIndex(count: number): number {
  return Math.floor(Math.random() * count);
}

function randomRecipe(): AvatarRecipe {
  return {
    skin: randomIndex(LAYER_META.skin.count),
    eyes: randomIndex(LAYER_META.eyes.count),
    bottoms: randomIndex(LAYER_META.bottoms.count),
    tops: randomIndex(LAYER_META.tops.count),
    shoes: randomIndex(LAYER_META.shoes.count),
    hair: randomIndex(LAYER_META.hair.count),
  };
}

export interface AvatarBuilder {
  recipe(): AvatarRecipe;
  randomize(): void;
  setRecipe(recipe: AvatarRecipe): void;
}

export function createAvatarBuilder(root: HTMLElement): AvatarBuilder {
  const preview = root.querySelector<HTMLElement>("#avatar-preview-canvas");
  if (preview === null) {
    throw new Error("Missing avatar preview canvas.");
  }

  let currentRecipe = randomRecipe();
  const previewLayers = new Map<AvatarLayer, HTMLElement>();
  for (const layer of AVATAR_LAYERS) {
    const layerElement = document.createElement("span");
    layerElement.className = "avatar-preview__layer";
    layerElement.dataset.layer = layer;
    layerElement.style.backgroundImage =
      `url("/static/assets/crowd/source/${layer}.png")`;
    preview.append(layerElement);
    previewLayers.set(layer, layerElement);
  }

  function renderLayer(layer: AvatarLayer): void {
    const meta = LAYER_META[layer];
    const index = currentRecipe[layer];
    const column = index % meta.columns;
    const row = Math.floor(index / meta.columns);
    const previewLayer = previewLayers.get(layer);
    if (previewLayer !== undefined) {
      previewLayer.style.backgroundPosition =
        `-${column * (CELL_WIDTH + CELL_GAP_X)}px ` +
        `-${row * (CELL_HEIGHT + CELL_GAP_Y)}px`;
    }

    const choice = root.querySelector<HTMLElement>(`[data-avatar-layer="${layer}"]`);
    const output = choice?.querySelector<HTMLOutputElement>("output");
    if (output !== null && output !== undefined) {
      output.value = `${index + 1}/${meta.count}`;
    }
  }

  function render(): void {
    for (const layer of AVATAR_LAYERS) {
      renderLayer(layer);
    }
  }

  for (const choice of root.querySelectorAll<HTMLElement>("[data-avatar-layer]")) {
    const layer = choice.dataset.avatarLayer;
    if (!isAvatarLayer(layer)) {
      continue;
    }
    for (const button of choice.querySelectorAll<HTMLButtonElement>(
      "[data-avatar-direction]",
    )) {
      button.addEventListener("click", () => {
        const direction = Number(button.dataset.avatarDirection);
        const count = LAYER_META[layer].count;
        currentRecipe[layer] = (currentRecipe[layer] + direction + count) % count;
        renderLayer(layer);
      });
    }
  }

  render();
  return {
    recipe: () => ({ ...currentRecipe }),
    randomize: () => {
      currentRecipe = randomRecipe();
      render();
    },
    setRecipe: (recipe) => {
      currentRecipe = { ...recipe };
      render();
    },
  };
}
