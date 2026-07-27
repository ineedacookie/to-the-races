# To The Races

A locally hosted fantasy race night: one shared race display, phone-sized betting sheets,
passwordless device identities, and completely fictional money.

## Requirements

- Python 3.13
- Node.js 22 or newer
- `uv` (the setup command below also works with the project-local executable)

## Setup

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install uv
.venv/bin/uv sync --all-groups
npm install
```

## Run on the local network

```bash
.venv/bin/python scripts/serve.py
```

The launcher builds the frontend, migrates and seeds SQLite, prefers port `1515`, falls
back to `5151`, binds to all interfaces, and prints the betting and display URLs.

- `/display/` is the shared, fullscreen race view.
- `/bet/` is the mobile betting sheet.
- `/admin/` controls racers and room settings.

Create an optional local admin login after the first run:

```bash
.venv/bin/python manage.py createsuperuser
```

For code-only iteration, use `--skip-build`; use `npm run build` after frontend changes.
`--reload` enables ASGI reloads. Keep the server at one worker: the MVP intentionally uses
an in-memory Channels layer. Redis and Postgres are only needed for a multi-process host.
To keep an always-on local game bounded, full animation/event payloads are retained for the
latest 12 rounds; compact results, bets, balances, and ledger history remain available.
Static artwork is cached by browsers for one hour to avoid repeated LAN revalidation. Set
`STATIC_ASSET_CACHE_SECONDS=0` while actively replacing artwork.

If phones cannot connect, ensure they are on the same Wi-Fi and allow incoming connections
for Python in the macOS firewall.

## Quality checks

```bash
.venv/bin/ruff check .
.venv/bin/mypy .
.venv/bin/pytest
npm run lint
npm run typecheck
npm test
npm run build
```

Install Playwright's Chromium once with `npx playwright install chromium`, then run the
browser checks with `npm run e2e`.

## Game rules

- Four non-player fantasy racers run left-to-right.
- Races run at a slower, roughly 39-second baseline pace and end as soon as every racer
  has either finished or been eliminated. The race display shows `LIVE`, not a guessed
  finish countdown.
- Betting closes before the server generates a seeded, deterministic race.
- Players may spread fixed-odds winner bets across racers, up to the configured round cap.
- During the open phase, players can also buy **schemes** from the trackside black market—
  tonics for racers or track hazards (bananas, potholes)—subject to available balance plus
  per-round spend and use caps.
- Every tonic has a deterministic, seed-driven activation chance; none guarantees an outcome.
  Same-target stacks get progressively weaker, and an activated guard tonic lowers the chance
  that trip or confusion tonics take hold.
- Growth tonic makes a racer larger, sturdier, slower, and easier to collide with; shrink tonic
  makes them smaller, quicker, and more fragile; transformation tonic borrows another racer's
  sprite and a bounded blend of their stats. All three may fizzle.
- Tonic drinks use locally vendored CC0 pixel art and are color-coded and labeled during
  pre-race drinking. Multiple bottles and placed track hazards remain visible during lineup
  lock so players can see the public schemes.
- **Prestige seats** in the grandstand can be claimed once per round; the display shows who
  holds each seat above a CC0 pixel-art spectator (the throne gets a crown). Seats also require
  enough available balance.
- While locked, racing, or during results, the crowd bar lets spectators **cheer**, **boo**,
  or send a short custom shout (optionally aimed at a racer). A seated spectator's mascot
  animates beneath a three-second speech bubble at their exact grandstand seat: green for
  cheers, red for boos, and black for custom shouts. The submit cooldown matches that display
  time.
- **Hall of Fame** tracks top balances and wins; the **Oops Ledger** celebrates the deepest
  fictional deficits. Negative balances are play-money only—no real debt, no real consequences.
- The betting sheet keeps the live lineup on one viewport. Its toolbar tracks player, money,
  round, and clock; Shop, Inventory, Boards, Account, and recent activity live in the menu.
- Bets may drive balances negative, but items and prestige seats cannot be bought on credit.
- Tripped racers stay in a half-speed crawling state until they roll the deliberately uncommon
  `get_up` action. Other actions are separate from state: for example, a `turn` action still moves
  a crawler sideways, while a standing racer's `get_up` action is simply wasted. A stomp while
  they are down destroys them, and racers that wander beyond the outer lanes fall into a fire pit;
  both outcomes are DNF.
- Crawling racers may cross the finish line. The first finisher starts a visible 30-second finish
  clock; active racers that have not crossed when it expires are eliminated and marked DNF.
- Crossing time determines placement.
- If nobody finishes, the house keeps every stake.

All third-party art and audio is stored locally and documented in [CREDITS.md](CREDITS.md).
This application is intended for local entertainment only; it does not use real money.
