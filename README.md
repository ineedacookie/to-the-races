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

The launcher builds the frontend, migrates and seeds SQLite, fingerprints deploy assets,
prefers port `1515`, falls back to `5151`, binds to all interfaces, and prints the betting
and display URLs.

- `/display/` is the shared, fullscreen race view.
- `/bet/` is the mobile betting sheet.
- `/house/` is the public House Account with operating totals, round history, and recent activity.
- `/admin/` controls racers and room settings.
- New players create a username and character; returning players can enter that username with no
  password. Logging in restores the same balance, inventory, bets, seat, and avatar on multiple
  devices.

Create an optional local admin login after the first run:

```bash
.venv/bin/python manage.py createsuperuser
```

For active development, use `--debug --reload`; add `--skip-build` for backend-only changes.
Normal LAN mode gives fingerprinted CSS and JavaScript long-lived immutable URLs, caches stable
artwork for `STATIC_ASSET_CACHE_SECONDS` (one hour by default), and keeps routine HTTP access
logs quiet. Add `--access-log` when request-level diagnostics are useful. A `304 Not Modified`
in that log is a successful cache validation, not an error.

Keep the server at one worker: the MVP intentionally uses an in-memory Channels layer. Redis
and Postgres are only needed for a multi-process host.
To keep an always-on local game bounded, full animation/event payloads are retained for the
latest 12 rounds; compact results, bets, balances, and ledger history remain available.

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
- Players may spread fixed-odds winner bets across racers up to a configurable per-round stake
  cap (default $150 total across all bets that round). New players begin with $200. The lineup
  accepts stakes to the cent; each bet must fit the player's available balance and remaining round
  cap.
- A player with less than $10 can take one **Track Medic** job per round at any point during that
  round: patch 2–5 server-selected wounds on a random current racer to earn $20 total. The payout
  is idempotent and cannot be replayed.
- Fixed odds are calibrated from deterministic samples of the complete race simulation, including
  lane position, collisions, actions, crawling and recovery, knockouts, finish-clock eliminations,
  no-finisher house wins, and each racer's likelihood of wandering into a fire pit. Once enough
  history exists, the market blends that simulation with each racer's latest 50 settled starts;
  older results no longer affect the odds.
- Players can buy **schemes** from the trackside black market into a persistent four-slot bag.
  **Permanent upgrades** can expand that bag to six or eight slots for $150 and $350; the larger
  tier requires the first. Effective capacity is always the room baseline or your highest owned
  tier, whichever is larger. Potions must be assigned to a racer during betting and are drunk at
  the next race start. Track items are activated while the race is live; choosing a racer portrait
  places the item just ahead in that racer's current path. Deployments still respect per-round
  spend and use caps. Every bag card has its own **Use** control and a trash control; discarding
  permanently frees the slot without refunding the purchase.
- Every tonic has a deterministic, seed-driven activation chance; none guarantees an outcome.
  Every activated potion in a same-target stack applies another adjustment, though later copies
  get progressively weaker. An activated guard tonic lowers the chance that trip or confusion
  tonics take hold.
- Growth tonic makes a racer larger, sturdier, slower, and easier to collide with; shrink tonic
  makes them smaller, quicker, and more fragile; transformation tonic borrows another racer's
  identity, sprite, and a bounded blend of their stats. If the transformed body crosses first,
  the borrowed identity receives the official win and its bettors are paid. All three may fizzle.
- Fireproof, Nitro, Recovery, Ghost, Second Wind, and Phoenix drinks add one-use protection,
  burst-and-fatigue speed, rapid incident recovery, phasing, trailing-only catch-up, and one
  revival. Like every tonic, each has a deterministic activation chance and can fizzle.
- Tonic drinks and track props use locally stored pixel art and are grouped as positive, negative,
  neutral, or live in the shop, with each group ordered from lowest to highest price. Durable track
  props—Banana, Pothole, Oil Slick, Boost Pad, Detour Sign, Speed Bump, Rock Wall, and
  Springboard—can affect every racer once. Detour racers either change lanes or take a two-second
  slowdown. A Glass Door remains through failed attempts and disappears only when a racer breaks
  through it. Boxing Glove, Stop Sign, Magnet Mine, and Portal Gate disappear after their first
  activation. Roomba Vacuum slowly patrols toward hazards and vacuums up multiple hazards, but
  trips each racer that collides with it. Boost Pad now launches racers about 7% of the track and
  grants roughly +65% speed for three seconds.
- **Prestige seats** in the grandstand persist until another player outbids you. Each new
  betting round resets displayed prices to the seat's base cost while keeping the current owner.
  Every takeover during a round raises the next price by exactly $5. Evicted owners receive a 50%
  refund of what they paid for that seat. One prestige seat per player globally; switching seats
  vacates your old seat immediately.
  Depending on the seat, ownership adds 5%, 10%, 15%, or 25% to the profit from every winning bet
  while you hold it. Seats require available balance and range from $40 to $150 at round open.
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
- **Hall of Fame** tracks top balances and wins; the **Oops Ledger** ranks all-time net betting
  losses from settled tickets (including seat payout bonuses). Negative balances are no longer allowed.
- The public **House Account** derives its operating winnings from the canonical player ledger:
  stakes and sales are income, while payouts, refunds, and Track Medic bailouts are expenses.
  Opening grants and admin adjustments are disclosed separately.
- Account panels show settled betting wins, losses, stakes, returns, and net results. Racer cards
  and dossiers show starts, official wins, losses, DNFs, win rate, current odds, and recent rounds.
- After 50 settled rounds, newly opened lineups blend lifetime official win rates with simulation
  odds; racers with fewer than 50 starts still open on pure simulation odds. Frozen round odds never
  change retroactively.
- The betting sheet keeps the live lineup on one viewport. Its toolbar tracks player, money,
  round, and clock; Shop, Inventory, Boards, Account, and recent activity live in the menu.
- Bets, items, and prestige seats all require available balance; stakes are capped per round.
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
