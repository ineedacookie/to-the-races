const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface OverlayOptions {
  backdrop: HTMLElement;
  focusRoot: HTMLElement;
  closeButton: HTMLButtonElement;
  inertTargets: HTMLElement[];
  trigger?: HTMLButtonElement;
  fallbackFocus?: HTMLElement;
  bodyClass?: string;
  onOpen?: () => void;
  onClose?: () => void;
}

interface OverlayController {
  open: (returnFocus?: HTMLElement) => void;
  close: () => void;
  wireEvents: () => void;
}

function canRestoreFocus(element: HTMLElement | null): element is HTMLElement {
  return element !== null && element.isConnected && element.closest("[hidden]") === null;
}

export function createOverlayController(options: OverlayOptions): OverlayController {
  let returnFocus: HTMLElement | null = null;

  function open(explicitReturnFocus?: HTMLElement): void {
    if (!options.backdrop.hidden) {
      return;
    }
    returnFocus =
      explicitReturnFocus ??
      (document.activeElement instanceof HTMLElement
        ? document.activeElement
        : options.trigger ?? null);
    options.backdrop.hidden = false;
    options.trigger?.setAttribute("aria-expanded", "true");
    if (options.bodyClass !== undefined) {
      document.body.classList.add(options.bodyClass);
    }
    for (const target of options.inertTargets) {
      target.inert = true;
    }
    options.onOpen?.();
    options.closeButton.focus();
  }

  function close(): void {
    if (options.backdrop.hidden) {
      return;
    }
    options.backdrop.hidden = true;
    options.trigger?.setAttribute("aria-expanded", "false");
    if (options.bodyClass !== undefined) {
      document.body.classList.remove(options.bodyClass);
    }
    for (const target of options.inertTargets) {
      target.inert = false;
    }
    options.onClose?.();
    const focusTarget = canRestoreFocus(returnFocus)
      ? returnFocus
      : canRestoreFocus(options.fallbackFocus ?? null)
        ? options.fallbackFocus
        : null;
    focusTarget?.focus();
    returnFocus = null;
  }

  function trapFocus(event: KeyboardEvent): void {
    const focusable = Array.from(
      options.focusRoot.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter((element) => !element.hidden);
    const first = focusable[0];
    const last = focusable.at(-1);
    if (first === undefined || last === undefined) {
      event.preventDefault();
      options.closeButton.focus();
      return;
    }
    const focusOutside = !options.focusRoot.contains(document.activeElement);
    if (event.shiftKey && (document.activeElement === first || focusOutside)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (document.activeElement === last || focusOutside)) {
      event.preventDefault();
      first.focus();
    }
  }

  function wireEvents(): void {
    options.trigger?.addEventListener("click", () => {
      open();
    });
    options.closeButton.addEventListener("click", close);
    options.backdrop.addEventListener("click", (event) => {
      if (event.target === options.backdrop) {
        close();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (options.backdrop.hidden) {
        return;
      }
      if (event.key === "Escape") {
        close();
      } else if (event.key === "Tab") {
        trapFocus(event);
      }
    });
  }

  return { open, close, wireEvents };
}
