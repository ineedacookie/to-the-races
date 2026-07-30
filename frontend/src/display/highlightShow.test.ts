import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type { RacerEntry } from "../shared/types";
import {
  fireworkCount,
  goldCelebrationForSprite,
  potionAlertActive,
  speakerVisibility,
  wreckedFinishers,
} from "./highlightShow";

const template = readFileSync(
  resolve(process.cwd(), "templates/display/index.html"),
  "utf8",
);
const styles = readFileSync(
  resolve(process.cwd(), "static/css/display.css"),
  "utf8",
);

function racer(
  racerId: number,
  name: string,
  spriteKey: string,
  place: number | null,
  dnfReason = "",
): RacerEntry {
  return {
    id: racerId,
    racer_id: racerId,
    name,
    slug: name.toLowerCase().replaceAll(" ", "-"),
    sprite_key: spriteKey,
    color: "#ffffff",
    lane: racerId,
    odds: "4.00",
    tagline: "Fast enough for television.",
    backstory: "A racer with something to prove.",
    total_staked_cents: 0,
    finish_place: place,
    dnf_reason: dnfReason,
    record: {
      starts: 1,
      wins: place === 1 ? 1 : 0,
      losses: place === 1 ? 0 : 1,
      dnfs: place === null ? 1 : 0,
      win_rate: place === 1 ? 1 : 0,
    },
  };
}

describe("display podium", () => {
  it("scales the podium and racers with the display container", () => {
    expect(styles).toContain("width: 78cqw");
    expect(styles).toContain(
      "height: clamp(76px, 16cqh, 160px)",
    );
    expect(styles).toContain(
      "min-height: clamp(150px, 28cqh, 280px)",
    );
    expect(styles).not.toContain("width: min(67%, 840px)");
  });

  it("puts only the last official finisher and every DNF in wreckage", () => {
    const entries = [
      racer(1, "First", "skeleton", 1),
      racer(2, "Second", "mushroom", 2),
      racer(3, "Third", "goblin", 3),
      racer(4, "Fourth", "flying-eye", 4),
      racer(5, "Last", "rat", 5),
      racer(6, "Wreck", "slime", null, "destroyed"),
    ];

    expect(
      wreckedFinishers(entries).map((entry) => entry.name),
    ).toEqual(["Last", "Wreck"]);
  });

  it("maps every known sprite to its own gold celebration", () => {
    expect(
      [
        "skeleton",
        "mushroom",
        "goblin",
        "flying-eye",
        "mimic",
        "rat",
        "slime",
        "bat",
      ].map(goldCelebrationForSprite),
    ).toEqual([
      "rattle-hop",
      "spore-bounce",
      "victory-stomp",
      "orbit-blink",
      "royal-chomp",
      "cheese-scurrying",
      "gloop-ripple",
      "wing-flap",
    ]);
    expect(goldCelebrationForSprite("future-racer")).toBe(
      "champion-hop",
    );
  });
});

describe("server-authored highlight markup", () => {
  it("shows only the active desk portrait outside interviews", () => {
    expect(
      speakerVisibility({
        kind: "host",
        name: "Chip McChatter",
        racer_id: null,
        sprite_key: null,
      }),
    ).toEqual({ host: true, racer: false });
    expect(
      speakerVisibility({
        kind: "racer",
        name: "Bonejamin",
        racer_id: 1,
        sprite_key: "skeleton",
      }),
    ).toEqual({ host: false, racer: true });
  });

  it("contains conditional finance, record, podium, interview, and feature stages", () => {
    expect(template).not.toContain('id="display-results"');
    expect(template).toContain('id="display-highlight-show"');
    expect(template).toContain('id="highlight-replay-canvas"');
    expect(template).toContain('id="highlight-finance"');
    expect(template).toContain('id="highlight-record"');
    expect(template).toContain('id="highlight-fireworks"');
    expect(template).toContain('id="highlight-podium-slots"');
    expect(template).toContain('id="highlight-interview"');
    expect(template).toContain('id="highlight-feature"');
  });

  it("keeps Chip in a reactive live booth and exposes no sound control", () => {
    expect(template).toContain('id="live-tech-booth"');
    expect(template).toContain('id="live-tech-booth-sprite"');
    expect(template).not.toContain('id="mute-button"');
    expect(styles).toContain(".live-tech-booth__sprite.is-reacting");
    expect(styles).toContain(".live-tech-booth__sprite.is-alarmed");
    expect(styles).toContain(".live-tech-booth__sprite.is-celebrating");
  });

  it("hides the stable live caption and removes redundant desk detail", () => {
    expect(template).toContain(
      'id="highlight-caption" aria-hidden="true"',
    );
    expect(template).toContain('id="highlight-caption-live"');
    expect(template).toContain('aria-atomic="true"');
    expect(template).not.toContain('id="highlight-detail"');
    expect(styles).toContain(
      ".display-highlight-show .visually-hidden",
    );
  });

  it("wraps captions into a bottom-pinned two-line viewport", () => {
    expect(styles).toContain(".highlight-interview__bubble > span");
    expect(styles).toContain("max-height: 2.24em");
    expect(styles).toContain("max-height: 2.16em");
    expect(styles).toContain("white-space: normal");
    expect(styles).not.toContain("text-wrap: nowrap");
  });

  it("gives the host and winner a full-screen animated interview set", () => {
    expect(template).toContain('id="highlight-interview-host"');
    expect(template).toContain('id="highlight-interview-racer"');
    expect(template).toContain(
      'id="highlight-interview-host-bubble"',
    );
    expect(template).toContain(
      'id="highlight-interview-racer-bubble"',
    );
    expect(styles).toContain("@keyframes interview-host-talk");
    expect(styles).toContain("@keyframes interview-racer-talk");
  });

  it("keeps the racer, microphone, and host on one interview row in that order", () => {
    const racerIndex = template.indexOf('id="highlight-interview-racer"');
    const microphoneIndex = template.indexOf("highlight-interview__microphone");
    const hostIndex = template.indexOf('id="highlight-interview-host"');

    expect(racerIndex).toBeGreaterThan(-1);
    expect(racerIndex).toBeLessThan(microphoneIndex);
    expect(microphoneIndex).toBeLessThan(hostIndex);
    expect(styles).toContain(".highlight-interview__racer");
    expect(styles).toContain("grid-row: 1");
    expect(styles).toContain("height: calc(var(--interview-host-width) * 1.468)");
  });

  it("scopes fireworks and reduced-motion tableau styles to record stages", () => {
    expect(fireworkCount(false)).toBe(22);
    expect(fireworkCount(true)).toBe(8);
    expect(styles).toContain(
      'url("/static/assets/effects/fireworks-source.png")',
    );
    expect(styles).toContain("@keyframes firework-sheet");
    expect(styles).toContain(".highlight-firework");
    expect(styles).toContain(
      "@media (prefers-reduced-motion: reduce)",
    );
    expect(styles).toContain("host-record-jump");
  });

  it("briefly flashes police lights only for the confirmed potion callout", () => {
    expect(potionAlertActive("potion_callout")).toBe(true);
    expect(potionAlertActive("potion_response")).toBe(false);
    expect(potionAlertActive("interview_question")).toBe(false);
    expect(styles).toContain(
      ".display-highlight-show.is-potion-alert::before",
    );
    expect(styles).toContain("potion-alert-red 2.4s ease-out 1");
    expect(styles).toContain("potion-alert-blue 2.4s ease-out 1");
  });
});
