from __future__ import annotations

from apps.racing.models import ItemDefinition, RoundItemUse
from apps.racing.sim.types import RaceEffect


def build_race_effects(item_uses: list[RoundItemUse]) -> list[RaceEffect]:
    effects: list[RaceEffect] = []
    for use in item_uses:
        if use.item.target == ItemDefinition.Target.RACER:
            if use.target_entry is None:
                continue
            effects.append(
                RaceEffect(
                    kind=use.item.kind,
                    strength=use.item.effect_strength,
                    effect_id=use.pk,
                    item_name=use.item.name,
                    item_icon=use.item.icon,
                    item_color=use.item.color,
                    buyer=use.player.nickname,
                    racer_id=use.target_entry.racer_id,
                )
            )
        else:
            if use.track_lane is None or use.track_position is None:
                continue
            effects.append(
                RaceEffect(
                    kind=use.item.kind,
                    strength=use.item.effect_strength,
                    effect_id=use.pk,
                    item_name=use.item.name,
                    item_icon=use.item.icon,
                    item_color=use.item.color,
                    buyer=use.player.nickname,
                    lane=use.track_lane,
                    position=use.track_position,
                )
            )
    return effects


def serialize_effects(effects: list[RaceEffect]) -> list[dict[str, float | int | str | None]]:
    serialized: list[dict[str, float | int | str | None]] = []
    for effect in effects:
        payload: dict[str, float | int | str | None] = {
            "id": effect.effect_id,
            "kind": effect.kind,
            "item_name": effect.item_name,
            "item_icon": effect.item_icon,
            "item_color": effect.item_color,
            "buyer": effect.buyer,
            "strength": effect.strength,
        }
        if effect.racer_id is not None:
            payload["target_racer_id"] = effect.racer_id
        if effect.lane is not None:
            payload["lane"] = effect.lane
        if effect.position is not None:
            payload["position"] = effect.position
        serialized.append(payload)
    return serialized
