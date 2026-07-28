"""Generate project-original track item PNGs and potion palette derivatives.

Track sprites are deterministic 32×32 pixel art authored for this repo.
Potion derivatives palette-swap FunnyDude's CC0 blue.png (see potions/README.md).
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
POTION_DIR = ROOT / "static" / "assets" / "items" / "potions"
TRACK_DIR = ROOT / "static" / "assets" / "items" / "track"
MANIFEST_PATH = TRACK_DIR / "manifest.json"

Color = tuple[int, int, int, int]
Box = tuple[int, int, int, int]
TrackDrawer = Callable[[ImageDraw.ImageDraw], None]

POTION_PALETTES: dict[str, dict[Color, Color]] = {
    "fireproof.png": {
        (57, 120, 168, 255): (196, 84, 44, 255),
        (57, 71, 120, 255): (120, 45, 31, 255),
        (40, 204, 223, 255): (255, 176, 64, 255),
    },
    "nitro.png": {
        (57, 120, 168, 255): (196, 220, 44, 255),
        (57, 71, 120, 255): (92, 120, 31, 255),
        (40, 204, 223, 255): (255, 255, 120, 255),
    },
    "recovery.png": {
        (57, 120, 168, 255): (196, 84, 132, 255),
        (57, 71, 120, 255): (120, 45, 88, 255),
        (40, 204, 223, 255): (255, 192, 220, 255),
    },
    "ghost.png": {
        (57, 120, 168, 255): (168, 196, 220, 255),
        (57, 71, 120, 255): (96, 120, 152, 255),
        (40, 204, 223, 255): (240, 248, 255, 255),
    },
    "second_wind.png": {
        (57, 120, 168, 255): (64, 180, 196, 255),
        (57, 71, 120, 255): (36, 96, 120, 255),
        (40, 204, 223, 255): (176, 255, 240, 255),
    },
    "phoenix.png": {
        (57, 120, 168, 255): (220, 120, 44, 255),
        (57, 71, 120, 255): (140, 64, 24, 255),
        (40, 204, 223, 255): (255, 220, 96, 255),
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _swap_potion(filename: str, palette: dict[Color, Color]) -> None:
    source_path = POTION_DIR / "blue.png"
    with Image.open(source_path) as source:
        blue = source.convert("RGBA")
    derivative = Image.new("RGBA", blue.size)
    derivative.putdata([palette.get(pixel, pixel) for pixel in blue.getdata()])
    output_path = POTION_DIR / filename
    derivative.save(output_path, optimize=True)
    print(f"Prepared potion {output_path.relative_to(ROOT)}")


def _fill_ellipse(draw: ImageDraw.ImageDraw, bbox: Box, color: Color) -> None:
    draw.ellipse(bbox, fill=color)


def _fill_rect(draw: ImageDraw.ImageDraw, xy: Box, color: Color) -> None:
    draw.rectangle(xy, fill=color)


def _draw_banana(draw: ImageDraw.ImageDraw) -> None:
    _fill_ellipse(draw, (4, 10, 28, 22), (243, 188, 62, 255))
    _fill_ellipse(draw, (8, 14, 16, 20), (212, 160, 23, 255))
    _fill_rect(draw, (22, 10, 25, 16), (24, 33, 43, 255))


def _draw_pothole(draw: ImageDraw.ImageDraw) -> None:
    _fill_ellipse(draw, (2, 12, 30, 26), (61, 41, 20, 255))
    _fill_ellipse(draw, (7, 16, 25, 24), (24, 33, 43, 255))
    _fill_rect(draw, (4, 8, 10, 12), (90, 61, 30, 255))
    _fill_rect(draw, (22, 6, 27, 10), (90, 61, 30, 255))


def _draw_oil_slick(draw: ImageDraw.ImageDraw) -> None:
    _fill_ellipse(draw, (2, 13, 30, 25), (24, 33, 43, 255))
    _fill_ellipse(draw, (6, 14, 16, 18), (82, 97, 112, 255))
    _fill_ellipse(draw, (18, 19, 25, 22), (138, 106, 200, 255))


def _draw_boost_pad(draw: ImageDraw.ImageDraw) -> None:
    _fill_rect(draw, (2, 8, 30, 26), (28, 107, 69, 255))
    draw.polygon([(6, 12), (15, 17), (6, 22)], fill=(125, 255, 154, 255))
    draw.polygon([(15, 12), (25, 17), (15, 22)], fill=(125, 255, 154, 255))


def _draw_boxing_glove(draw: ImageDraw.ImageDraw) -> None:
    _fill_ellipse(draw, (5, 6, 21, 22), (239, 91, 91, 255))
    _fill_ellipse(draw, (14, 6, 28, 20), (239, 91, 91, 255))
    _fill_rect(draw, (8, 16, 28, 26), (239, 91, 91, 255))
    _fill_rect(draw, (11, 25, 25, 30), (143, 38, 48, 255))


def _draw_detour_sign(draw: ImageDraw.ImageDraw) -> None:
    draw.polygon([(16, 4), (28, 16), (16, 28), (4, 16)], fill=(243, 140, 44, 255))
    _fill_rect(draw, (14, 10, 18, 22), (24, 33, 43, 255))
    draw.polygon([(18, 12), (22, 16), (18, 20), (14, 16)], fill=(255, 248, 231, 255))


def _draw_speed_bump(draw: ImageDraw.ImageDraw) -> None:
    for x in range(2, 30, 6):
        color = (255, 248, 231, 255) if (x // 6) % 2 == 0 else (24, 33, 43, 255)
        _fill_rect(draw, (x, 18, x + 4, 26), color)
    _fill_ellipse(draw, (2, 10, 30, 22), (196, 160, 44, 255))
    _fill_rect(draw, (2, 14, 30, 18), (196, 160, 44, 255))


def _draw_stop_sign(draw: ImageDraw.ImageDraw) -> None:
    draw.polygon(
        [(16, 3), (26, 8), (29, 18), (26, 28), (16, 31), (6, 28), (3, 18), (6, 8)],
        fill=(196, 44, 44, 255),
    )
    _fill_rect(draw, (10, 13, 22, 17), (255, 248, 231, 255))
    _fill_rect(draw, (14, 17, 18, 21), (255, 248, 231, 255))


def _draw_glass_door(draw: ImageDraw.ImageDraw) -> None:
    _fill_rect(draw, (6, 4, 26, 28), (126, 196, 255, 180))
    _fill_rect(draw, (8, 6, 24, 26), (190, 230, 255, 120))
    _fill_rect(draw, (10, 8, 14, 20), (255, 255, 255, 200))
    _fill_rect(draw, (22, 4, 24, 28), (24, 33, 43, 255))
    _fill_rect(draw, (6, 26, 26, 28), (24, 33, 43, 255))


def _draw_rock_wall(draw: ImageDraw.ImageDraw) -> None:
    colors = [(120, 120, 128, 255), (96, 96, 104, 255), (144, 144, 152, 255)]
    blocks = [
        (4, 8, 14, 16),
        (14, 6, 24, 14),
        (8, 16, 18, 24),
        (18, 14, 28, 22),
        (4, 22, 16, 30),
        (16, 22, 28, 30),
    ]
    for index, block in enumerate(blocks):
        _fill_rect(draw, block, colors[index % len(colors)])
        x0, y0, x1, y1 = block
        _fill_rect(draw, (x0, y0, x1, y0 + 1), (180, 180, 188, 255))
        _fill_rect(draw, (x0, y1 - 1, x1, y1), (64, 64, 72, 255))


def _draw_roomba_vacuum(draw: ImageDraw.ImageDraw) -> None:
    _fill_ellipse(draw, (4, 8, 28, 26), (96, 104, 112, 255))
    _fill_ellipse(draw, (8, 10, 24, 22), (64, 72, 80, 255))
    _fill_ellipse(draw, (12, 12, 20, 18), (180, 188, 196, 255))
    _fill_rect(draw, (14, 4, 18, 10), (24, 33, 43, 255))
    _fill_ellipse(draw, (20, 6, 24, 10), (255, 64, 64, 255))


def _draw_springboard(draw: ImageDraw.ImageDraw) -> None:
    _fill_rect(draw, (4, 20, 28, 28), (28, 107, 69, 255))
    for x in range(6, 26, 4):
        _fill_rect(draw, (x, 14, x + 2, 20), (180, 180, 188, 255))
    _fill_rect(draw, (6, 10, 26, 14), (125, 255, 154, 255))
    draw.polygon([(16, 4), (22, 10), (10, 10)], fill=(255, 248, 231, 255))


def _draw_magnet_mine(draw: ImageDraw.ImageDraw) -> None:
    _fill_ellipse(draw, (6, 10, 26, 26), (196, 44, 44, 255))
    _fill_rect(draw, (10, 6, 14, 12), (255, 64, 64, 255))
    _fill_rect(draw, (18, 6, 22, 12), (64, 120, 255, 255))
    _fill_rect(draw, (13, 14, 19, 20), (24, 33, 43, 255))


def _draw_portal_gate(draw: ImageDraw.ImageDraw) -> None:
    _fill_ellipse(draw, (4, 4, 28, 28), (120, 64, 196, 255))
    _fill_ellipse(draw, (8, 8, 24, 24), (24, 33, 43, 255))
    _fill_ellipse(draw, (10, 10, 22, 22), (201, 140, 255, 255))
    _fill_ellipse(draw, (13, 13, 19, 19), (255, 248, 231, 255))


TRACK_DRAWERS: dict[str, TrackDrawer] = {
    "banana.png": _draw_banana,
    "pothole.png": _draw_pothole,
    "oil_slick.png": _draw_oil_slick,
    "boost_pad.png": _draw_boost_pad,
    "boxing_glove.png": _draw_boxing_glove,
    "detour_sign.png": _draw_detour_sign,
    "speed_bump.png": _draw_speed_bump,
    "stop_sign.png": _draw_stop_sign,
    "glass_door.png": _draw_glass_door,
    "rock_wall.png": _draw_rock_wall,
    "roomba_vacuum.png": _draw_roomba_vacuum,
    "springboard.png": _draw_springboard,
    "magnet_mine.png": _draw_magnet_mine,
    "portal_gate.png": _draw_portal_gate,
}


def _draw_track_sprite(filename: str, drawer: TrackDrawer) -> None:
    image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    drawer(ImageDraw.Draw(image))
    output_path = TRACK_DIR / filename
    image.save(output_path, optimize=True)
    print(f"Prepared track item {output_path.relative_to(ROOT)}")


def main() -> None:
    TRACK_DIR.mkdir(parents=True, exist_ok=True)
    for filename, palette in POTION_PALETTES.items():
        _swap_potion(filename, palette)
    for filename, drawer in TRACK_DRAWERS.items():
        _draw_track_sprite(filename, drawer)

    manifest = {
        "license": "Project-original pixel art generated by scripts/prepare_item_assets.py",
        "size": "32x32",
        "files": {name: _sha256(TRACK_DIR / name) for name in sorted(TRACK_DRAWERS)},
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {MANIFEST_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
