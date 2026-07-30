import { racerPortraitPath } from "../shared/assets";
import { presentationRound } from "../shared/liveUi";
import {
  replayShowElapsed,
  resolveReplayStage,
  revealedCaption,
  serverClockOffset,
} from "../shared/replayTimeline";
import type {
  BettingSpotlightPerson,
  LiveState,
  RacerEntry,
  ReplayMontage,
  ReplayShowSpeaker,
  ReplayShowStage,
  ReplayShowStageKind,
} from "../shared/types";
import { assertNever } from "../shared/types";
import { createReplayCanvasRenderer } from "../betting/replayCanvas";

const ROOT_TRANSITION_MS = 650;

type HighlightPanel =
  | "intro"
  | "reel"
  | "finance"
  | "record"
  | "podium"
  | "interview"
  | "feature";

interface DisplayHighlightElements {
  root: HTMLElement;
  intro: HTMLElement;
  introKicker: HTMLElement;
  introTitle: HTMLElement;
  reel: HTMLElement;
  canvas: HTMLCanvasElement;
  clipLabel: HTMLElement;
  clipProgress: HTMLElement;
  finance: HTMLElement;
  financeCards: HTMLElement;
  record: HTMLElement;
  recordTitle: HTMLElement;
  recordHolder: HTMLElement;
  fireworks: HTMLElement;
  podium: HTMLElement;
  podiumTitle: HTMLElement;
  podiumSlots: HTMLElement;
  wreckage: HTMLElement;
  interview: HTMLElement;
  interviewHost: HTMLElement;
  interviewRacer: HTMLElement;
  interviewHostBubble: HTMLElement;
  interviewHostText: HTMLElement;
  interviewRacerBubble: HTMLElement;
  interviewRacerText: HTMLElement;
  interviewRacerPortrait: HTMLImageElement;
  interviewRacerName: HTMLElement;
  feature: HTMLElement;
  featureKicker: HTMLElement;
  featureTitle: HTMLElement;
  featureArt: HTMLElement;
  hostDesk: HTMLElement;
  hostSprite: HTMLElement;
  hostBadge: HTMLElement;
  speaker: HTMLElement;
  caption: HTMLElement;
  captionLive: HTMLElement;
  guest: HTMLElement;
  guestPortrait: HTMLImageElement;
  guestName: HTMLElement;
}

export interface DisplayHighlightController {
  sync: (state: LiveState) => void;
  abort: () => void;
  dispose: () => void;
}

export function potionAlertActive(
  kind: ReplayShowStageKind,
): boolean {
  return kind === "potion_callout";
}

function validMontage(
  value: ReplayMontage | undefined,
): value is ReplayMontage {
  return (
    value !== undefined &&
    typeof value.playback_key === "string" &&
    value.playback_key.length > 0 &&
    Array.isArray(value.clips) &&
    value.clips.length > 0 &&
    Array.isArray(value.stages) &&
    value.stages.length > 0 &&
    typeof value.show_started_at === "string"
  );
}

function orderedResults(entries: readonly RacerEntry[]): RacerEntry[] {
  return [...entries].sort((left, right) => {
    if (left.finish_place === null && right.finish_place === null) {
      return left.lane - right.lane;
    }
    if (left.finish_place === null) {
      return 1;
    }
    if (right.finish_place === null) {
      return -1;
    }
    return left.finish_place - right.finish_place;
  });
}

export function wreckedFinishers(
  entries: readonly RacerEntry[],
): RacerEntry[] {
  const officialFinishers = entries.filter(
    (entry): entry is RacerEntry & { finish_place: number } =>
      entry.finish_place !== null,
  );
  const lastPlace = officialFinishers.reduce(
    (place, entry) => Math.max(place, entry.finish_place),
    0,
  );
  return orderedResults(entries).filter(
    (entry) =>
      entry.finish_place === null ||
      (lastPlace > 3 && entry.finish_place === lastPlace),
  );
}

