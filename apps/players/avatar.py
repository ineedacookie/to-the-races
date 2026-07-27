from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Final

from django.core.exceptions import ValidationError
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "static" / "assets" / "crowd" / "source"
CELL_SIZE: Final = (64, 112)
CELL_GAP: Final = (4, 4)
AVATAR_LAYER_ORDER: Final = ("skin", "eyes", "bottoms", "tops", "shoes", "hair")
AVATAR_LAYER_COUNTS: Final = {
    "skin": 12,
    "eyes": 17,
    "bottoms": 150,
    "tops": 253,
    "shoes": 34,
    "hair": 65,
}
AVATAR_SOURCE_FILES: Final = {layer: SOURCE_DIR / f"{layer}.png" for layer in AVATAR_LAYER_ORDER}
AVATAR_RENDER_VERSION: Final = 1

AvatarRecipe = dict[str, int]


def default_avatar_recipe(seed: int) -> AvatarRecipe:
    recipe: AvatarRecipe = {}
    for layer in AVATAR_LAYER_ORDER:
        digest = hashlib.sha256(f"{seed}:{layer}".encode()).digest()
        recipe[layer] = int.from_bytes(digest[:4], "big") % AVATAR_LAYER_COUNTS[layer]
    return recipe


def normalize_avatar_recipe(value: object, *, seed: int) -> AvatarRecipe:
    if value in (None, {}):
        return default_avatar_recipe(seed)
    if not isinstance(value, dict):
        raise ValidationError({"avatar": "Avatar choices must be a JSON object."})

    if set(value) != set(AVATAR_LAYER_ORDER):
        raise ValidationError({"avatar": "Choose every avatar layer exactly once."})

    recipe: AvatarRecipe = {}
    for layer in AVATAR_LAYER_ORDER:
        index = value.get(layer)
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValidationError({"avatar": f"{layer.title()} must be a whole-number choice."})
        if not 0 <= index < AVATAR_LAYER_COUNTS[layer]:
            raise ValidationError({"avatar": f"{layer.title()} choice is out of range."})
        recipe[layer] = index
    return recipe


def avatar_version(recipe: AvatarRecipe) -> str:
    payload = json.dumps(
        {"render_version": AVATAR_RENDER_VERSION, "recipe": recipe},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@lru_cache(maxsize=len(AVATAR_LAYER_ORDER))
def _source_layer(layer: str) -> Image.Image:
    return Image.open(AVATAR_SOURCE_FILES[layer]).convert("RGBA")


def _cell(image: Image.Image, index: int) -> Image.Image:
    cell_width, cell_height = CELL_SIZE
    gap_x, gap_y = CELL_GAP
    columns = max(round((image.width + gap_x) / (cell_width + gap_x)), 1)
    column = index % columns
    row = index // columns
    left = column * (cell_width + gap_x)
    top = row * (cell_height + gap_y)
    return image.crop((left, top, left + cell_width, top + cell_height))


@lru_cache(maxsize=512)
def _render_avatar_png(recipe_items: tuple[tuple[str, int], ...]) -> bytes:
    recipe = dict(recipe_items)
    avatar = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
    for layer in AVATAR_LAYER_ORDER:
        avatar.alpha_composite(_cell(_source_layer(layer), recipe[layer]))

    output = BytesIO()
    avatar.save(output, format="PNG", optimize=True)
    return output.getvalue()


def render_avatar_png(recipe: AvatarRecipe) -> bytes:
    return _render_avatar_png(tuple((layer, recipe[layer]) for layer in AVATAR_LAYER_ORDER))
