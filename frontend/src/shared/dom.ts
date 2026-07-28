export function required<T extends Element>(selector: string, root: ParentNode = document): T {
  const element = root.querySelector<T>(selector);
  if (element === null) {
    throw new Error(`Missing required element: ${selector}`);
  }
  return element;
}

export function renderEmptyState(
  parent: Element,
  message: string,
  tag: "li" | "p" = "p",
  className = "empty-state",
): HTMLElement {
  parent.replaceChildren();
  const empty = document.createElement(tag);
  empty.className = className;
  empty.textContent = message;
  parent.append(empty);
  return empty;
}