export type GoldCelebration =
  | "rattle-hop"
  | "spore-bounce"
  | "victory-stomp"
  | "orbit-blink"
  | "royal-chomp"
  | "cheese-scurrying"
  | "gloop-ripple"
  | "wing-flap"
  | "champion-hop";

export function goldCelebrationForSprite(
  spriteKey: string,
): GoldCelebration {
  switch (spriteKey) {
    case "skeleton":
      return "rattle-hop";
    case "mushroom":
      return "spore-bounce";
    case "goblin":
      return "victory-stomp";
    case "flying-eye":
      return "orbit-blink";
    case "mimic":
      return "royal-chomp";
    case "rat":
      return "cheese-scurrying";
    case "slime":
      return "gloop-ripple";
    case "bat":
      return "wing-flap";
    default:
      return "champion-hop";
  }
}

export function speakerVisibility(
  speaker: ReplayShowSpeaker,
): { host: boolean; racer: boolean } {
  switch (speaker.kind) {
    case "host":
      return { host: true, racer: false };
    case "racer":
      return { host: false, racer: true };
    default:
      return assertNever(speaker.kind);
  }
}

function dnfLabel(reason: string): string {
  return reason.length > 0
    ? reason.replaceAll("_", " ")
    : "did not finish";
}

function racerPortrait(
  entry: RacerEntry,
  className: string,
): HTMLImageElement {
  const portrait = document.createElement("img");
  portrait.className = className;
  portrait.src = racerPortraitPath(entry.sprite_key);
  portrait.alt = "";
  portrait.addEventListener(
    "error",
    () => {
      portrait.hidden = true;
    },
    { once: true },
  );
  return portrait;
}

function podiumPlace(
  place: 1 | 2 | 3,
  entry: RacerEntry | undefined,
): HTMLElement {
  const placeElement = document.createElement("article");
  placeElement.className = "highlight-podium__place";
  placeElement.dataset.place = String(place);
  placeElement.classList.toggle(
    "highlight-podium__place--empty",
    entry === undefined,
  );
  const figure = document.createElement("div");
  figure.className = "highlight-podium__figure";
  if (entry !== undefined) {
    const portrait = racerPortrait(
      entry,
      "highlight-podium__racer",
    );
    if (place === 1) {
      const celebration = goldCelebrationForSprite(entry.sprite_key);
      figure.dataset.celebration = celebration;
      portrait.classList.add(
        "highlight-podium__racer--gold",
        `celebration--${celebration}`,
      );
    }
    figure.append(portrait);
    const name = document.createElement("strong");
    name.textContent = entry.name;
    figure.append(name);
  } else {
    figure.classList.add("highlight-podium__figure--empty");
  }
  const block = document.createElement("div");
  block.className = "highlight-podium__block";
  const rank = document.createElement("strong");
  rank.textContent = entry === undefined ? "—" : String(place);
  const medal = document.createElement("span");
  medal.textContent =
    entry === undefined
      ? "VACANT"
      : place === 1
        ? "GOLD"
        : place === 2
          ? "SILVER"
          : "BRONZE";
  block.append(rank, medal);
  placeElement.append(figure, block);
  return placeElement;
}

function renderPodium(
  elements: DisplayHighlightElements,
  entries: readonly RacerEntry[],
): void {
  const top = new Map(
    entries
      .filter(
        (entry): entry is RacerEntry & { finish_place: number } =>
          entry.finish_place !== null && entry.finish_place <= 3,
      )
      .map((entry) => [entry.finish_place, entry]),
  );
  const winner = top.get(1);
  elements.podiumTitle.textContent =
    winner === undefined
      ? "The house takes the trophy!"
      : `${winner.name} takes the gold!`;
  elements.podiumSlots.replaceChildren(
    podiumPlace(2, top.get(2)),
    podiumPlace(1, winner),
    podiumPlace(3, top.get(3)),
  );
  elements.wreckage.replaceChildren();
  for (const entry of wreckedFinishers(entries)) {
    const wreck = document.createElement("article");
    wreck.className = "highlight-wreck";
    const crash = document.createElement("span");
    crash.className = "highlight-wreck__crash";
    crash.textContent = "×";
    const portrait = racerPortrait(
      entry,
      "highlight-wreck__racer",
    );
    const copy = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = entry.name;
    const reason = document.createElement("small");
    reason.textContent =
      entry.finish_place === null
        ? `WRECKED · ${dnfLabel(entry.dnf_reason)}`
        : `LAST PLACE · #${entry.finish_place}`;
    copy.append(name, reason);
    wreck.append(crash, portrait, copy);
    elements.wreckage.append(wreck);
  }
  elements.wreckage.hidden =
    elements.wreckage.childElementCount === 0;
}

