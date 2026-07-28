import type {
  ConnectedSpectator,
  SeatClaim,
  SeatDefinition,
} from "../shared/types";

const CROWD_SLOTS_PER_ROW = 8;
const MIN_CROWD_ROWS = 3;

interface PrestigePosition {
  seat: SeatDefinition;
  claim: SeatClaim | undefined;
  spectator: ConnectedSpectator | undefined;
  rank: number;
}

interface CrowdSlot {
  rowIndex: number;
  slotIndex: number;
  spectator: ConnectedSpectator | undefined;
}

interface CrowdRow {
  rowIndex: number;
  slots: CrowdSlot[];
}

interface GrandstandModel {
  prestige: PrestigePosition[];
  crowdRows: CrowdRow[];
}

export function spectatorArtPath(spectator: ConnectedSpectator): string {
  return `/api/players/${spectator.player_id}/avatar/?v=${encodeURIComponent(
    spectator.avatar_version,
  )}`;
}

export function crowdRowLabel(rowIndex: number, rowCount: number): string {
  if (rowIndex === rowCount - 1) {
    return "Trackside row";
  }
  if (rowIndex === rowCount - 2) {
    return "Middle row";
  }
  if (rowIndex === rowCount - 3) {
    return "Upper row";
  }
  return `Row ${rowCount - rowIndex}`;
}

function stableCrowdSeatHash(playerId: number): number {
  let value = playerId >>> 0;
  value ^= value >>> 16;
  value = Math.imul(value, 0x7feb352d);
  value ^= value >>> 15;
  value = Math.imul(value, 0x846ca68b);
  return (value ^ (value >>> 16)) >>> 0;
}

export function buildGrandstandModel(
  catalog: SeatDefinition[],
  claims: SeatClaim[],
  spectators: ConnectedSpectator[],
): GrandstandModel {
  const connectedByPlayer = new Map(
    spectators.map((spectator) => [spectator.player_id, spectator]),
  );
  const prestigePlayerIds = new Set<number>();
  const prestige = catalog.map((seat, index): PrestigePosition => {
    const claim = claims.find((candidate) => candidate.seat_slug === seat.slug);
    const spectator =
      claim === undefined ? undefined : connectedByPlayer.get(claim.player_id);
    if (spectator !== undefined) {
      prestigePlayerIds.add(spectator.player_id);
    }
    return {
      seat,
      claim,
      spectator,
      rank: catalog.length - index,
    };
  });

  const crowd = spectators
    .filter((spectator) => !prestigePlayerIds.has(spectator.player_id))
    .sort((first, second) => first.player_id - second.player_id);
  const rowCount = Math.max(
    MIN_CROWD_ROWS,
    Math.ceil(crowd.length / CROWD_SLOTS_PER_ROW),
  );
  const crowdRows = Array.from({ length: rowCount }, (_, rowIndex): CrowdRow => ({
    rowIndex,
    slots: Array.from(
      { length: CROWD_SLOTS_PER_ROW },
      (_, slotIndex): CrowdSlot => ({
        rowIndex,
        slotIndex,
        spectator: undefined,
      }),
    ),
  }));

  const slotCount = rowCount * CROWD_SLOTS_PER_ROW;
  const occupiedSlots = new Set<number>();
  for (const spectator of crowd) {
    let flatSlotIndex = stableCrowdSeatHash(spectator.player_id) % slotCount;
    while (occupiedSlots.has(flatSlotIndex)) {
      flatSlotIndex = (flatSlotIndex + 1) % slotCount;
    }
    occupiedSlots.add(flatSlotIndex);
    const rowIndex = Math.floor(flatSlotIndex / CROWD_SLOTS_PER_ROW);
    const slotIndex = flatSlotIndex % CROWD_SLOTS_PER_ROW;
    const row = crowdRows[rowIndex];
    if (row !== undefined) {
      row.slots[slotIndex] = { rowIndex, slotIndex, spectator };
    }
  }

  return {
    prestige,
    crowdRows,
  };
}
