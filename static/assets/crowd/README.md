# Pixel People crowd

The bleacher spectators are assembled from **Pixel People** by TokyoGeisha.

- Source: https://opengameart.org/content/pixel-people
- License: CC0 1.0 Universal / public domain
- Original archive: `Pixel People.zip`
- Original cell layout: 64×112 pixels with 4-pixel spacing

The six modular layer sheets used by the game are retained in `source/`. The
name-screen character builder reads them for its live preview. Django stores
the selected indexes and composites a cacheable 64×112 PNG through
`apps/players/avatar.py` for the display bleachers.
