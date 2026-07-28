import { expect, test, type Browser, type Page } from "@playwright/test";

async function createPlayer(browser: Browser, baseURL: string | undefined, prefix: string) {
  const context = await browser.newContext({
    baseURL,
    viewport: { width: 390, height: 844 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  await page.goto("/bet/");
  const nickname = `${prefix}-${String(Date.now()).slice(-8)}`;
  await page.locator("#nickname").fill(nickname);
  await page.getByRole("button", { name: "Get my sheet" }).click();
  await expect(page.locator("#player-name")).toHaveText(nickname);
  return { context, page, nickname };
}

async function waitForFreshOpen(page: Page): Promise<void> {
  await expect
    .poll(
      async () => {
        const phase = await page.locator("#phase-label").textContent();
        const countdown = Number.parseInt(
          (await page.locator("#countdown").textContent()) ?? "0",
          10,
        );
        return phase === "Betting open" && countdown >= 7;
      },
      { timeout: 60_000 },
    )
    .toBe(true);
}

function formatTestMoney(cents: number): string {
  return cents % 100 === 0 ? `$${cents / 100}` : `$${(cents / 100).toFixed(2)}`;
}

test("the public house account exposes totals, history, and recent activity", async ({ page }) => {
  await page.goto("/house/");

  await expect(page.getByRole("heading", { name: "The House Account" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Lifetime breakdown" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Round history" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent activity" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Return to betting" })).toHaveAttribute(
    "href",
    "/bet/",
  );
});

test("fractional bets unlock one track-medic bailout below ten dollars", async ({
  browser,
  baseURL,
}) => {
  test.setTimeout(90_000);
  const { context, page } = await createPlayer(browser, baseURL, "Medic");
  await waitForFreshOpen(page);

  await page.getByRole("tab", { name: "Shop" }).click();
  const expanded = page.locator(".upgrade-card").filter({ hasText: "Expanded Pockets" });
  await expanded.locator(".upgrade-buy-btn").click();
  await expect(page.locator("#balance")).toHaveText("$350");
  for (const [itemName, expectedBalance] of [
    ["Spring-Loaded Boxing Glove", "$270"],
    ["Identity Crisis Cordial", "$210"],
    ["Portal Gate", "$150"],
  ] as const) {
    const item = page.locator(".item-card").filter({ hasText: itemName });
    await item.locator(".item-buy-btn").click();
    await expect(page.locator("#balance")).toHaveText(expectedBalance);
  }
  await page.getByRole("tab", { name: "Bet" }).click();

  const stake = page.locator("#custom-stake");
  await expect(stake).toHaveAttribute("max", "150");
  const shortcutTops = await page
    .locator(".lineup-stake__shortcuts button")
    .evaluateAll((buttons) => buttons.map((button) => button.getBoundingClientRect().top));
  expect(shortcutTops).toHaveLength(3);
  expect(Math.max(...shortcutTops) - Math.min(...shortcutTops)).toBeLessThan(1);
  await page.getByRole("button", { name: "Add $5 to stake" }).click();
  await expect(stake).toHaveValue("10");
  await page.getByRole("button", { name: "Add $10 to stake" }).click();
  await expect(stake).toHaveValue("20");
  const maxStake = page.getByRole("button", { name: "Set maximum stake" });
  await maxStake.click();
  await expect(stake).toHaveValue("150");
  await expect(maxStake).toBeDisabled();
  await stake.fill("149.55");
  await expect(page.locator("#stake-hint")).toContainText("$150 cap");
  const betButton = page.locator(".bet-button").first();
  await expect(betButton).toHaveText("Bet $149.55");
  await expect(betButton).toBeEnabled();
  await page.route(
    "**/api/bets/",
    async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 400));
      await route.continue();
    },
    { times: 1 },
  );
  await betButton.click();
  await expect(page.locator(".bet-button").nth(1)).toBeDisabled();

  await expect(page.locator("#balance")).toHaveText("$0.45");
  await expect(stake).toHaveAttribute("max", "0.45");
  await expect(page.locator("#track-medic-callout")).toBeVisible();
  await page.locator("#track-medic-open").click();
  await expect(page.locator("#track-medic-backdrop")).toBeVisible();

  const wounds = page.locator(".track-medic-wound");
  const woundCount = await wounds.count();
  expect(woundCount).toBeGreaterThanOrEqual(2);
  expect(woundCount).toBeLessThanOrEqual(5);

  await expect
    .poll(() => page.locator("#phase-label").textContent(), { timeout: 30_000 })
    .not.toBe("Betting open");
  await expect(page.locator("#track-medic-callout")).toBeVisible();
  await expect(page.locator("#track-medic-backdrop")).toBeVisible();

  for (let patched = 0; patched < woundCount - 1; patched += 1) {
    await page.locator(".track-medic-wound:not(.is-patched)").first().click();
    await expect(page.locator(".track-medic-wound.is-patched")).toHaveCount(patched + 1);
  }
  await page.locator(".track-medic-wound:not(.is-patched)").first().click();

  await expect(page.locator("#toast")).toContainText("Track medic paid $20");
  await expect(page.locator("#balance")).toHaveText("$20.45");
  await expect(page.locator("#track-medic-backdrop")).toBeHidden();
  await expect(page.locator("#track-medic-callout")).toBeHidden();
  await expect
    .poll(() => page.evaluate(() => (document.activeElement as HTMLElement | null)?.id))
    .toBe("custom-stake");
  await context.close();
});

