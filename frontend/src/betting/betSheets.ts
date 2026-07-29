type BetSheetName = "chat" | "bet" | "tune-in" | "inventory" | "shop" | "boards";

interface BetSheetElements {
  tabs: HTMLButtonElement[];
  panels: HTMLElement[];
}

interface BetSheetController {
  select: (sheet: BetSheetName) => void;
  wireEvents: () => void;
}

function sheetName(tab: HTMLButtonElement): BetSheetName {
  const value = tab.dataset.betSheet;
  if (
    value === "chat" ||
    value === "bet" ||
    value === "tune-in" ||
    value === "inventory" ||
    value === "shop" ||
    value === "boards"
  ) {
    return value;
  }
  throw new Error(`Unknown betting sheet: ${value ?? "missing"}`);
}

export function createBetSheetController(elements: BetSheetElements): BetSheetController {
  function select(sheet: BetSheetName): void {
    for (const tab of elements.tabs) {
      const selected = sheetName(tab) === sheet;
      tab.classList.toggle("is-selected", selected);
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
    }
    for (const panel of elements.panels) {
      panel.hidden = panel.dataset.betSheetContent !== sheet;
    }
  }

  function wireEvents(): void {
    for (const tab of elements.tabs) {
      tab.addEventListener("click", () => {
        select(sheetName(tab));
      });
      tab.addEventListener("keydown", (event) => {
        const currentIndex = elements.tabs.indexOf(tab);
        let nextIndex: number | null = null;
        if (event.key === "ArrowRight") {
          nextIndex = (currentIndex + 1) % elements.tabs.length;
        } else if (event.key === "ArrowLeft") {
          nextIndex = (currentIndex - 1 + elements.tabs.length) % elements.tabs.length;
        } else if (event.key === "Home") {
          nextIndex = 0;
        } else if (event.key === "End") {
          nextIndex = elements.tabs.length - 1;
        }
        if (nextIndex === null) {
          return;
        }
        event.preventDefault();
        const nextTab = elements.tabs[nextIndex];
        if (nextTab !== undefined) {
          select(sheetName(nextTab));
          nextTab.focus();
        }
      });
    }
  }

  return { select, wireEvents };
}
