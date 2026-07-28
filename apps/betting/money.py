from __future__ import annotations


def whole_dollars(cents: int) -> str:
    return f"{cents // 100:,}"


def format_money(cents: int) -> str:
    sign = "−" if cents < 0 else ""
    dollars, remainder = divmod(abs(cents), 100)
    if remainder == 0:
        return f"{sign}${dollars:,}"
    return f"{sign}${dollars:,}.{remainder:02d}"


def available_funds_message(required_cents: int) -> str:
    return f"You need {whole_dollars(required_cents)} dollars in available fun money."


def remaining_budget_message(remaining_cents: int) -> str:
    return f"You may still spend {whole_dollars(remaining_cents)} dollars."


def stake_cap_message(*, cap_cents: int, remaining_cents: int) -> str:
    return (
        f"That exceeds this round's {format_money(cap_cents)} stake cap. "
        f"You may stake {format_money(remaining_cents)} more."
    )
