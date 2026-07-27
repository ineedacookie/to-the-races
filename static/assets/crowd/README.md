# Pixel People crowd

The bleacher spectators are assembled from **Pixel People** by TokyoGeisha.

- Source: https://opengameart.org/content/pixel-people
- License: CC0 1.0 Universal / public domain
- Original archive: `Pixel People.zip`
- Original cell layout: 64×112 pixels with 4-pixel spacing

The original modular layer sheets are retained in `source/`. Run:

```bash
python scripts/prepare_crowd_assets.py
```

to deterministically rebuild `spectator-00.png` through `spectator-15.png` and
their checksum manifest. The generated combinations are project derivatives
released under the same CC0 terms.

The name-screen character builder reads these same layer sheets for its live
preview. Django stores the six selected indexes and composites a cacheable
64×112 PNG through `apps/players/avatar.py` for the display bleachers.
