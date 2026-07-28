import type { AudienceReactionKind } from "../shared/types";

const REACTION_SUBMISSION_COOLDOWN_MS = 3_000;

interface CrowdReactionElements {
  cheer: HTMLButtonElement;
  boo: HTMLButtonElement;
  cry: HTMLButtonElement;
  shout: HTMLInputElement;
  shoutSend: HTMLButtonElement;
}

interface CrowdReactionActions {
  sendReaction: (kind: AudienceReactionKind, options?: { text?: string }) => void;
  showError: (message: string) => void;
}

export function createCrowdReactionController(
  elements: CrowdReactionElements,
  actions: CrowdReactionActions,
): { wireEvents: () => void } {
  let cooldownUntil = 0;
  let cooldownTimer: number | null = null;

  function updateControls(): void {
    const remainingMs = Math.max(cooldownUntil - Date.now(), 0);
    const coolingDown = remainingMs > 0;
    elements.cheer.disabled = coolingDown;
    elements.boo.disabled = coolingDown;
    elements.cry.disabled = coolingDown;
    elements.shoutSend.disabled = coolingDown;
    const title = coolingDown
      ? `Ready in ${Math.max(Math.ceil(remainingMs / 1_000), 1)} seconds`
      : "";
    elements.cheer.title = title;
    elements.boo.title = title;
    elements.cry.title = title;
    elements.shoutSend.title = title;
    if (cooldownTimer !== null) {
      window.clearTimeout(cooldownTimer);
      cooldownTimer = null;
    }
    if (coolingDown) {
      cooldownTimer = window.setTimeout(updateControls, remainingMs + 25);
    }
  }

  function send(kind: AudienceReactionKind): void {
    if (Date.now() < cooldownUntil) {
      return;
    }
    if (kind === "shout") {
      const text = elements.shout.value.trim();
      if (text.length === 0) {
        actions.showError("Type a shout first (24 characters max).");
        return;
      }
      actions.sendReaction("shout", { text });
      elements.shout.value = "";
    } else {
      actions.sendReaction(kind);
    }
    cooldownUntil = Date.now() + REACTION_SUBMISSION_COOLDOWN_MS;
    updateControls();
  }

  function wireEvents(): void {
    elements.cheer.addEventListener("click", () => {
      send("cheer");
    });
    elements.boo.addEventListener("click", () => {
      send("boo");
    });
    elements.cry.addEventListener("click", () => {
      send("cry");
    });
    elements.shoutSend.addEventListener("click", () => {
      send("shout");
    });
    elements.shout.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        send("shout");
      }
    });
  }

  return { wireEvents };
}
