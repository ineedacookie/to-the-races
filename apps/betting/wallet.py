from __future__ import annotations

from apps.betting.models import Bet, LedgerEntry
from apps.core.errors import ServiceError
from apps.players.models import Player
from apps.racing.models import Round


def lock_player(player: Player | int) -> Player:
    player_id = player if isinstance(player, int) else player.pk
    return Player.objects.select_for_update().get(pk=player_id)


def record_ledger_entry(
    *,
    player: Player,
    kind: str,
    amount_cents: int,
    description: str,
    current_round: Round | None = None,
    bet: Bet | None = None,
) -> LedgerEntry:
    return LedgerEntry.objects.create(
        player=player,
        round=current_round,
        bet=bet,
        kind=kind,
        amount_cents=amount_cents,
        balance_after_cents=player.balance_cents,
        description=description,
    )


def change_balance(
    *,
    player: Player,
    amount_cents: int,
    kind: str,
    description: str,
    current_round: Round | None = None,
    bet: Bet | None = None,
    error_type: type[ServiceError] = ServiceError,
    insufficient_message: str = "That exceeds your available balance.",
) -> int:
    next_balance = player.balance_cents + amount_cents
    if next_balance < 0:
        raise error_type("insufficient_funds", insufficient_message)

    player.balance_cents = next_balance
    player.save(update_fields=["balance_cents", "updated_at"])
    record_ledger_entry(
        player=player,
        current_round=current_round,
        bet=bet,
        kind=kind,
        amount_cents=amount_cents,
        description=description,
    )
    return next_balance
