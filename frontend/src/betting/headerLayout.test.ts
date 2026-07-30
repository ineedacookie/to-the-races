import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const bettingTemplate = readFileSync(
  resolve(process.cwd(), "templates/betting/index.html"),
  "utf8",
);

describe("betting header layout", () => {
  it("places the connection pill immediately left of the account button", () => {
    const headerMatch = bettingTemplate.match(/<header class="betting-header">[\s\S]*?<\/header>/);
    expect(headerMatch).not.toBeNull();
    const header = headerMatch?.[0] ?? "";
    const connectionIndex = header.indexOf('id="connection-text"');
    const accountIndex = header.indexOf('id="account-button"');
    expect(connectionIndex).toBeGreaterThan(-1);
    expect(accountIndex).toBeGreaterThan(connectionIndex);
    expect(header).toContain('aria-label="Open account"');
    expect(header).not.toContain(">Menu<");
  });

  it("announces connection changes and wires the track medic dialog trigger", () => {
    expect(bettingTemplate).toMatch(
      /id="connection-text"[\s\S]*?role="status"[\s\S]*?aria-live="polite"/,
    );
    expect(bettingTemplate).toMatch(
      /id="track-medic-open"[\s\S]*?aria-controls="track-medic-panel"[\s\S]*?aria-expanded="false"[\s\S]*?aria-haspopup="dialog"/,
    );
  });

  it("uses a four-column desktop header grid with the account button last", () => {
    const css = readFileSync(resolve(process.cwd(), "static/css/betting.css"), "utf8");
    expect(css).toMatch(/\.betting-header\s*\{[\s\S]*?grid-template-columns:\s*auto minmax\(0,\s*1fr\) auto auto;/);
  });

  it("shows the six requested icon sheets in order", () => {
    const tablistMatch = bettingTemplate.match(
      /<nav class="bet-sheet-tabs"[\s\S]*?<\/nav>/,
    );
    expect(tablistMatch).not.toBeNull();
    const tablist = tablistMatch?.[0] ?? "";
    const sheets = Array.from(tablist.matchAll(/data-bet-sheet="([^"]+)"/g), (match) => match[1]);
    expect(sheets).toEqual(["chat", "bet", "tune-in", "inventory", "shop", "boards"]);
    expect(tablist.match(/<svg /g)).toHaveLength(6);
    expect(tablist).toContain('id="inventory-tab-count"');
  });

  it("embeds the shared display broadcast in the Tune In sheet", () => {
    expect(bettingTemplate).toContain('id="bet-sheet-tab-tune-in"');
    expect(bettingTemplate).toContain('id="bet-sheet-tune-in"');
    expect(bettingTemplate).toContain('id="tune-in-broadcast"');
    expect(bettingTemplate).toContain("Live To The Races broadcast");
    expect(bettingTemplate).toContain('<details class="tune-in-inventory">');
    expect(bettingTemplate).toContain('aria-label="Open or close your item bag"');
    expect(bettingTemplate).not.toContain('id="tune-in-target-step"');
    expect(bettingTemplate).not.toContain('id="tune-in-inventory-title"');
  });

  it("keeps replay and highlight playback out of the Bet sheet", () => {
    expect(bettingTemplate).not.toContain('id="replay-prompt"');
    expect(bettingTemplate).not.toContain('id="replay-stage"');
    expect(bettingTemplate).not.toContain('name="replay-preference"');
  });

  it("does not cover the lineup with a closed-betting overlay", () => {
    const css = readFileSync(resolve(process.cwd(), "static/css/betting.css"), "utf8");
    expect(bettingTemplate).not.toContain('id="lineup-overlay"');
    expect(bettingTemplate).not.toContain("lineup-lock-title");
    expect(css).not.toContain(".lineup-overlay");
    expect(css).not.toContain(".race-sheet.is-locked");
  });
});
