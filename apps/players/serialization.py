from __future__ import annotations

from apps.players.avatar import avatar_version, normalize_avatar_recipe
from apps.players.models import Player


def player_identity_fields(
    player: Player,
    *,
    include_avatar_recipe: bool = False,
    include_api_key: bool = False,
) -> dict[str, object]:
    recipe = normalize_avatar_recipe(player.avatar_recipe, seed=player.pk)
    version = avatar_version(recipe)
    fields: dict[str, object] = {
        "id": player.pk,
        "nickname": player.nickname,
        "balance_cents": player.balance_cents,
        "avatar_version": version,
        "avatar_url": f"/api/players/{player.pk}/avatar/?v={version}",
        "replay_preference": player.replay_preference,
    }
    if include_avatar_recipe:
        fields["avatar_recipe"] = recipe
    if include_api_key:
        fields["api_key"] = player.api_key
    return fields
