from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHEETS = ROOT / "static" / "assets" / "racers" / "sheets"
PORTRAITS = ROOT / "static" / "assets" / "racers" / "portraits"
MANIFEST = ROOT / "static" / "assets" / "racers" / "manifest.json"

FRAME_COUNTS = {
    "skeleton": 4,
    "mushroom": 8,
    "goblin": 8,
    "flying-eye": 8,
    "mimic": 6,
    "rat": 8,
    "slime": 6,
    "bat": 11,
}


@dataclass(frozen=True, slots=True)
class AssetRecord:
    key: str
    sheet: str
    portrait: str
    frame_width: int
    frame_height: int
    frame_count: int
    sha256: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def process_asset(key: str, frame_count: int) -> AssetRecord:
    sheet_path = SHEETS / f"{key}.png"
    with Image.open(sheet_path) as source:
        image = source.convert("RGBA")
        if image.width % frame_count != 0:
            raise ValueError(f"{sheet_path.name} width is not divisible by {frame_count}.")
        frame_width = image.width // frame_count
        portrait = image.crop((0, 0, frame_width, image.height))
        portrait.save(PORTRAITS / f"{key}.png", optimize=True)
        return AssetRecord(
            key=key,
            sheet=f"/static/assets/racers/sheets/{key}.png",
            portrait=f"/static/assets/racers/portraits/{key}.png",
            frame_width=frame_width,
            frame_height=image.height,
            frame_count=frame_count,
            sha256=sha256(sheet_path),
        )


def main() -> None:
    PORTRAITS.mkdir(parents=True, exist_ok=True)
    records = [
        process_asset(key, frame_count) for key, frame_count in FRAME_COUNTS.items()
    ]
    MANIFEST.write_text(
        json.dumps(
            {
                "license": "CC0-1.0",
                "source": "https://luizmelo.itch.io/",
                "racers": [asdict(record) for record in records],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Prepared {len(records)} racer sprite sets.")


if __name__ == "__main__":
    main()