function renderClipProgress(
  container: HTMLElement,
  count: number,
  currentIndex: number,
): void {
  container.replaceChildren();
  for (let index = 0; index < count; index += 1) {
    const marker = document.createElement("span");
    marker.classList.toggle("is-current", index === currentIndex);
    marker.classList.toggle("is-complete", index < currentIndex);
    container.append(marker);
  }
}

function money(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Math.abs(cents) / 100);
}

function financeCard(
  person: BettingSpotlightPerson | null,
  kind: "gain" | "loss",
): HTMLElement {
  const card = document.createElement("article");
  card.className = "highlight-finance__card";
  card.dataset.kind = kind;
  const label = document.createElement("span");
  label.textContent =
    kind === "gain" ? "HIGHEST GAIN" : "HIGHEST LOSS";
  if (person === null) {
    const empty = document.createElement("strong");
    empty.textContent = "No contender";
    card.classList.add("is-vacant");
    card.append(label, empty);
    return card;
  }
  const avatar = document.createElement("img");
  avatar.src = person.avatar_url;
  avatar.alt = "";
  const name = document.createElement("strong");
  name.textContent = person.nickname;
  const value = document.createElement("b");
  value.textContent = `${kind === "gain" ? "+" : "−"}${money(person.net_cents)}`;
  const detail = document.createElement("small");
  detail.textContent = `${person.bet_count} settled bet${person.bet_count === 1 ? "" : "s"}`;
  card.append(label, avatar, name, value, detail);
  return card;
}

function renderFinance(
  elements: DisplayHighlightElements,
  stage: ReplayShowStage,
): void {
  const spotlight = stage.betting_spotlight;
  if (spotlight === undefined) {
    elements.financeCards.replaceChildren();
    return;
  }
  elements.financeCards.replaceChildren(
    financeCard(spotlight.highest_gain, "gain"),
    financeCard(spotlight.highest_loss, "loss"),
  );
}

function createFireworks(
  container: HTMLElement,
  reducedMotion: boolean,
): void {
  container.replaceChildren();
  const count = fireworkCount(reducedMotion);
  for (let index = 0; index < count; index += 1) {
    const burst = document.createElement("span");
    burst.className = "highlight-firework";
    burst.style.setProperty(
      "--firework-x",
      `${6 + ((index * 37) % 88)}%`,
    );
    burst.style.setProperty(
      "--firework-y",
      `${4 + ((index * 53) % 68)}%`,
    );
    burst.style.setProperty(
      "--firework-delay",
      `${(index % 9) * 0.24}s`,
    );
    burst.style.setProperty(
      "--firework-scale",
      String(0.55 + (index % 5) * 0.16),
    );
    container.append(burst);
  }
}

export function fireworkCount(reducedMotion: boolean): number {
  return reducedMotion ? 8 : 22;
}

