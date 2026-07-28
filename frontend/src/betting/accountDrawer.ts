import { createOverlayController } from "../shared/overlay";

interface AccountDrawerElements {
  bettingHeader: HTMLElement;
  bettingMain: HTMLElement;
  accountButton: HTMLButtonElement;
  backdrop: HTMLElement;
  drawer: HTMLElement;
  closeButton: HTMLButtonElement;
}

export function createAccountDrawerController(elements: AccountDrawerElements): {
  close: () => void;
  wireEvents: () => void;
} {
  const overlay = createOverlayController({
    backdrop: elements.backdrop,
    focusRoot: elements.drawer,
    closeButton: elements.closeButton,
    inertTargets: [elements.bettingHeader, elements.bettingMain],
    trigger: elements.accountButton,
    bodyClass: "account-drawer-open",
  });
  return { close: overlay.close, wireEvents: overlay.wireEvents };
}
