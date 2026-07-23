import type { LiveState } from "./types";

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

export function identifyPlayer(
  nickname?: string,
): Promise<{ player: { id: number; nickname: string; balance_cents: number } }> {
  return requestJson("/api/player/", {
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
      client_request_id: crypto.randomUUID(),
    }),
  });
}

export interface DeployItemRequest {
  round_id: number;
  item_slug: string;
  client_request_id: string;
  target_entry_id?: number;
  track_lane?: number;
  track_position?: number;
}

export function deployItem(
  request: DeployItemRequest,
): Promise<{
  balance_cents: number;
  item_use: {
    id: number;
    item_name: string;
    price_paid_cents: number;
    duplicate: boolean;
  };
}> {
  return requestJson("/api/items/deploy/", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function claimSeat(
  roundId: number,
  seatSlug: string,
): Promise<{
  balance_cents: number;
  seat_claim: {
    id: number;
    seat_name: string;
    seat_color: string;
    price_paid_cents: number;
    duplicate: boolean;
  };
}> {
  return requestJson("/api/seats/claim/", {
    method: "POST",
    body: JSON.stringify({
      round_id: roundId,
      seat_slug: seatSlug,
      client_request_id: crypto.randomUUID(),
    }),
  });
}
