# To The Races

A locally hosted fantasy race night: one shared race display, phone-sized betting sheets,
passwordless username accounts, and completely fictional money.

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
- New players create a username and character; returning players can enter that username with no
  password. Logging in restores the same balance, inventory, bets, seat, and avatar on multiple
  devices.

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
- Racers move at 1.5× the previous track speed, for a roughly 26-second baseline race, and
  each race ends as soon as every racer has either finished or been eliminated. The race
  display shows `LIVE`, not a guessed finish countdown.
- Betting closes before the server generates a seeded, deterministic race.
- Players may spread fixed-odds winner bets across racers with no maximum stake. The lineup has one
  whole-dollar stake field, and bets may push the fictional balance as far negative as players want.
- Fixed odds are calibrated from deterministic samples of the complete race simulation, including
  lane position, collisions, actions, crawling and recovery, knockouts, finish-clock eliminations,
  no-finisher house wins, and each racer's likelihood of wandering into a fire pit.
- Players can buy **schemes** from the trackside black market into a persistent four-slot bag.
  Potions must be assigned to a racer during betting and are drunk at the next race start. Bananas,
  potholes, oil slicks, boost pads, and boxing gloves are instead activated while the race is live;
  choosing a racer portrait places the item just ahead in that racer's current path. Deployments
  still respect per-round spend and use caps. Every bag card has its own **Use** control and a trash
  control; discarding permanently frees the slot without refunding the purchase.
- Every tonic has a deterministic, seed-driven activation chance; none guarantees an outcome.
  Every activated potion in a same-target stack applies another adjustment, though later copies
  get progressively weaker. An activated guard tonic lowers the chance that trip or confusion
  tonics take hold.
- Growth tonic makes a racer larger, sturdier, slower, and easier to collide with; shrink tonic
  makes them smaller, quicker, and more fragile; transformation tonic borrows another racer's
  identity, sprite, and a bounded blend of their stats. If the transformed body crosses first,
  the borrowed identity receives the official win and its bettors are paid. All three may fizzle.
- Tonic drinks use locally vendored CC0 pixel art and are grouped as positive, negative, or neutral
  in the shop. They are color-coded, labeled, and publicly visible during pre-race drinking. Live
  track items cost substantially more, remain on the display after triggering, and can affect each
  racer once.
- **Prestige seats** in the grandstand can be claimed once per round; a connected holder moves
  into its clearly numbered front-row position. Depending on the seat, it adds 5%, 10%, 15%, or
  25% to the profit from every winning bet that round. Seats require available balance and range
  from $40 to $150.
- The display bleachers contain several ranked rows populated only by players whose betting
  pages are currently connected. Regular spectators are scattered among stable pseudo-random
  bleacher spots instead of filling one row from the left. New players build a custom CC0 Pixel
  People avatar from skin, eyes, hair, top, bottoms, and shoes on the name screen, and can reopen
  that builder from Account; the same generated person appears beside their username in the
  bleachers. Multiple tabs still produce one spectator, and the avatar leaves after the player's
  final connection closes. Prestige holders move into clearly marked #4 through #1 positions
  without also appearing in the general rows.
- While locked, racing, or during results, the crowd bar lets spectators **cheer**, **boo**,
  **cry**, or send a short custom shout. A seated spectator's mascot animates beneath a
  three-second speech bubble at their exact grandstand seat: green for cheers, red for boos,
  blue for crying, and black for custom shouts. The submit cooldown matches that display time.
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
- Showboat actions nearly stop a racer for a randomized 1.6–2.8 seconds while they wave to Mom,
  thank imaginary sponsors, inspect emergency snacks, or perform other strategically terrible bits.
- Crawling racers may cross the finish line. The first finisher starts a visible 30-second finish
  clock; active racers that have not crossed when it expires are eliminated and marked DNF.
- Crossing time determines placement.
- If nobody finishes, the house keeps every stake.

All third-party art and audio is stored locally and documented in [CREDITS.md](CREDITS.md).
This application is intended for local entertainment only; it does not use real money.
