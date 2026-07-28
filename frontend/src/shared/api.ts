import type { AvatarRecipe, LiveState } from "./types";
import { createClientRequestId } from "./requestId";

interface ApiErrorPayload {
  error?: {
    code?: string;
    message?: string;
  };
}

export class ApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

function csrfToken(): string {
  const token = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("csrftoken="))
    ?.split("=")
    .slice(1)
    .join("=");
  return decodeURIComponent(token ?? "");
}

async function requestJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken(),
      ...init.headers,
    },
    credentials: "same-origin",
  });
  const payload = (await response.json()) as T & ApiErrorPayload;
  if (!response.ok) {
    throw new ApiError(
      payload.error?.code ?? "request_failed",
      payload.error?.message ?? `Request failed (${response.status}).`,
    );
  }
  return payload;
}

export function fetchState(): Promise<LiveState> {
  return requestJson<LiveState>("/api/state/");
}

interface IdentityResponse {
  player: {
    id: number;
    nickname: string;
    balance_cents: number;
    avatar_version: string;
    avatar_url: string;
  };
}

export function identifyPlayer(
  nickname?: string,
  avatar?: AvatarRecipe,
): Promise<IdentityResponse> {
  return requestJson("/api/player/", {
    method: "POST",
    body: JSON.stringify({ nickname, avatar }),
  });
}

export function loginPlayer(nickname: string): Promise<IdentityResponse> {
  return requestJson("/api/player/login/", {
    method: "POST",
    body: JSON.stringify({ nickname }),
  });
}

export function suggestNickname(): Promise<{ nickname: string }> {
  return requestJson("/api/nickname-suggestion/");
}

export function submitBet(
  raceEntryId: number,
  amountCents: number,
): Promise<{
  bet: {
    id: number;
    amount_cents: number;
    racer_name: string;
    odds: string;
    duplicate: boolean;
  };
  balance_cents: number;
}> {
  return requestJson("/api/bets/", {
    method: "POST",
    body: JSON.stringify({
      race_entry_id: raceEntryId,
      amount_cents: amountCents,
      client_request_id: createClientRequestId(),
    }),
  });
}

export function purchaseItem(
  itemSlug: string,
): Promise<{
  balance_cents: number;
  inventory_item: {
    id: number;
    item_name: string;
    price_paid_cents: number;
    duplicate: boolean;
  };
}> {
  return requestJson("/api/items/purchase/", {
    method: "POST",
    body: JSON.stringify({
      item_slug: itemSlug,
      client_request_id: createClientRequestId(),
    }),
  });
}

export function discardItem(inventoryItemId: number): Promise<{
  discarded_item: {
    id: number;
    item_name: string;
    duplicate: boolean;
  };
}> {
  return requestJson("/api/items/discard/", {
    method: "POST",
    body: JSON.stringify({
      inventory_item_id: inventoryItemId,
    }),
  });
}

export function useItem(
  roundId: number,
  inventoryItemId: number,
  targetEntryId: number,
): Promise<{
  balance_cents: number;
  item_use: {
    id: number;
    inventory_item_id: number;
    item_name: string;
    price_paid_cents: number;
    duplicate: boolean;
  };
}> {
  return requestJson("/api/items/use/", {
    method: "POST",
    body: JSON.stringify({
      round_id: roundId,
      inventory_item_id: inventoryItemId,
      target_entry_id: targetEntryId,
      client_request_id: createClientRequestId(),
    }),
  });
}

export function purchaseUpgrade(
  upgradeSlug: string,
): Promise<{
  balance_cents: number;
  player_upgrade: {
    id: number;
    upgrade_name: string;
    inventory_capacity: number | null;
    price_paid_cents: number;
    duplicate: boolean;
  };
}> {
  return requestJson("/api/upgrades/purchase/", {
    method: "POST",
    body: JSON.stringify({
      upgrade_slug: upgradeSlug,
      client_request_id: createClientRequestId(),
    }),
  });
}

export function claimSeat(
  roundId: number,
  seatSlug: string,
  expectedPriceCents: number,
): Promise<{
  balance_cents: number;
  seat_claim: {
    id: number;
    seat_name: string;
    seat_color: string;
    price_paid_cents: number;
    next_price_cents: number;
    duplicate: boolean;
  };
}> {
  return requestJson("/api/seats/claim/", {
    method: "POST",
    body: JSON.stringify({
      round_id: roundId,
      seat_slug: seatSlug,
      expected_price_cents: expectedPriceCents,
      client_request_id: createClientRequestId(),
    }),
  });
}

export function startBailout(roundId: number): Promise<{
  balance_cents: number;
  bailout: {
    session_id: number;
    round_id: number;
    race_entry_id: number;
    racer_name: string;
    sprite_key: string;
    wound_count: number;
    wounds: Array<{ x: number; y: number }>;
    patched_indices: number[];
    completed: boolean;
    reward_cents: number;
    duplicate: boolean;
  };
}> {
  return requestJson("/api/bailout/start/", {
    method: "POST",
    body: JSON.stringify({
      round_id: roundId,
      client_request_id: createClientRequestId(),
    }),
  });
}

export function patchBailoutWound(
  sessionId: number,
  woundIndex: number,
): Promise<{
  balance_cents: number;
  bailout_patch: {
    session_id: number;
    wound_index: number;
    patched_indices: number[];
    completed: boolean;
    reward_cents: number;
    duplicate: boolean;
  };
}> {
  return requestJson("/api/bailout/patch/", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      wound_index: woundIndex,
      client_request_id: createClientRequestId(),
    }),
  });
}
