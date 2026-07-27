import { expect, test } from "@playwright/test";

test("a phone joins, places a bet, and shares live state with the display", async ({
  browser,
  baseURL,
}) => {
  const displayContext = await browser.newContext({
    baseURL,
    viewport: { width: 1440, height: 900 },
  });
  const phoneContext = await browser.newContext({
    baseURL,
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  await phoneContext.addInitScript(() => {
    Object.defineProperty(globalThis.crypto, "randomUUID", {
      configurable: true,
      value: undefined,
    });
  });
  const display = await displayContext.newPage();
  const phone = await phoneContext.newPage();

  await display.goto("/display/");
  await expect(display.locator("#game-canvas canvas")).toBeVisible();
  const grandstandAlignment = await display.evaluate(() => {
    const viewport = document.querySelector(".race-viewport")?.getBoundingClientRect();
    const grandstand = document.querySelector("#grandstand")?.getBoundingClientRect();
    if (viewport === undefined || grandstand === undefined) {
      return null;
    }
    const sceneWidth = Math.min(viewport.width, viewport.height * (16 / 9));
    return {
      actualWidth: grandstand.width,
      expectedWidth: sceneWidth * (1_104 / 1_280),
    };
  });
  expect(grandstandAlignment).not.toBeNull();
  expect(
    Math.abs(
      (grandstandAlignment?.actualWidth ?? 0) -
        (grandstandAlignment?.expectedWidth ?? 0),
    ),
  ).toBeLessThan(2);
  const joinCardPlacement = await display.evaluate(() => {
    const card = document.querySelector("#join-card")?.getBoundingClientRect();
    const viewport = document.querySelector(".race-viewport")?.getBoundingClientRect();
    if (card === undefined || viewport === undefined) {
      return null;
    }
    return {
      cardRight: card.right,
      raceViewportLeft: viewport.left,
    };
  });
  expect(joinCardPlacement).not.toBeNull();
  expect(joinCardPlacement?.cardRight ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(
    joinCardPlacement?.raceViewportLeft ?? 0,
  );
  await expect(display.getByText("Scan to bet")).toBeVisible();
  await expect(display.locator("#display-connection")).toHaveText("Live");
  const bonejaminName = display.locator(".racer-name-tag").filter({ hasText: "Bonejamin" });
  await expect(bonejaminName).toBeVisible();
  const racerNameLayering = await bonejaminName.evaluate((element) => {
    const labelBounds = element.getBoundingClientRect();
    const grandstand = document.querySelector("#grandstand");
    const nameLayer = document.querySelector("#racer-name-layer");
    if (grandstand === null || nameLayer === null) {
      return null;
    }
    const grandstandBounds = grandstand.getBoundingClientRect();
    return {
      grandstandZ: Number.parseInt(getComputedStyle(grandstand).zIndex, 10),
      labelZ: Number.parseInt(getComputedStyle(nameLayer).zIndex, 10),
      overlapsGrandstand:
        labelBounds.top < grandstandBounds.bottom &&
        labelBounds.bottom > grandstandBounds.top,
    };
  });
  expect(racerNameLayering?.overlapsGrandstand).toBe(true);
  expect(racerNameLayering?.labelZ ?? 0).toBeGreaterThan(
    racerNameLayering?.grandstandZ ?? 0,
  );
  const displayFontSizes = await display.evaluate(() => {
    const fontSize = (selector: string) => {
      const element = document.querySelector(selector);
      return element === null ? 0 : Number.parseFloat(getComputedStyle(element).fontSize);
    };
    return {
      hud: fontSize(".race-hud strong"),
      joinPrompt: fontSize(".join-card strong"),
      racerName: fontSize(".racer-name-tag"),
      rowName: fontSize(".grandstand__row-name"),
      seatName: fontSize(".grandstand__seat-name"),
    };
  });
  expect(displayFontSizes.hud).toBeGreaterThanOrEqual(32);
  expect(displayFontSizes.joinPrompt).toBeGreaterThanOrEqual(22);
  expect(displayFontSizes.racerName).toBeGreaterThanOrEqual(18);
  expect(displayFontSizes.rowName).toBeGreaterThanOrEqual(8);
  expect(displayFontSizes.seatName).toBeGreaterThanOrEqual(10);

  await phone.goto("/bet/");
  await expect
    .poll(() => phone.evaluate(() => typeof globalThis.crypto.randomUUID))
    .toBe("undefined");
  await expect(phone.getByRole("heading", { name: "What should the bookie call you?" })).toBeVisible();
  await expect(phone.locator("#connection-text")).toHaveText("Live");
  await expect(phone.locator("#avatar-preview-canvas .avatar-preview__layer")).toHaveCount(6);
  await phone.getByRole("button", { name: "Random look" }).click();
  await phone.getByRole("button", { name: "Random name" }).click();
  await expect(phone.locator("#nickname")).not.toHaveValue("");

  const nickname = `Runner-${String(Date.now()).slice(-8)}`;
  await phone.locator("#nickname").fill(nickname);
  await phone.getByRole("button", { name: "Get my sheet" }).click();
  await expect(phone.locator("#player-name")).toHaveText(nickname);
  await expect(phone.locator("#account-toolbar")).toBeVisible();
  await expect(phone.locator(".racer-card")).toHaveCount(4);
  await expect(display.locator("#grandstand-crowd-rows")).toContainText(nickname);
  const crowdPerson = display
    .locator("#grandstand-crowd-rows [data-player-id]")
    .filter({ hasText: nickname });
  await expect(
    crowdPerson.locator(".grandstand__character img"),
  ).toHaveAttribute("src", /\/api\/players\/\d+\/avatar\/\?v=[a-f0-9]{16}/);

  await phone.locator("#custom-stake").fill("250");
  const firstBet = phone.locator(".bet-button").first();
  await expect(firstBet).toHaveText("Bet $250");
  await expect(firstBet).toBeEnabled({ timeout: 25_000 });
  await firstBet.click();
  await expect(phone.locator("#toast")).toContainText("Good luck");
  await expect(phone.locator("#bets-list li")).toHaveCount(1);
  await expect(display.locator("#display-pot")).not.toHaveText("$0");

  await phone.getByRole("button", { name: "Open game menu" }).click();
  await expect(phone.locator("#game-menu")).toBeVisible();
  await expect(phone.getByRole("tab", { name: "Shop" })).toHaveAttribute(
    "aria-selected",
    "true",
  );

  const firstSchemeCard = phone.locator(".item-card").first();
  const firstScheme = firstSchemeCard.locator(".item-buy-btn");
  await expect(firstScheme).toBeEnabled();
  await firstScheme.click();

  const bananaScheme = phone.locator(".item-card").filter({ hasText: "Banana of Binding" });
  await bananaScheme.locator(".item-buy-btn").click();
  const guardScheme = phone.locator(".item-card").filter({ hasText: "Rubber-Bone Broth" });
  await guardScheme.locator(".item-buy-btn").click();
  const oilScheme = phone.locator(".item-card").filter({ hasText: "Open-Source Oil Slick" });
  await oilScheme.locator(".item-buy-btn").click();

  await phone.getByRole("tab", { name: "Inventory" }).click();
  const bagItems = phone.locator(
    "#item-inventory-grid .inventory-item-card:not(.inventory-item-card--empty)",
  );
  await expect(bagItems).toHaveCount(4);
  const oilBagItem = bagItems.filter({ hasText: "Open-Source Oil Slick" });
  phone.once("dialog", (dialog) => dialog.accept());
  await oilBagItem.locator(".inventory-item-trash-button").click();
  await expect(bagItems).toHaveCount(3);

  const quantumBagItem = bagItems.filter({ hasText: "Quantum Quencher" });
  await quantumBagItem.locator(".inventory-item-use-button").click();
  await expect(phone.locator("#item-target-grid .item-target-portrait")).toHaveCount(4);
  await phone.locator("#item-target-grid .item-target-portrait").nth(1).click();
  await expect(phone.locator("#my-schemes-list li:not(.empty-state)")).toHaveCount(1);

  const bananaBagItem = bagItems.filter({ hasText: "Banana of Binding" });
  await expect(
    bananaBagItem.locator(".inventory-item-use-button"),
  ).toHaveText("Use during race");
  await expect(bagItems).toHaveCount(2);

  await phone.getByRole("tab", { name: "Shop" }).click();
  const availableSeat = phone.locator(".seat-claim-btn:not(:disabled)").first();
  await expect(availableSeat).toBeEnabled();
  await availableSeat.click();
  await expect(display.locator("#grandstand-seats")).toContainText(nickname);
  await expect(display.locator("#grandstand-crowd-rows")).not.toContainText(nickname);

  await phone.getByRole("tab", { name: "Inventory" }).click();
  await expect(phone.locator("#menu-panel-inventory")).toBeVisible();
  await expect(bagItems.filter({ hasText: "Rubber-Bone Broth" })).toHaveCount(1);
  await expect(bagItems.filter({ hasText: "Banana of Binding" })).toHaveCount(1);
  await phone.getByRole("tab", { name: "Account" }).click();
  await expect(phone.locator("#account-name")).toHaveText(nickname);
  const originalAvatarSrc = await phone.locator("#account-avatar").getAttribute("src");
  expect(originalAvatarSrc).toMatch(/\/api\/players\/\d+\/avatar\/\?v=[a-f0-9]{16}/);
  await phone.getByRole("button", { name: "Edit name & character" }).click();
  await expect(phone.locator("#identity-panel")).toBeVisible();
  await expect(phone.locator("#nickname")).toHaveValue(nickname);
  await phone.getByRole("button", { name: "Next hair" }).click();
  await phone.getByRole("button", { name: "Save name & look" }).click();
  await expect(phone.locator("#account-toolbar")).toBeVisible();
  await expect(phone.locator("#toast")).toContainText("character is updated");
  await expect(phone.locator("#account-avatar")).not.toHaveAttribute(
    "src",
    originalAvatarSrc ?? "",
  );
  const updatedAvatarSrc = await phone.locator("#account-avatar").getAttribute("src");

  const returningContext = await browser.newContext({
    baseURL,
    viewport: { width: 390, height: 844 },
  });
  const returningPhone = await returningContext.newPage();
  await returningPhone.goto("/bet/");
  await returningPhone.locator("#identity-mode-login").click();
  await expect(returningPhone.locator("#avatar-builder")).toBeHidden();
  await returningPhone.locator("#nickname").fill(nickname.toLowerCase());
  await returningPhone.locator("#identity-submit").click();
  await expect(returningPhone.locator("#player-name")).toHaveText(nickname);
  await returningPhone.getByRole("button", { name: "Open game menu" }).click();
  await returningPhone.getByRole("tab", { name: "Account" }).click();
  await expect(returningPhone.locator("#account-avatar")).toHaveAttribute(
    "src",
    updatedAvatarSrc ?? "",
  );
  await returningContext.close();

  await expect(phone.locator("#crowd-bar")).toBeVisible({ timeout: 20_000 });
  await expect(phone.locator("#crowd-target")).toHaveCount(0);
  await phone.getByRole("button", { name: "Cheer" }).click();
  const claimedSeat = display.locator("#grandstand-seats > li").filter({ hasText: nickname });
  const cheerBubble = display.locator(".reaction-bubble--seated").filter({ hasText: nickname });
  await expect(cheerBubble).toBeVisible();
  await expect(cheerBubble).toHaveCSS("background-color", "rgb(47, 157, 87)");
  await expect(claimedSeat).toHaveClass(/grandstand__seat--reacting-cheer/);
  await expect(phone.getByRole("button", { name: "Boo" })).toBeDisabled();
  await expect(phone.getByRole("button", { name: "Boo" })).toBeEnabled({
    timeout: 5_000,
  });
  await phone.getByRole("button", { name: "Cry" }).click();
  const cryBubble = display.locator(".reaction-bubble--cry").filter({ hasText: nickname });
  await expect(cryBubble).toBeVisible();
  await expect(cryBubble).toHaveCSS("background-color", "rgb(63, 114, 216)");
  await expect(claimedSeat).toHaveClass(/grandstand__seat--reacting-cry/);
  await expect(claimedSeat.locator(".grandstand__character")).toHaveCSS(
    "animation-name",
    "grandstand-cry",
  );
  const wireReaction = phone.locator("#message-feed .message-feed__reaction").first();
  await expect(wireReaction.locator(".message-feed__author")).toHaveText(nickname);
  await expect(wireReaction.locator(".message-feed__message")).toHaveText("WAAAH!");
  await expect(display.locator("#display-phase")).toHaveText("They're off!", {
    timeout: 15_000,
  });
  await expect(display.locator("#display-countdown")).toHaveText("LIVE");
  await expect(phone.locator("#countdown")).toHaveText("LIVE");
  await phone.getByRole("button", { name: "Open game menu" }).click();
  await phone.getByRole("tab", { name: "Inventory" }).click();
  await expect(
    bananaBagItem.locator(".inventory-item-use-button"),
  ).toHaveText("Use");
  await bananaBagItem.locator(".inventory-item-use-button").click();
  await phone.locator("#item-target-grid .item-target-portrait").first().click();
  await expect(phone.locator("#my-schemes-list li:not(.empty-state)")).toHaveCount(2);
  await expect(bagItems).toHaveCount(1);
  await phone.getByRole("button", { name: "Close game menu" }).click();

  await phoneContext.setOffline(true);
  await expect(phone.locator("#connection-text")).toHaveText("Reconnecting…");
  await expect(claimedSeat).toHaveCount(0);
  await expect(
    display.locator("#grandstand-seats > li").filter({ hasText: "VIEWER OFFLINE" }),
  ).toHaveCount(1);
  await phoneContext.setOffline(false);
  await expect(phone.locator("#connection-text")).toHaveText("Live", { timeout: 12_000 });
  await expect(claimedSeat).toHaveCount(1);

  await expect(phone.locator("#phase-label")).toHaveText("Betting open", {
    timeout: 15_000,
  });
  await phone.getByRole("button", { name: "Open game menu" }).click();
  await phone.getByRole("tab", { name: "Inventory" }).click();
  await expect(bagItems.filter({ hasText: "Rubber-Bone Broth" })).toHaveCount(1);
  await expect(phone.locator("#my-schemes-list li:not(.empty-state)")).toHaveCount(0);
  await bagItems
    .filter({ hasText: "Rubber-Bone Broth" })
    .locator(".inventory-item-use-button")
    .click();
  await phone.locator("#item-target-grid .item-target-portrait").first().click();
  await expect(phone.locator("#my-schemes-list li:not(.empty-state)")).toHaveCount(1);

  await phoneContext.close();
  await displayContext.close();
});
