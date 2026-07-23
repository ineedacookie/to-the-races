export function formatMoney(cents: number): string {
  const sign = cents < 0 ? "−" : "";
  const dollars = Math.abs(cents) / 100;
  return `${sign}$${dollars.toLocaleString(undefined, {
    minimumFractionDigits: Number.isInteger(dollars) ? 0 : 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatOdds(value: string): string {
  return `${Number.parseFloat(value).toFixed(2)}×`;
}

export function secondsRemaining(deadline: string, serverOffsetMs: number): number {
  const remaining = Date.parse(deadline) - (Date.now() + serverOffsetMs);
  return Math.max(0, Math.ceil(remaining / 1000));
}

export function activeCountdownSeconds(
  startsAt: string | null,
  endsAt: string | null,
  serverOffsetMs: number,
): number | null {
  if (startsAt === null || endsAt === null) {
    return null;
  }
  if (Date.now() + serverOffsetMs < Date.parse(startsAt)) {
    return null;
  }
  return secondsRemaining(endsAt, serverOffsetMs);
}

export function ordinal(value: number): string {
  const mod100 = value % 100;
  if (mod100 >= 11 && mod100 <= 13) {
    return `${value}th`;
  }
  switch (value % 10) {
    case 1:
      return `${value}st`;
    case 2:
      return `${value}nd`;
    case 3:
      return `${value}rd`;
    default:
      return `${value}th`;
  }
}

export function dnfLabel(reason: string): string {
  switch (reason) {
    case "fire_pit":
      return "DNF · FIRE PIT";
    case "stomped":
      return "DNF · STOMPED";
    case "track_consumed":
      return "DNF · FIRE";
    case "finish_countdown":
      return "DNF · CLOCK";
    case "knocked_out":
      return "DNF · KO";
    case "timeout":
      return "DNF · TIME";
    default:
      return "DNF";
  }
}
