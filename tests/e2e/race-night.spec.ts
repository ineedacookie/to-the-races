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
  const display = await displayContext.newPage();
  const phone = await phoneContext.newPage();

  await display.goto("/display/");
  await expect(display.locator("#game-canvas canvas")).toBeVisible();
  await expect(display.getByText("Scan to bet")).toBeVisible();
  await expect(display.locator("#display-connection")).toHaveText("Live");

  await phone.goto("/bet/");
  await expect(phone.getByRole("heading", { name: "What should the bookie call you?" })).toBeVisible();
  await phone.getByRole("button", { name: "Surprise me" }).click();
  await expect(phone.locator("#nickname")).not.toHaveValue("");

  const nickname = `Runner-${String(Date.now()).slice(-8)}`;
  await phone.locator("#nickname").fill(nickname);
  await phone.getByRole("button", { name: "Get my sheet" }).click();
  await expect(phone.locator("#player-name")).toHaveText(nickname);
  await expect(phone.locator("#account-toolbar")).toBeVisible();
  await expect(phone.locator(".racer-card")).toHaveCount(4);

  const firstBet = phone.locator(".bet-button").first();
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
  await firstSchemeCard.locator("select").selectOption({ index: 1 });
  const firstScheme = firstSchemeCard.locator(".item-deploy-btn");
  await expect(firstScheme).toBeEnabled();
  await firstScheme.click();
  await expect(phone.locator("#my-schemes-list li")).toHaveCount(1);

  const bananaScheme = phone.locator(".item-card").filter({ hasText: "Banana of Binding" });
  await bananaScheme.locator(".item-deploy-btn").click();
  await expect(phone.locator("#my-schemes-list li")).toHaveCount(2);

  const availableSeat = phone.locator(".seat-claim-btn:not(:disabled)").first();
  await expect(availableSeat).toBeEnabled();
  await availableSeat.click();
  await expect(display.locator("#grandstand-seats")).toContainText(nickname);

  await phone.getByRole("tab", { name: "Inventory" }).click();
  await expect(phone.locator("#menu-panel-inventory")).toBeVisible();
  await phone.getByRole("tab", { name: "Account" }).click();
  await expect(phone.locator("#account-name")).toHaveText(nickname);
  await phone.getByRole("button", { name: "Close game menu" }).click();

  await expect(phone.locator("#crowd-bar")).toBeVisible({ timeout: 20_000 });
  await phone.getByRole("button", { name: "Cheer" }).click();
  await expect(display.locator(".reaction-bubble").filter({ hasText: nickname })).toBeVisible();
  await expect(display.locator("#display-phase")).toHaveText("They're off!", {
    timeout: 10_000,
  });
  await expect(display.locator("#display-countdown")).toHaveText("LIVE");
  await expect(phone.locator("#countdown")).toHaveText("LIVE");

  await phoneContext.setOffline(true);
  await expect(phone.locator("#connection-text")).toHaveText("Reconnecting…");
  await phoneContext.setOffline(false);
  await expect(phone.locator("#connection-text")).toHaveText("Live", { timeout: 12_000 });

  await expect(phone.locator("#phase-label")).toHaveText("Betting open", {
    timeout: 15_000,
  });
  await phone.getByRole("button", { name: "Open game menu" }).click();
  const nextRoundScheme = phone.locator(".item-deploy-btn").first();
  await expect(nextRoundScheme).toBeEnabled();
  await nextRoundScheme.click();
  await expect(phone.locator("#my-schemes-list li")).toHaveCount(1);

  await phoneContext.close();
  await displayContext.close();
});
