import { patchBailoutWound, startBailout } from "../shared/api";
import { formatMoney } from "../shared/format";
import {
  presentationRound,
  userFacingApiError,
} from "../shared/liveUi";
import { createOverlayController } from "../shared/overlay";
import { runPendingAction } from "../shared/pendingAction";
import type { LivePlayer, LiveState } from "../shared/types";
import {
  applyTrackMedicPatch,
  shouldShowTrackMedicCallout,
  trackMedicCalloutCopy,
  trackMedicForRound,
  woundButtonLabel,
} from "./trackMedic";

interface TrackMedicElements {
  bettingHeader: HTMLElement;
  bettingMain: HTMLElement;
  trackMedicCallout: HTMLElement;
  trackMedicCalloutTitle: HTMLElement;
  trackMedicCalloutCopyEl: HTMLElement;
  trackMedicOpen: HTMLButtonElement;
  trackMedicBackdrop: HTMLElement;
  trackMedicClose: HTMLButtonElement;
  trackMedicTitle: HTMLElement;
  trackMedicCopy: HTMLElement;
  trackMedicPortrait: HTMLImageElement;
  trackMedicWounds: HTMLElement;
  trackMedicProgress: HTMLElement;
  trackMedicReward: HTMLElement;
  returnFocusFallback: HTMLElement;
}

interface TrackMedicHooks {
  getState: () => LiveState | null;
  refresh: () => Promise<void>;
  showToast: (message: string, tone: "good" | "bad" | "neutral") => void;
}

export interface TrackMedicUiState {
  panelOpen: boolean;
  pendingStarts: Set<number>;
  pendingPatches: Set<string>;
}

interface TrackMedicController {
  render: (player: LivePlayer, currentState: LiveState) => void;
  close: () => void;
  wireEvents: () => void;
}

