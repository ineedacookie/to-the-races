import { mowLawnCells, startLawnMowing } from "../shared/api";
import { formatMoney } from "../shared/format";
import { presentationRound, userFacingApiError } from "../shared/liveUi";
import { createOverlayController } from "../shared/overlay";
import type { LivePlayer, LiveState } from "../shared/types";
import {
  applyLawnMowingReceipt,
  lawnMowingForRound,
  shouldShowLawnMowingCallout,
} from "./lawnMowing";

interface LawnMowingElements {
  bettingHeader: HTMLElement;
  bettingMain: HTMLElement;
  callout: HTMLElement;
  openButton: HTMLButtonElement;
  backdrop: HTMLElement;
  closeButton: HTMLButtonElement;
  stage: HTMLElement;
  grid: HTMLElement;
  mower: HTMLElement;
  progress: HTMLElement;
  reward: HTMLElement;
  returnFocusFallback: HTMLElement;
}

interface LawnMowingHooks {
  getState: () => LiveState | null;
  refresh: () => Promise<void>;
  showToast: (message: string, tone: "good" | "bad" | "neutral") => void;
}

export interface LawnMowingUiState {
  panelOpen: boolean;
  starting: boolean;
  saving: boolean;
  pendingCells: Set<number>;
}

export function createLawnMowingController(
  elements: LawnMowingElements,
  hooks: LawnMowingHooks,
  state: LawnMowingUiState,
): {
  render: (player: LivePlayer, currentState: LiveState) => void;
  close: () => void;
  wireEvents: () => void;
} {
  let mowing = false;
  let pointerId: number | null = null;

  const overlay = createOverlayController({
    backdrop: elements.backdrop,
    focusRoot: elements.backdrop,
    closeButton: elements.closeButton,
    inertTargets: [elements.bettingHeader, elements.bettingMain],
    fallbackFocus: elements.returnFocusFallback,
    onOpen: () => {
      state.panelOpen = true;
      elements.openButton.setAttribute("aria-expanded", "true");
    },
    onClose: () => {
      state.panelOpen = false;
      elements.openButton.setAttribute("aria-expanded", "false");
    },
  });

  function close(): void {
    overlay.close();
  }

  function render(player: LivePlayer, currentState: LiveState): void {
    const round = presentationRound(currentState);
    const lawn = lawnMowingForRound(player, round);
    elements.callout.hidden = !shouldShowLawnMowingCallout(player, round);
    elements.openButton.disabled = state.starting;
    elements.openButton.textContent = lawn.session === null ? "Start mowing" : "Keep mowing";

    if (lawn.stale && state.panelOpen) {
      close();
      hooks.showToast("That lawn job expired with the last round.", "neutral");
    }
    if (!state.panelOpen || lawn.session === null || lawn.session.completed) {
      return;
    }

    const { session } = lawn;
    const mowed = new Set([...session.mowed_cells, ...state.pendingCells]);
    elements.grid.style.setProperty("--lawn-columns", String(session.columns));
    elements.grid.style.setProperty("--lawn-rows", String(session.rows));
    const cells = Array.from({ length: session.cell_count }, (_, index) => {
      const cell = document.createElement("span");
      cell.className = "lawn-cell";
      cell.classList.toggle("is-mowed", mowed.has(index));
      cell.dataset.cellIndex = String(index);
      return cell;
    });
    elements.grid.replaceChildren(...cells);
    elements.progress.textContent = `${mowed.size} of ${session.cell_count} grass tiles mowed`;
    elements.reward.hidden = true;
  }

  async function flushStroke(): Promise<void> {
    if (state.saving || state.pendingCells.size === 0) {
      return;
    }
    const currentState = hooks.getState();
    const player = currentState?.player;
    const round = currentState === null ? null : presentationRound(currentState);
    if (currentState === null || player === null || player === undefined) {
      return;
    }
    const session = lawnMowingForRound(player, round).session;
    if (session === null) {
      return;
    }
    const cells = [...state.pendingCells];
    state.pendingCells.clear();
    state.saving = true;
    try {
      const receipt = await mowLawnCells(session.id, cells);
      player.balance_cents = receipt.balance_cents;
      player.lawn_mowing = applyLawnMowingReceipt(
        player.lawn_mowing,
        receipt.lawn_mowing,
      );
      render(player, currentState);
      await hooks.refresh();
      if (receipt.lawn_mowing.completed) {
        elements.reward.hidden = false;
        elements.reward.textContent = `Paid ${formatMoney(receipt.lawn_mowing.reward_cents)} · New balance ${formatMoney(receipt.balance_cents)}`;
        hooks.showToast(
          `Lawn mowing paid ${formatMoney(receipt.lawn_mowing.reward_cents)}!`,
          "good",
        );
        window.setTimeout(close, 1400);
      }
    } catch (error: unknown) {
      cells.forEach((cell) => state.pendingCells.add(cell));
      hooks.showToast(userFacingApiError(error, "Could not save that mowing path."), "bad");
      render(player, currentState);
    } finally {
      state.saving = false;
      if (state.pendingCells.size > 0 && !mowing) {
        void flushStroke();
      }
    }
  }

  function moveMower(event: PointerEvent, cutGrass: boolean): void {
    const rect = elements.stage.getBoundingClientRect();
    const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
    const y = Math.max(0, Math.min(rect.height, event.clientY - rect.top));
    elements.mower.style.left = `${x}px`;
    elements.mower.style.top = `${y}px`;
    if (!cutGrass) {
      return;
    }
    const currentState = hooks.getState();
    const player = currentState?.player;
    const round = currentState === null ? null : presentationRound(currentState);
    if (player === null || player === undefined) {
      return;
    }
    const session = lawnMowingForRound(player, round).session;
    if (session === null) {
      return;
    }
    const column = Math.min(session.columns - 1, Math.floor((x / rect.width) * session.columns));
    const row = Math.min(session.rows - 1, Math.floor((y / rect.height) * session.rows));
    const index = row * session.columns + column;
    if (!session.mowed_cells.includes(index)) {
      state.pendingCells.add(index);
      elements.grid.querySelector(`[data-cell-index="${index}"]`)?.classList.add("is-mowed");
      elements.progress.textContent =
        `${new Set([...session.mowed_cells, ...state.pendingCells]).size} of ${session.cell_count} grass tiles mowed`;
    }
  }

  async function begin(): Promise<void> {
    const currentState = hooks.getState();
    const player = currentState?.player;
    const round = currentState === null ? null : presentationRound(currentState);
    if (currentState === null || player === null || player === undefined || round === null) {
      return;
    }
    const existing = lawnMowingForRound(player, round).session;
    if (existing !== null && !existing.completed) {
      overlay.open(elements.openButton);
      render(player, currentState);
      return;
    }
    state.starting = true;
    render(player, currentState);
    try {
      await startLawnMowing(round.id);
      await hooks.refresh();
      const refreshed = hooks.getState();
      if (refreshed?.player !== null && refreshed?.player !== undefined) {
        overlay.open(elements.openButton);
        render(refreshed.player, refreshed);
        hooks.showToast("Lawn mower ready. Drag across every grass tile.", "good");
      }
    } catch (error: unknown) {
      hooks.showToast(userFacingApiError(error, "Could not start lawn mowing."), "bad");
    } finally {
      state.starting = false;
    }
  }

  function wireEvents(): void {
    elements.openButton.addEventListener("click", () => void begin());
    elements.stage.addEventListener("pointerdown", (event) => {
      mowing = true;
      pointerId = event.pointerId;
      elements.stage.setPointerCapture(event.pointerId);
      moveMower(event, true);
    });
    elements.stage.addEventListener("pointermove", (event) => {
      moveMower(event, mowing && pointerId === event.pointerId);
    });
    const finishStroke = (event: PointerEvent) => {
      if (pointerId !== event.pointerId) {
        return;
      }
      mowing = false;
      pointerId = null;
      void flushStroke();
    };
    elements.stage.addEventListener("pointerup", finishStroke);
    elements.stage.addEventListener("pointercancel", finishStroke);
    overlay.wireEvents();
  }

  return { render, close, wireEvents };
}
