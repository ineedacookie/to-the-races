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


def main() -> None:
    source_path = POTION_DIR / "blue.png"
    output_path = POTION_DIR / "purple.png"
    with Image.open(source_path) as source:
        blue = source.convert("RGBA")

    purple = Image.new("RGBA", blue.size)
    purple.putdata([PURPLE_PALETTE.get(pixel, pixel) for pixel in blue.getdata()])
    purple.save(output_path, optimize=True)
    print(f"Prepared {output_path.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