function renderRecord(
  elements: DisplayHighlightElements,
  stage: ReplayShowStage,
  reducedMotion: boolean,
): void {
  elements.recordHolder.replaceChildren();
  createFireworks(elements.fireworks, reducedMotion);
  const record = stage.world_record;
  if (record === undefined) {
    elements.recordTitle.textContent =
      stage.record_beat === "finale"
        ? "Record-breaker grand finale!"
        : "World record alert!";
    const message = document.createElement("strong");
    message.textContent =
      stage.record_beat === "finale"
        ? "THE RECORD BOOK HAS BEEN REWRITTEN"
        : "HISTORY IS HAPPENING LIVE";
    elements.recordHolder.append(message);
    return;
  }
  elements.recordTitle.textContent = "A new name in history!";
  const portrait = document.createElement("img");
  portrait.src = racerPortraitPath(record.sprite_key);
  portrait.alt = "";
  const copy = document.createElement("div");
  const name = document.createElement("strong");
  name.textContent = record.racer_name;
  const label = document.createElement("span");
  label.textContent = record.label;
  const value = document.createElement("b");
  value.textContent = record.display_value;
  copy.append(name, label, value);
  elements.recordHolder.append(portrait, copy);
}

function stageBadge(kind: ReplayShowStageKind): string {
  switch (kind) {
    case "intro":
      return "LIVE · REPLAY BOOTH";
    case "clip":
      return "CHIP REACTS · LIVE";
    case "betting_spotlight":
      return "CHIP'S WALLET WATCH";
    case "world_record_celebration":
      return "WORLD RECORD ALERT";
    case "podium":
      return "OFFICIAL PODIUM";
    case "interview_question":
    case "interview_answer":
      return "WINNER INTERVIEW";
    case "potion_callout":
    case "potion_response":
      return "POTION INVESTIGATION";
    case "outro":
      return "CHIP'S FINAL WORD";
    default:
      return assertNever(kind);
  }
}

function featureLabel(kind: ReplayShowStageKind): string {
  switch (kind) {
    case "interview_question":
    case "interview_answer":
      return "TRACKSIDE · EXCLUSIVE";
    case "potion_callout":
    case "potion_response":
      return "THE BOTTLE DOES NOT LIE";
    case "outro":
      return "THAT'S THE SHOW";
    case "intro":
    case "clip":
    case "betting_spotlight":
    case "world_record_celebration":
    case "podium":
      return "";
    default:
      return assertNever(kind);
  }
}

