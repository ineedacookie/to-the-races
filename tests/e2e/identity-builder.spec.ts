import { expect, test } from "@playwright/test";

test("the bleacher builder keeps nickname tools compact and clear", async ({ page }) => {
  await page.goto("/bet/");

  await expect(page.getByText("Pixel People wardrobe")).toHaveCount(0);
  await expect(page.getByText(/wardrobe goblin/i)).toHaveCount(0);
  await expect(page.locator("#nickname")).toBeVisible();
  await expect(page.locator("#random-name img")).toHaveAttribute(
    "src",
    "/static/assets/ui/dice.png",
  );

  const nicknameBounds = await page.locator("#nickname").boundingBox();
  const diceBounds = await page.locator("#random-name").boundingBox();
  expect(nicknameBounds).not.toBeNull();
  expect(diceBounds).not.toBeNull();
  expect(diceBounds?.x ?? 0).toBeGreaterThanOrEqual(
    (nicknameBounds?.x ?? 0) + (nicknameBounds?.width ?? 0),
  );

  await page.getByRole("button", { name: "Suggest a random nickname" }).click();
  await expect(page.locator("#nickname")).not.toHaveValue("");

  await page.locator("#identity-mode-login").click();
  await expect(page.locator("#avatar-preview-canvas")).toBeHidden();
  await expect(page.locator(".avatar-builder__controls")).toBeHidden();
  await expect(page.locator("#nickname")).toBeVisible();
});

test("item cards leave timing guidance to their section headers", async ({ page }) => {
  await page.goto("/bet/");
  await page.locator("#nickname").fill(`Clarity-${Date.now()}`);
  await page.getByRole("button", { name: "Get my sheet" }).click();

  await expect(page.locator(".item-card")).toHaveCount(27);
  await expect(page.locator(".item-card__timing")).toHaveCount(0);
  await expect(page.locator(".item-card__target-hint")).toHaveCount(0);

  const descriptions = await page.locator(".item-card__header p").allTextContents();
  expect(descriptions).toHaveLength(27);
  expect(
    descriptions.every(
      (description) =>
        !description.startsWith("LIVE") &&
        !description.toLowerCase().includes("proc") &&
        !description.includes("Activate during") &&
        !description.includes("Assign during"),
    ),
  ).toBe(true);
});

test("icon tabs switch sheets while the account icon opens the account", async ({ page }) => {
  await page.goto("/bet/");
  await page.locator("#nickname").fill(`Tabs-${Date.now()}`);
  await page.getByRole("button", { name: "Get my sheet" }).click();

  const tabs = page.getByRole("tab");
  await expect(tabs).toHaveCount(5);
  await expect(tabs.nth(0)).toHaveAccessibleName("Chat");
  await expect(tabs.nth(1)).toHaveAccessibleName("Bet");
  await expect(tabs.nth(2)).toHaveAccessibleName("Inventory, 0 items");
  await expect(tabs.nth(3)).toHaveAccessibleName("Shop");
  await expect(tabs.nth(4)).toHaveAccessibleName("Boards");
  await expect(page.getByRole("tab", { name: "Bet" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.locator(".bet-sheet-tabs svg")).toHaveCount(5);
  await expect(page.locator("#inventory-tab-count")).toHaveText("0");

  await page.getByRole("tab", { name: "Chat" }).click();
  await expect(page.locator("#bet-sheet-chat")).toBeVisible();
  await page.getByRole("tab", { name: "Inventory" }).click();
  await expect(page.locator("#bet-sheet-inventory")).toBeVisible();
  await page.getByRole("tab", { name: "Shop" }).click();
  await expect(page.locator("#bet-sheet-shop")).toBeVisible();
  await page.getByRole("tab", { name: "Boards" }).click();
  await expect(page.locator("#bet-sheet-boards")).toBeVisible();

  await expect(page.getByRole("button", { name: "Open game menu" })).toHaveCount(0);
  const accountButton = page.getByRole("button", { name: "Open account" });
  await accountButton.click();
  await expect(page.getByRole("heading", { name: "Your account" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Close account" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("#account-drawer-backdrop")).toBeHidden();
  await expect(accountButton).toBeFocused();
});
