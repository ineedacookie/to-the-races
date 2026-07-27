from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
CROWD_DIR = ROOT / "static" / "assets" / "crowd"


def test_generated_crowd_manifest_matches_pixel_people_assets() -> None:
    manifest = json.loads((CROWD_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["license"] == "CC0 1.0 Universal / public domain"
    assert manifest["spectator_count"] == 16
    assert len(manifest["spectators"]) == 16

    for spectator in manifest["spectators"]:
        path = CROWD_DIR / spectator["file"]
        assert path.exists()
        assert Image.open(path).size == (64, 112)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == spectator["sha256"]
