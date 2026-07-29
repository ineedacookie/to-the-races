import { racerPortraitPath } from "./assets";
import type { RacerEntry } from "./types";

export interface ReplayPodiumModel {
  title: string;
  podium: RacerEntry[];
  wrecked: RacerEntry[];
}

interface ReplayPodiumElements {
  title: HTMLElement;
  grid: HTMLElement;
}

function resultOrder(left: RacerEntry, right: RacerEntry): number {
  if (left.finish_place === null && right.finish_place === null) {
    return left.lane - right.lane;
  }
  if (left.finish_place === null) {
    return 1;
  }
  if (right.finish_place === null) {
    return -1;
  }
  return left.finish_place - right.finish_place;
}

function resultDetail(entry: RacerEntry): string {
  if (entry.finish_place !== null) {
    return `${entry.finish_place}th place`;
  }
  return entry.dnf_reason ? entry.dnf_reason.replaceAll("_", " ") : "Did not finish";
}

function racerPortrait(entry: RacerEntry): HTMLImageElement {
  const portrait = document.createElement("img");
  portrait.src = racerPortraitPath(entry.sprite_key);
  portrait.alt = "";
  portrait.addEventListener(
    "error",
    () => {
      portrait.hidden = true;
    },
    { once: true },
  );
  return portrait;
}

export function replayPodiumModel(entries: readonly RacerEntry[]): ReplayPodiumModel {
  const ordered = [...entries].sort(resultOrder);
  const winner = ordered.find((entry) => entry.finish_place === 1) ?? null;
  return {
    title: winner === null ? "Total chaos. The house wins." : `${winner.name} wins!`,
    podium: ordered.filter(
      (entry) => entry.finish_place !== null && entry.finish_place <= 3,
    ),
    wrecked: ordered.filter(
      (entry) => entry.finish_place === null || entry.finish_place > 3,
    ),
  };
}

export function renderReplayPodium(
  elements: ReplayPodiumElements,
  entries: readonly RacerEntry[],
): void {
  const model = replayPodiumModel(entries);
  elements.title.textContent = model.title;
  elements.grid.replaceChildren();

  const stands = document.createElement("div");
  stands.className = "replay-podium-stands";
  for (const entry of model.podium) {
    const place = entry.finish_place;
    if (place === null) {
      continue;
    }
    const racer = document.createElement("article");
    racer.className = `replay-podium-place replay-podium-place--${place}`;
    racer.dataset.place = String(place);
    racer.style.setProperty("--racer-accent", entry.color);

    const character = document.createElement("div");
    character.className = "replay-podium-character";
    character.append(racerPortrait(entry));
    const name = document.createElement("strong");
    name.textContent = entry.name;
    character.append(name);

    const block = document.createElement("div");
    block.className = "replay-podium-block";
    const medal = document.createElement("span");
    medal.className = "replay-podium-medal";
    medal.textContent = `#${place}`;
    const label = document.createElement("small");
    label.textContent =
      place === 1 ? "Gold" : place === 2 ? "Silver" : "Bronze";
    block.append(medal, label);
    racer.append(character, block);
    stands.append(racer);
  }
  elements.grid.append(stands);

  if (model.wrecked.length === 0) {
    return;
  }
  const wrecks = document.createElement("div");
  wrecks.className = "replay-podium-wrecks";
  const wrecksLabel = document.createElement("strong");
  wrecksLabel.className = "replay-podium-wrecks__label";
  wrecksLabel.textContent = "Wreckage row";
  wrecks.append(wrecksLabel);
  for (const entry of model.wrecked) {
    const wreck = document.createElement("article");
    wreck.className = "replay-podium-wreck";
    wreck.style.setProperty("--racer-accent", entry.color);
    wreck.append(racerPortrait(entry));
    const copy = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = entry.name;
    const detail = document.createElement("small");
    detail.textContent = resultDetail(entry);
    copy.append(name, detail);
    wreck.append(copy);
    wrecks.append(wreck);
  }
  elements.grid.append(wrecks);
}