export function createDisplayHighlightController(
  elements: DisplayHighlightElements,
): DisplayHighlightController {
  const renderer = createReplayCanvasRenderer(elements.canvas);
  let generation = 0;
  let currentKey: string | null = null;
  let currentMontage: ReplayMontage | null = null;
  let currentEntries: RacerEntry[] = [];
  let serverOffsetMs = 0;
  let frameRequest: number | null = null;
  let renderedStageId: string | null = null;
  let assetsReadyKey: string | null = null;
  let hideTimer: number | null = null;

  function serverNow(): number {
    return Date.now() + serverOffsetMs;
  }

  function reducedMotion(): boolean {
    return window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
  }

  function setPanel(panel: HighlightPanel): void {
    elements.root.dataset.phase = panel;
    elements.intro.hidden = panel !== "intro";
    elements.reel.hidden = panel !== "reel";
    elements.finance.hidden = panel !== "finance";
    elements.record.hidden = panel !== "record";
    elements.podium.hidden = panel !== "podium";
    elements.interview.hidden = panel !== "interview";
    elements.feature.hidden = panel !== "feature";
  }

  function setSpeaker(stage: ReplayShowStage): void {
    const visibility = speakerVisibility(stage.speaker);
    const hostSpeaking = visibility.host;
    elements.speaker.textContent = stage.speaker.name;
    elements.hostSprite.hidden = !visibility.host;
    elements.guest.hidden = !visibility.racer;
    elements.hostDesk.classList.toggle(
      "speaker-is-racer",
      !hostSpeaking,
    );
    elements.hostDesk.classList.toggle(
      "speaker-is-host",
      hostSpeaking,
    );
    elements.hostSprite.classList.toggle(
      "is-speaking",
      hostSpeaking && !reducedMotion(),
    );
    elements.guest.classList.toggle(
      "is-speaking",
      !hostSpeaking && !reducedMotion(),
    );
    if (hostSpeaking) {
      elements.guestPortrait.removeAttribute("src");
      elements.guestName.textContent = "";
    } else {
      const spriteKey = stage.speaker.sprite_key;
      if (spriteKey !== null) {
        elements.guestPortrait.src = racerPortraitPath(spriteKey);
      }
      elements.guestName.textContent = stage.speaker.name;
    }
  }

  function showRoot(): void {
    if (hideTimer !== null) {
      window.clearTimeout(hideTimer);
      hideTimer = null;
    }
    elements.root.hidden = false;
    elements.hostDesk.hidden = false;
    elements.root.classList.remove("is-leaving");
    elements.root.classList.add("is-entering");
    requestAnimationFrame(() => {
      elements.root.classList.remove("is-entering");
    });
  }

  function finishHide(): void {
    elements.root.hidden = true;
    elements.root.classList.remove(
      "is-leaving",
      "is-potion-alert",
    );
    elements.hostSprite.classList.remove(
      "is-speaking",
      "is-record-celebrating",
    );
    elements.guest.classList.remove("is-speaking");
    elements.interviewHost.classList.remove("is-speaking");
    elements.interviewRacer.classList.remove("is-speaking");
    elements.interviewHostBubble.hidden = true;
    elements.interviewRacerBubble.hidden = true;
    elements.fireworks.replaceChildren();
  }

  function hideRoot(smooth: boolean): void {
    renderer.stop();
    if (elements.root.hidden || !smooth) {
      finishHide();
      return;
    }
    elements.root.classList.add("is-leaving");
    const duration = reducedMotion()
      ? Math.min(ROOT_TRANSITION_MS, 250)
      : ROOT_TRANSITION_MS;
    hideTimer = window.setTimeout(() => {
      hideTimer = null;
      finishHide();
    }, duration);
  }

  function stopTimeline(): void {
    if (frameRequest !== null) {
      cancelAnimationFrame(frameRequest);
      frameRequest = null;
    }
    renderedStageId = null;
    renderer.stop();
  }

  function isInterviewStage(stage: ReplayShowStage): boolean {
    return (
      stage.kind === "interview_question" ||
      stage.kind === "interview_answer" ||
      stage.kind === "potion_callout" ||
      stage.kind === "potion_response"
    );
  }

  function renderInterview(stage: ReplayShowStage): void {
    const hostSpeaking = stage.speaker.kind === "host";
    const winner = stage.winner;
    elements.interview.dataset.speaker = hostSpeaking
      ? "host"
      : "racer";
    elements.interview.dataset.variant =
      stage.kind === "potion_callout" ||
      stage.kind === "potion_response"
        ? "potion"
        : "winner";
    elements.interviewHost.classList.toggle(
      "is-speaking",
      hostSpeaking && !reducedMotion(),
    );
    elements.interviewRacer.classList.toggle(
      "is-speaking",
      !hostSpeaking && !reducedMotion(),
    );
    elements.interviewHostBubble.hidden = !hostSpeaking;
    elements.interviewRacerBubble.hidden = hostSpeaking;
    elements.interviewHostText.textContent = "";
    elements.interviewRacerText.textContent = "";
    if (winner === undefined || winner === null) {
      elements.interviewRacerPortrait.removeAttribute("src");
      elements.interviewRacerPortrait.hidden = true;
      elements.interviewRacerName.textContent = "Tonight's winner";
      return;
    }
    elements.interviewRacerPortrait.hidden = false;
    elements.interviewRacerPortrait.src = racerPortraitPath(
      winner.sprite_key,
    );
    elements.interviewRacerPortrait.onerror = () => {
      elements.interviewRacerPortrait.hidden = true;
    };
    elements.interviewRacerName.textContent = winner.name;
  }

  function renderInterviewCaption(
    stage: ReplayShowStage,
    caption: string,
  ): void {
    if (!isInterviewStage(stage)) {
      return;
    }
    if (stage.speaker.kind === "host") {
      elements.interviewHostText.textContent = caption;
      elements.interviewRacerText.textContent = "";
      elements.interviewHostText.scrollTop =
        elements.interviewHostText.scrollHeight;
    } else {
      elements.interviewHostText.textContent = "";
      elements.interviewRacerText.textContent = caption;
      elements.interviewRacerText.scrollTop =
        elements.interviewRacerText.scrollHeight;
    }
  }

  function renderFeature(stage: ReplayShowStage): void {
    elements.featureKicker.textContent = featureLabel(stage.kind);
    elements.featureTitle.textContent = stage.detail;
    elements.featureArt.replaceChildren();
    if (
      (stage.kind === "potion_callout" ||
        stage.kind === "potion_response") &&
      stage.potion !== undefined
    ) {
      const icon = document.createElement("b");
      icon.textContent = stage.potion.item_icon;
      const copy = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = stage.potion.item_name;
      const buyer = document.createElement("small");
      buyer.textContent = `Supplied by ${stage.potion.buyer}`;
      copy.append(name, buyer);
      elements.featureArt.append(icon, copy);
    } else {
      elements.featureArt.textContent =
        stage.kind === "outro" ? "★" : "";
    }
  }

  function renderStage(
    montage: ReplayMontage,
    stage: ReplayShowStage,
    stageElapsedMs: number,
  ): void {
    renderer.stop();
    elements.root.dataset.stageKind = stage.kind;
    elements.root.dataset.stageId = stage.id;
    elements.hostBadge.textContent = stageBadge(stage.kind);
    elements.captionLive.textContent = stage.caption;
    const interviewStage = isInterviewStage(stage);
    elements.hostDesk.hidden = interviewStage;
    setSpeaker(stage);
    const isRecord = stage.kind === "world_record_celebration";
    if (!isRecord) {
      elements.fireworks.replaceChildren();
    }
    elements.hostSprite.classList.toggle(
      "is-record-celebrating",
      isRecord && !reducedMotion(),
    );
    elements.root.classList.toggle(
      "is-record-stage",
      isRecord,
    );
    elements.root.classList.toggle(
      "is-potion-alert",
      potionAlertActive(stage.kind),
    );
    elements.root.classList.toggle(
      "is-reduced-motion",
      reducedMotion(),
    );
    switch (stage.kind) {
      case "intro":
        setPanel("intro");
        elements.introKicker.textContent = `${stage.speaker.name} presents`;
        elements.introTitle.textContent =
          "Tonight's Trackside Turmoil";
        break;
      case "clip": {
        setPanel("reel");
        const clip = montage.clips.find(
          (candidate) => candidate.id === stage.clip_id,
        );
        const clipIndex = stage.clip_index ?? 0;
        elements.clipLabel.textContent = `REEL ${clipIndex + 1} / ${montage.clips.length}`;
        renderClipProgress(
          elements.clipProgress,
          montage.clips.length,
          clipIndex,
        );
        if (clip !== undefined) {
          elements.canvas.setAttribute(
            "aria-label",
            stage.caption,
          );
          void renderer.play(
            clip,
            montage,
            currentEntries,
            reducedMotion(),
            {
              offsetMs: stageElapsedMs,
              durationMs: stage.duration_ms,
            },
          );
        }
        break;
      }
      case "betting_spotlight":
        setPanel("finance");
        renderFinance(elements, stage);
        break;
      case "world_record_celebration":
        setPanel("record");
        renderRecord(elements, stage, reducedMotion());
        break;
      case "podium":
        setPanel("podium");
        renderPodium(elements, currentEntries);
        break;
      case "interview_question":
      case "interview_answer":
      case "potion_callout":
      case "potion_response":
        setPanel("interview");
        renderInterview(stage);
        break;
      case "outro":
        setPanel("feature");
        renderFeature(stage);
        break;
      default:
        assertNever(stage.kind);
    }
  }

  function updateTimelineFrame(montage: ReplayMontage): void {
    const elapsed = replayShowElapsed(
      montage.show_started_at,
      serverNow(),
    );
    const position = resolveReplayStage(montage.stages, elapsed);
    if (position === null) {
      return;
    }
    if (position.stage.id !== renderedStageId) {
      renderedStageId = position.stage.id;
      renderStage(
        montage,
        position.stage,
        position.stageElapsedMs,
      );
    }
    const caption = revealedCaption(
      position.stage.caption,
      position.stageElapsedMs,
      position.stage.duration_ms,
      reducedMotion(),
    );
    elements.caption.textContent = caption;
    elements.caption.scrollTop = elements.caption.scrollHeight;
    renderInterviewCaption(position.stage, caption);
    elements.root.style.setProperty(
      "--stage-progress",
      String(position.progress),
    );
  }

  function startTimeline(montage: ReplayMontage, token: number): void {
    stopTimeline();
    const tick = (): void => {
      if (
        token !== generation ||
        currentMontage !== montage ||
        currentKey !== montage.playback_key
      ) {
        return;
      }
      updateTimelineFrame(montage);
      frameRequest = requestAnimationFrame(tick);
    };
    tick();
  }

  function runMontage(
    token: number,
    montage: ReplayMontage,
    entries: readonly RacerEntry[],
  ): void {
    showRoot();
    currentEntries = [...entries];
    currentMontage = montage;
    assetsReadyKey = null;
    setPanel("intro");
    elements.root.dataset.stageKind = "intro";
    elements.root.dataset.stageId = "loading";
    elements.root.classList.remove("is-potion-alert");
    elements.introKicker.textContent = "Chip McChatter presents";
    elements.introTitle.textContent = "Tonight's Trackside Turmoil";
    elements.hostBadge.textContent = "LIVE · REPLAY BOOTH";
    elements.speaker.textContent = "Chip McChatter";
    elements.caption.textContent = "";
    elements.captionLive.textContent = "";
    elements.hostDesk.hidden = false;
    elements.hostSprite.hidden = false;
    elements.guest.hidden = true;
    elements.root.classList.remove("is-potion-alert");
    void renderer.load(montage, entries).then(() => {
      if (
        token !== generation ||
        currentMontage !== montage ||
        currentKey !== montage.playback_key
      ) {
        return;
      }
      assetsReadyKey = montage.playback_key;
      startTimeline(montage, token);
    });
  }

  function showFallback(
    entries: readonly RacerEntry[],
  ): void {
    showRoot();
    currentEntries = [...entries];
    setPanel("podium");
    renderPodium(elements, entries);
    elements.hostBadge.textContent = "OFFICIAL PODIUM";
    elements.speaker.textContent = "Chip McChatter";
    elements.caption.textContent =
      "The replay booth is dark, but the podium still shines!";
    elements.captionLive.textContent = elements.caption.textContent;
    elements.hostSprite.hidden = false;
    elements.guest.hidden = true;
  }

  function abort(): void {
    generation += 1;
    currentKey = null;
    currentMontage = null;
    assetsReadyKey = null;
    stopTimeline();
    hideRoot(true);
  }

  function sync(state: LiveState): void {
    serverOffsetMs = serverClockOffset(state.server_time);
    const round = presentationRound(state);
    if (round === null || round.state !== "results") {
      if (currentKey !== null) {
        abort();
      }
      return;
    }
    const montage = round.display_replay;
    const key = validMontage(montage)
      ? montage.playback_key
      : `round-${round.id}-fallback`;
    currentEntries = round.entries;
    if (key === currentKey) {
      if (
        currentMontage !== null &&
        assetsReadyKey === currentKey
      ) {
        updateTimelineFrame(currentMontage);
      }
      return;
    }
    generation += 1;
    stopTimeline();
    currentKey = key;
    const token = generation;
    if (validMontage(montage)) {
      runMontage(token, montage, round.entries);
    } else {
      currentMontage = null;
      showFallback(round.entries);
    }
  }

  function dispose(): void {
    generation += 1;
    currentKey = null;
    currentMontage = null;
    assetsReadyKey = null;
    stopTimeline();
    renderer.dispose();
    if (hideTimer !== null) {
      window.clearTimeout(hideTimer);
      hideTimer = null;
    }
    hideRoot(false);
  }

  return { sync, abort, dispose };
}