test("inventory tiers purchase in order and remain after reload", async ({ browser, baseURL }) => {
  const { context, page } = await createPlayer(browser, baseURL, "Upgrader");
  await page.getByRole("tab", { name: "Shop" }).click();

  const expanded = page.locator(".upgrade-card").filter({ hasText: "Expanded Pockets" });
  await expect(expanded.locator(".upgrade-buy-btn")).toHaveText("Buy · $150");
  await expanded.locator(".upgrade-buy-btn").click();
  await expect(expanded.locator(".upgrade-buy-btn")).toHaveText("Owned");

  const deep = page.locator(".upgrade-card").filter({ hasText: "Deep Pockets" });
  await expect(deep.locator(".upgrade-buy-btn")).toHaveText("Buy · $350");
  await deep.locator(".upgrade-buy-btn").click();
  await expect(deep.locator(".upgrade-buy-btn")).toHaveText("Owned");

  await page.getByRole("tab", { name: "Inventory" }).click();
  await expect(page.locator("#inventory-summary")).toHaveText("0 / 8 items");
  await page.getByRole("button", { name: "Open account" }).click();
  await expect(page.locator("#account-inventory")).toContainText("capacity 8 slots");
  await expect(page.locator("#account-inventory")).toContainText("2 permanent upgrades");

  await page.reload();
  await page.getByRole("tab", { name: "Inventory" }).click();
  await expect(page.locator("#inventory-summary")).toHaveText("0 / 8 items");
  await context.close();
});

test("prestige seats persist, escalate by $5, and reset next round", async ({
  browser,
  baseURL,
}) => {
  test.setTimeout(100_000);
  const first = await createPlayer(browser, baseURL, "SeatA");
  const second = await createPlayer(browser, baseURL, "SeatB");
  await waitForFreshOpen(first.page);

  await first.page.getByRole("tab", { name: "Shop" }).click();
  await second.page.getByRole("tab", { name: "Shop" }).click();
  const firstSeat = first.page.locator(".seat-card").filter({ hasText: "Finish Barrel" });
  const secondSeat = second.page.locator(".seat-card").filter({ hasText: "Finish Barrel" });

  const openingClaimText = (await firstSeat.locator(".seat-claim-btn").textContent()) ?? "";
  const openingPriceMatch = openingClaimText.match(/\$([\d.]+)/);
  expect(openingPriceMatch).not.toBeNull();
  const openingPriceCents = Math.round(Number.parseFloat(openingPriceMatch?.[1] ?? "0") * 100);
  await firstSeat.locator(".seat-claim-btn").click();
  await expect(firstSeat.locator(".seat-claim-btn")).toHaveText("Your seat");
  await expect(first.page.locator("#balance")).toHaveText(
    formatTestMoney(50_000 - openingPriceCents),
  );

  await expect(secondSeat.locator(".seat-claim-btn")).toHaveText(
    `Take over · ${formatTestMoney(openingPriceCents + 500)}`,
  );
  await secondSeat.locator(".seat-claim-btn").click();
  await expect(secondSeat.locator(".seat-claim-btn")).toHaveText("Your seat");
  await expect(second.page.locator("#balance")).toHaveText(
    formatTestMoney(50_000 - openingPriceCents - 500),
  );
  await expect(first.page.locator("#balance")).toHaveText(
    formatTestMoney(50_000 - openingPriceCents + Math.floor(openingPriceCents / 2)),
  );
  await expect(firstSeat.locator(".seat-owner")).toContainText(second.nickname);
  await expect(first.page.locator("#toast")).toContainText(
    "You were bumped from Finish Barrel. 50% of your purchase was refunded.",
  );

  const currentRound = await second.page.locator("#round-label").textContent();
  await expect
    .poll(
      async () => {
        const phase = await second.page.locator("#phase-label").textContent();
        const nextRound = await second.page.locator("#round-label").textContent();
        return phase === "Betting open" && nextRound !== currentRound;
      },
      { timeout: 80_000 },
    )
    .toBe(true);

  await expect(secondSeat.locator(".seat-claim-btn")).toHaveText("Your seat");
  await expect(secondSeat.locator(".seat-owner")).toContainText("$40");
  await expect(firstSeat.locator(".seat-claim-btn")).toHaveText("Take over · $40");

  await first.context.close();
  await second.context.close();
});
