from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "static" / "assets" / "crowd" / "source"
OUTPUT_DIR = SOURCE_DIR.parent
CELL_SIZE = (64, 112)
CELL_GAP = (4, 4)
SPECTATOR_COUNT = 16

LAYER_FILES = {
    "skin": "skin.png",
    "eyes": "eyes.png",
    "bottoms": "bottoms.png",
    "tops": "tops.png",
    "shoes": "shoes.png",
    "hair": "hair.png",
}
LAYER_ORDER = ("skin", "eyes", "bottoms", "tops", "shoes", "hair")
LAYER_STRIDES = {
    "skin": (1, 0),
    "eyes": (5, 2),
    "bottoms": (11, 17),
    "tops": (13, 29),
    "shoes": (7, 3),
    "hair": (9, 5),
}


def _grid_size(image: Image.Image) -> tuple[int, int]:
    cell_width, cell_height = CELL_SIZE
    gap_x, gap_y = CELL_GAP
    columns = max(round((image.width + gap_x) / (cell_width + gap_x)), 1)
    rows = max(round((image.height + gap_y) / (cell_height + gap_y)), 1)
    expected_width = columns * cell_width + (columns - 1) * gap_x
    expected_height = rows * cell_height + (rows - 1) * gap_y
    if (
        abs(image.width - expected_width) > gap_x
        or abs(image.height - expected_height) > gap_y
    ):
        raise ValueError(f"Unexpected Pixel People sheet size: {image.size}")
    return columns, rows


def _cell(image: Image.Image, index: int) -> Image.Image:
    columns, rows = _grid_size(image)
    cell_width, cell_height = CELL_SIZE
    gap_x, gap_y = CELL_GAP
    normalized_index = index % (columns * rows)
    column = normalized_index % columns
    row = normalized_index // columns
    left = column * (cell_width + gap_x)
    top = row * (cell_height + gap_y)
    return image.crop((left, top, left + cell_width, top + cell_height))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    layers = {
        name: Image.open(SOURCE_DIR / filename).convert("RGBA")
        for name, filename in LAYER_FILES.items()
    }
    manifest_entries: list[dict[str, object]] = []

    for spectator_index in range(SPECTATOR_COUNT):
        spectator = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
        recipe: dict[str, int] = {}
        for layer_name in LAYER_ORDER:
            stride, offset = LAYER_STRIDES[layer_name]
            layer_index = spectator_index * stride + offset
            recipe[layer_name] = layer_index
            spectator.alpha_composite(_cell(layers[layer_name], layer_index))

        filename = f"spectator-{spectator_index:02d}.png"
        output_path = OUTPUT_DIR / filename
        spectator.save(output_path, optimize=True)
        manifest_entries.append(
            {
                "file": filename,
                "recipe": recipe,
                "sha256": _sha256(output_path),
            }
        )

    manifest = {
        "source": "https://opengameart.org/content/pixel-people",
        "author": "TokyoGeisha",
        "license": "CC0 1.0 Universal / public domain",
        "spectator_count": SPECTATOR_COUNT,
        "cell_size": list(CELL_SIZE),
        "spectators": manifest_entries,
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