export function createTrackMedicController(
  elements: TrackMedicElements,
  hooks: TrackMedicHooks,
  state: TrackMedicUiState,
): TrackMedicController {
  const overlay = createOverlayController({
    backdrop: elements.trackMedicBackdrop,
    focusRoot: elements.trackMedicBackdrop,
    closeButton: elements.trackMedicClose,
    inertTargets: [elements.bettingHeader, elements.bettingMain],
    fallbackFocus: elements.returnFocusFallback,
    onOpen: () => {
      state.panelOpen = true;
      elements.trackMedicOpen.setAttribute("aria-expanded", "true");
    },
    onClose: () => {
      state.panelOpen = false;
      elements.trackMedicOpen.setAttribute("aria-expanded", "false");
    },
  });

  function close(): void {
    overlay.close();
  }

  function open(focusTarget?: HTMLElement): void {
    overlay.open(focusTarget ?? elements.trackMedicOpen);
  }

  async function patchWound(
    sessionId: number,
    woundIndex: number,
    player: LivePlayer,
    currentState: LiveState,
  ): Promise<void> {
    const pendingKey = `${sessionId}:${woundIndex}`;
    let confirmedPatch:
      | Awaited<ReturnType<typeof patchBailoutWound>>["bailout_patch"]
      | null = null;
    await runPendingAction({
      key: pendingKey,
      pending: state.pendingPatches,
      onPendingChange: () => {
        const latest = hooks.getState() ?? currentState;
        const latestPlayer = latest.player ?? player;
        const renderPlayer =
          confirmedPatch === null
            ? latestPlayer
            : {
                ...latestPlayer,
                track_medic: applyTrackMedicPatch(
                  latestPlayer.track_medic,
                  confirmedPatch,
                ),
              };
        render(renderPlayer, latest);
      },
      action: async () => {
        const receipt = await patchBailoutWound(sessionId, woundIndex);
        confirmedPatch = receipt.bailout_patch;
        player.balance_cents = receipt.balance_cents;
        player.track_medic = applyTrackMedicPatch(
          player.track_medic,
          receipt.bailout_patch,
        );
        render(player, currentState);
        await hooks.refresh();
        if (receipt.bailout_patch.completed) {
          hooks.showToast(
            `Track medic paid ${formatMoney(receipt.bailout_patch.reward_cents)}! Balance refreshed.`,
            "good",
          );
          elements.trackMedicReward.hidden = false;
          elements.trackMedicReward.textContent = `Paid ${formatMoney(receipt.bailout_patch.reward_cents)} · New balance ${formatMoney(receipt.balance_cents)}`;
          window.setTimeout(close, 1400);
        } else {
          hooks.showToast("Wound patched.", "good");
        }
      },
      onError: (error) => {
        hooks.showToast(userFacingApiError(error, "Could not patch that wound."), "bad");
      },
    });
  }

  function render(player: LivePlayer, currentState: LiveState): void {
    const round = presentationRound(currentState);
    const showCallout = shouldShowTrackMedicCallout(
      player,
      round,
    );
    elements.trackMedicCallout.hidden = !showCallout;
    if (showCallout) {
      const copy = trackMedicCalloutCopy(player, round);
      elements.trackMedicCalloutTitle.textContent = copy.title;
      elements.trackMedicCalloutCopyEl.textContent = copy.copy;
      elements.trackMedicOpen.textContent = copy.action;
      elements.trackMedicOpen.disabled = state.pendingStarts.has(round?.id ?? -1);
    }

    const trackMedic = trackMedicForRound(player, round);
    if (trackMedic.stale && state.panelOpen) {
      close();
      hooks.showToast("That track medic session expired with the last round.", "neutral");
    }

    const session = trackMedic.session;
    if (!state.panelOpen) {
      return;
    }

    if (session === null || session.completed) {
      close();
      return;
    }

    elements.trackMedicTitle.textContent = `Patch ${session.target.racer_name}`;
    elements.trackMedicCopy.textContent = "Click each red wound marker to bandage it.";
    elements.trackMedicPortrait.src = session.target.portrait_url;
    elements.trackMedicPortrait.alt = `${session.target.racer_name} needs patching`;
    elements.trackMedicProgress.textContent = `${session.patched_count} of ${session.wound_count} wounds patched`;
    elements.trackMedicReward.hidden = true;
    elements.trackMedicWounds.replaceChildren();

    for (const wound of session.wounds) {
      const pendingKey = `${session.id}:${wound.index}`;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "track-medic-wound";
      button.style.left = `${wound.x * 100}%`;
      button.style.top = `${wound.y * 100}%`;
      button.setAttribute("aria-label", woundButtonLabel(wound.index));
      button.disabled = wound.patched || state.pendingPatches.has(pendingKey);
      button.classList.toggle("is-patched", wound.patched);
      button.classList.toggle("is-pending", state.pendingPatches.has(pendingKey));
      if (!wound.patched) {
        button.addEventListener("click", () => {
          void patchWound(session.id, wound.index, player, currentState);
        });
      }
      elements.trackMedicWounds.append(button);
    }
  }

  async function begin(): Promise<void> {
    const currentState = hooks.getState();
    if (
      currentState?.player === null ||
      currentState?.player === undefined
    ) {
      return;
    }
    const round = presentationRound(currentState);
    if (round === null) {
      return;
    }
    const { player } = currentState;
    const roundId = round.id;
    const existing = trackMedicForRound(player, round).session;
    if (existing !== null && !existing.completed) {
      open(elements.trackMedicOpen);
      render(player, currentState);
      return;
    }

    await runPendingAction({
      key: roundId,
      pending: state.pendingStarts,
      onPendingChange: () => {
        const latest = hooks.getState() ?? currentState;
        render(latest.player ?? player, latest);
      },
      action: async () => {
        await startBailout(roundId);
        await hooks.refresh();
        const refreshed = hooks.getState();
        if (refreshed?.player !== null && refreshed?.player !== undefined) {
          open(elements.trackMedicOpen);
          render(refreshed.player, refreshed);
          hooks.showToast("Track medic assigned a patient.", "good");
        }
      },
      onError: (error) => {
        hooks.showToast(userFacingApiError(error, "Could not start track medic."), "bad");
      },
    });
  }

  function wireEvents(): void {
    elements.trackMedicOpen.addEventListener("click", () => {
      void begin();
    });
    overlay.wireEvents();
  }

  return { render, close, wireEvents };
}
