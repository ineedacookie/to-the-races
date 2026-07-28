import { expect, test } from "@playwright/test";

test("a phone joins, places a bet, and shares live state with the display", async ({
  browser,
  baseURL,
}) => {
  test.setTimeout(120_000);
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
  await display.evaluate(() => {
    const grandstand = document.querySelector("#grandstand");
    if (grandstand === null) {
      return;
    }
    const tracker = { count: 0, active: false };
    new MutationObserver(() => {
      const active = grandstand.classList.contains("grandstand--celebrating");
      if (active && !tracker.active) {
        tracker.count += 1;
      }
      tracker.active = active;
    }).observe(grandstand, { attributes: true, attributeFilter: ["class"] });
    (window as unknown as { __firstFinisherTracker: typeof tracker }).__firstFinisherTracker =
      tracker;
  });
  const grandstandAlignment = await display.evaluate(() => {
    const viewport = document.querySelector(".race-viewport")?.getBoundingClientRect();
    const grandstand = document.querySelector("#grandstand")?.getBoundingClientRect();
    const hud = document.querySelector(".race-hud")?.getBoundingClientRect();
    if (viewport === undefined || grandstand === undefined || hud === undefined) {
      return null;
    }
    const sceneWidth = Math.min(viewport.width, viewport.height * (16 / 9));
    return {
      actualWidth: grandstand.width,
      expectedWidth: sceneWidth * (1_104 / 1_280),
      grandstandTop: grandstand.top,
      hudBottom: hud.bottom,
      viewportTop: viewport.top,
    };
  });
  expect(grandstandAlignment).not.toBeNull();
  expect(
    Math.abs(
      (grandstandAlignment?.actualWidth ?? 0) -
        (grandstandAlignment?.expectedWidth ?? 0),
    ),
  ).toBeLessThan(2);
  expect(grandstandAlignment?.grandstandTop ?? 0).toBeGreaterThanOrEqual(
    grandstandAlignment?.viewportTop ?? Number.POSITIVE_INFINITY,
  );
  expect(grandstandAlignment?.grandstandTop ?? 0).toBeGreaterThanOrEqual(
    grandstandAlignment?.hudBottom ?? Number.POSITIVE_INFINITY,
  );
  const joinCardPlacement = await display.evaluate(() => {
    const card = document.querySelector("#join-card")?.getBoundingClientRect();
    const qrCode = document.querySelector("#join-card img")?.getBoundingClientRect();
    const arena = document.querySelector("#grandstand")?.getBoundingClientRect();
    if (card === undefined || qrCode === undefined || arena === undefined) {
      return null;
    }
    return {
      cardWidth: card.width,
      cardRight: card.right,
      qrCodeWidth: qrCode.width,
      arenaLeft: arena.left,
    };
  });
  expect(joinCardPlacement).not.toBeNull();
  const joinCardGap =
    (joinCardPlacement?.arenaLeft ?? 0) -
    (joinCardPlacement?.cardRight ?? Number.POSITIVE_INFINITY);
  expect(joinCardGap).toBeGreaterThanOrEqual(-2);
  expect(joinCardGap).toBeLessThanOrEqual(8);
  expect(
    Math.abs(
      (joinCardPlacement?.cardWidth ?? 0) -
        (joinCardPlacement?.qrCodeWidth ?? Number.POSITIVE_INFINITY) -
        6,
    ),
  ).toBeLessThanOrEqual(1);
  const trackReportPlacement = await display.evaluate(() => {
    const report = document.querySelector<HTMLElement>("#event-card");
    const reportText = document.querySelector<HTMLElement>("#event-text");
    const viewport = document.querySelector(".race-viewport")?.getBoundingClientRect();
    const joinCard = document.querySelector("#join-card")?.getBoundingClientRect();
    if (report === null || reportText === null || viewport === undefined || joinCard === undefined) {
      return null;
    }
    reportText.textContent = "A sample track report that stays clear of the arena.";
    report.style.animation = "none";
    report.hidden = false;
    const reportBounds = report.getBoundingClientRect();
    const placement = {
      parentIsRaceLayout: report.parentElement?.classList.contains("race-layout") ?? false,
      reportRight: reportBounds.right,
      reportBottom: reportBounds.bottom,
      viewportLeft: viewport.left,
      joinCardTop: joinCard.top,
    };
    report.hidden = true;
    report.style.removeProperty("animation");
    return placement;
  });
  expect(trackReportPlacement).not.toBeNull();
  expect(trackReportPlacement?.parentIsRaceLayout).toBe(true);
  expect(trackReportPlacement?.reportRight ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(
    trackReportPlacement?.viewportLeft ?? 0,
  );
  expect(trackReportPlacement?.reportBottom ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(
    trackReportPlacement?.joinCardTop ?? 0,
  );
  await expect(display.getByText("Scan to bet")).toBeVisible();
  await expect(display.locator("#display-connection")).toHaveText("Live");
  await expect
    .poll(() => display.locator("#display-phase").textContent(), { timeout: 90_000 })
    .toMatch(/Place your bets|Final lineup/);
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
  await expect(phone.locator("#random-name img")).toHaveAttribute(
    "src",
    "/static/assets/ui/dice.png",
  );
  await phone.getByRole("button", { name: "Suggest a random nickname" }).click();
  await expect(phone.locator("#nickname")).not.toHaveValue("");

  const nickname = `Runner-${String(Date.now()).slice(-8)}`;
  await phone.locator("#nickname").fill(nickname);
  await phone.getByRole("button", { name: "Get my sheet" }).click();
  await expect(phone.locator("#player-name")).toHaveText(nickname);
  await expect(phone.locator("#account-toolbar")).toBeVisible();
  const headerControlOrder = await phone.evaluate(() => {
    const header = document.querySelector(".betting-header");
    const connection = document.querySelector("#connection-text");
    const account = document.querySelector("#account-button");
    if (header === null || connection === null || account === null) {
      return null;
    }
    const nodes = Array.from(header.children);
    return {
      connectionIndex: nodes.indexOf(connection),
      accountIndex: nodes.indexOf(account),
      accountRight: account.getBoundingClientRect().right,
      headerRight: header.getBoundingClientRect().right,
      connectionRight: connection.getBoundingClientRect().right,
      accountLeft: account.getBoundingClientRect().left,
    };
  });
  expect(headerControlOrder).not.toBeNull();
  expect(headerControlOrder?.connectionIndex ?? -1).toBeLessThan(
    headerControlOrder?.accountIndex ?? 0,
  );
  expect(headerControlOrder?.accountRight ?? 0).toBeGreaterThan(
    headerControlOrder?.connectionRight ?? 0,
  );
  expect((headerControlOrder?.headerRight ?? 0) - (headerControlOrder?.accountRight ?? 0)).toBeLessThanOrEqual(
    12,
  );
  await expect(phone.locator(".racer-card")).toHaveCount(4);
  const firstDossierHref = await phone
    .locator(".racer-card__portrait-link")
    .first()
    .getAttribute("href");
  expect(firstDossierHref).toMatch(/^\/racers\/.+\/$/);
  await expect(phone.locator(".racer-card__meta").first()).toContainText(
    /No settled starts yet|\d+-\d+/,
  );
  await expect(display.locator("#grandstand-crowd-rows")).toContainText(nickname);
  const crowdPerson = display
    .locator("#grandstand-crowd-rows [data-player-id]")
    .filter({ hasText: nickname });
  await expect(
    crowdPerson.locator(".grandstand__character img"),
  ).toHaveAttribute("src", /\/api\/players\/\d+\/avatar\/\?v=[a-f0-9]{16}/);
  const crowdNamePlacement = await crowdPerson.evaluate((element) => {
    const figure = element.querySelector(".grandstand__figure");
    const avatar = element.querySelector(".grandstand__character");
    const avatarImage = element.querySelector(".grandstand__character img");
    const name = element.querySelector(".grandstand__owner");
    if (figure === null || avatar === null || avatarImage === null || name === null) {
      return null;
    }
    const avatarBounds = avatar.getBoundingClientRect();
    const avatarImageBounds = avatarImage.getBoundingClientRect();
    const nameBounds = name.getBoundingClientRect();
    const figureBounds = figure.getBoundingClientRect();
    return {
      avatarBottom: avatarBounds.bottom,
      nameTop: nameBounds.top,
      nameBelowAvatarMidline:
        nameBounds.top >= avatarBounds.top + avatarBounds.height * 0.55,
      avatarBeforeName:
        figure.querySelector(".grandstand__character")?.nextElementSibling === name,
      nameBelowImage: nameBounds.top >= avatarImageBounds.bottom,
      figureFlexDirection: getComputedStyle(figure).flexDirection,
      nameWithinFigure:
        nameBounds.top >= figureBounds.top &&
        nameBounds.bottom <= figureBounds.bottom + 1,
    };
  });
  expect(crowdNamePlacement).not.toBeNull();
  expect(crowdNamePlacement?.figureFlexDirection).toBe("column");
  expect(crowdNamePlacement?.avatarBeforeName).toBe(true);
  expect(crowdNamePlacement?.nameBelowAvatarMidline).toBe(true);
  expect(crowdNamePlacement?.nameBelowImage).toBe(true);
  expect(crowdNamePlacement?.nameWithinFigure).toBe(true);

  await phone.locator("#custom-stake").fill("150");
  await expect(phone.locator("#phase-label")).toHaveText("Betting open", { timeout: 30_000 });
  const firstBet = phone.locator(".bet-button").first();
  await expect(firstBet).toHaveText("Bet $150");
  await expect(firstBet).toBeEnabled({ timeout: 25_000 });
  await firstBet.click();
  await expect(phone.locator("#toast")).toContainText("Good luck");
  await expect(phone.locator("#bets-list li")).toHaveCount(1);
  await expect(display.locator("#display-pot")).not.toHaveText("$0");

  await phone.getByRole("tab", { name: "Shop" }).click();
  await expect(phone.getByRole("tab", { name: "Shop" })).toHaveAttribute(
    "aria-selected",
    "true",
  );

  const quantumScheme = phone.locator(".item-card").filter({ hasText: "Quantum Quencher" });
  const quantumBuyButton = quantumScheme.locator(".item-buy-btn");
  await expect(quantumBuyButton).toBeEnabled();
  await quantumBuyButton.click();

  const bananaScheme = phone.locator(".item-card").filter({ hasText: "Banana of Binding" });
  await bananaScheme.locator(".item-buy-btn").click();
  const guardScheme = phone.locator(".item-card").filter({ hasText: "Rubber-Bone Broth" });
  await guardScheme.locator(".item-buy-btn").click();
  const oilScheme = phone.locator(".item-card").filter({ hasText: "Open-Source Oil Slick" });
  await oilScheme.locator(".item-buy-btn").click();
  await expect(phone.locator("#inventory-tab-count")).toHaveText("4");
  await expect(phone.getByRole("tab", { name: "Inventory" })).toHaveAccessibleName(
    "Inventory, 4 items",
  );

  await phone.getByRole("tab", { name: "Inventory" }).click();
  const bagItems = phone.locator(
    "#item-inventory-grid .inventory-item-card:not(.inventory-item-card--empty)",
  );
  await expect(bagItems).toHaveCount(4);
  const oilBagItem = bagItems.filter({ hasText: "Open-Source Oil Slick" });
  phone.once("dialog", (dialog) => dialog.accept());
  await oilBagItem.locator(".inventory-item-trash-button").click();
  await expect(bagItems).toHaveCount(3);
  await expect(phone.locator("#inventory-tab-count")).toHaveText("3");

  const quantumBagItem = bagItems.filter({ hasText: "Quantum Quencher" });
  await quantumBagItem.locator(".inventory-item-use-button").click();
  await expect(phone.locator("#item-target-grid .item-target-portrait")).toHaveCount(4);
  await phone.locator("#item-target-grid .item-target-portrait").nth(1).click();
  await expect(phone.locator("#my-schemes-list li:not(.empty-state)")).toHaveCount(1);
  await expect(phone.locator("#inventory-tab-count")).toHaveText("2");

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
  await expect(phone.locator("#bet-sheet-inventory")).toBeVisible();
  await expect(bagItems.filter({ hasText: "Rubber-Bone Broth" })).toHaveCount(1);
  await expect(bagItems.filter({ hasText: "Banana of Binding" })).toHaveCount(1);
  await phone.getByRole("button", { name: "Open account" }).click();
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
  await expect(returningPhone.locator("#avatar-preview-canvas")).toBeHidden();
  await expect(returningPhone.locator(".avatar-builder__controls")).toBeHidden();
  await expect(returningPhone.locator("#nickname")).toBeVisible();
  await returningPhone.locator("#nickname").fill(nickname.toLowerCase());
  await returningPhone.locator("#identity-submit").click();
  await expect(returningPhone.locator("#player-name")).toHaveText(nickname);
  await returningPhone.getByRole("button", { name: "Open account" }).click();
  await expect(returningPhone.locator("#account-avatar")).toHaveAttribute(
    "src",
    updatedAvatarSrc ?? "",
  );
  await returningContext.close();

  await phone.getByRole("tab", { name: "Chat" }).click();
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
  await expect(display.locator("#racer-name-layer")).toBeHidden();
  await expect(display.locator(".racer-name-tag")).toHaveCount(0);
  await expect(display.locator("#display-countdown")).toHaveText("LIVE");
  await expect(phone.locator("#countdown")).toHaveText("LIVE");
  await phone.getByRole("tab", { name: "Bet" }).click();
  await expect(phone.locator("#lineup-overlay")).toHaveCount(0);
  const liveBetButtons = phone.locator(".bet-button");
  await expect(liveBetButtons).toHaveCount(4);
  expect(
    await liveBetButtons.evaluateAll((buttons) =>
      buttons.every((button) => (button as HTMLButtonElement).disabled),
    ),
  ).toBe(true);
  const dossierLink = phone.locator(".racer-dossier-link").first();
  await expect(dossierLink).toBeVisible();
  await expect(dossierLink).toHaveAttribute("href", /^\/racers\/.+\/$/);
  await phone.locator("#custom-stake").fill("25");
  await expect(phone.locator("#custom-stake")).toHaveValue("25");
  await expect(phone.locator("#stake-add-five")).toBeEnabled();
  await phone.locator("#stake-add-five").click();
  await expect(phone.locator("#custom-stake")).toHaveValue("30");
  await phone.getByRole("tab", { name: "Inventory" }).click();
  await expect(
    bananaBagItem.locator(".inventory-item-use-button"),
  ).toHaveText("Use");
  await bananaBagItem.locator(".inventory-item-use-button").click();
  await phone.locator("#item-target-grid .item-target-portrait").first().click();
  await expect(phone.locator("#my-schemes-list li:not(.empty-state)")).toHaveCount(2);
  await expect(bagItems).toHaveCount(1);
  await expect
    .poll(
      () =>
        display.evaluate(
          () =>
            (window as unknown as { __firstFinisherTracker?: { count: number } })
              .__firstFinisherTracker?.count ?? 0,
        ),
      { timeout: 40_000 },
    )
    .toBe(1);
  await display.waitForTimeout(2_600);
  await expect
    .poll(() =>
      display.evaluate(
        () =>
          (window as unknown as { __firstFinisherTracker?: { count: number } })
            .__firstFinisherTracker?.count ?? 0,
      ),
    )
    .toBe(1);

  await phoneContext.setOffline(true);
  await expect(phone.locator("#connection-text")).toHaveText("Reconnecting…");
  await expect(claimedSeat).toHaveCount(1);
  await expect(claimedSeat).toHaveClass(/grandstand__seat--offline/);
  await expect(claimedSeat).toContainText("OFFLINE");
  await phoneContext.setOffline(false);
  await expect(phone.locator("#connection-text")).toHaveText("Live", { timeout: 12_000 });
  await expect(claimedSeat).toHaveCount(1);
  await expect(claimedSeat).not.toHaveClass(/grandstand__seat--offline/);

  await expect(phone.locator("#phase-label")).toHaveText("Betting open", {
    timeout: 40_000,
  });
  await phone.getByRole("button", { name: "Open account" }).click();
  await expect(phone.locator("#account-betting-record")).toContainText("$150 staked");
  await expect(phone.locator("#account-betting-record")).toContainText(/1 wins|1 losses/);
  await phone.getByRole("button", { name: "Close account" }).click();
  await phone.getByRole("tab", { name: "Inventory" }).click();
  await expect(bagItems.filter({ hasText: "Rubber-Bone Broth" })).toHaveCount(1);
  await expect(phone.locator("#my-schemes-list li:not(.empty-state)")).toHaveCount(0);
  await bagItems
    .filter({ hasText: "Rubber-Bone Broth" })
    .locator(".inventory-item-use-button")
    .click();
  await phone.locator("#item-target-grid .item-target-portrait").first().click();
  await expect(phone.locator("#my-schemes-list li:not(.empty-state)")).toHaveCount(1);

  const dossier = await displayContext.newPage();
  await dossier.goto(firstDossierHref ?? "/");
  await expect(dossier.locator(".dossier-record")).toBeVisible();
  await expect(dossier.locator(".record-summary")).toContainText("Starts");
  await expect(dossier.locator(".record-history li")).not.toHaveCount(0);
  await dossier.close();

  await phoneContext.close();
  await displayContext.close();
});
