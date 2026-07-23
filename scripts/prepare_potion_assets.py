from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
POTION_DIR = ROOT / "static" / "assets" / "items" / "potions"

PURPLE_PALETTE = {
    (57, 120, 168, 255): (145, 84, 196, 255),
    (57, 71, 120, 255): (87, 55, 137, 255),
    (40, 204, 223, 255): (216, 137, 255, 255),
}

WATER_PALETTE = {
    (57, 120, 168, 255): (104, 190, 225, 255),
    (57, 71, 120, 255): (52, 110, 150, 255),
    (40, 204, 223, 255): (190, 245, 255, 255),
}

GROWTH_PALETTE = {
    (57, 120, 168, 255): (210, 112, 44, 255),
    (57, 71, 120, 255): (125, 57, 31, 255),
    (40, 204, 223, 255): (255, 208, 92, 255),
}

SHRINK_PALETTE = {
    (57, 120, 168, 255): (63, 170, 164, 255),
    (57, 71, 120, 255): (35, 89, 107, 255),
    (40, 204, 223, 255): (154, 255, 231, 255),
}

TRANSFORM_PALETTE = {
    (57, 120, 168, 255): (208, 71, 157, 255),
    (57, 71, 120, 255): (103, 45, 121, 255),
    (40, 204, 223, 255): (255, 176, 225, 255),
}

DERIVATIVE_PALETTES = {
    "purple.png": PURPLE_PALETTE,
    "water.png": WATER_PALETTE,
    "growth.png": GROWTH_PALETTE,
    "shrink.png": SHRINK_PALETTE,
    "transform.png": TRANSFORM_PALETTE,
}


def main() -> None:
    source_path = POTION_DIR / "blue.png"
    with Image.open(source_path) as source:
        blue = source.convert("RGBA")

    for filename, palette in DERIVATIVE_PALETTES.items():
        output_path = POTION_DIR / filename
        derivative = Image.new("RGBA", blue.size)
        derivative.putdata([palette.get(pixel, pixel) for pixel in blue.getdata()])
        derivative.save(output_path, optimize=True)
        print(f"Prepared {output_path.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
