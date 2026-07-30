from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.racing.models import (
    ItemDefinition,
    Racer,
    RoomSettings,
    SpectatorSeatDefinition,
    UpgradeDefinition,
)

CANONICAL_SLUGS = frozenset({"bonejamin", "spore-score", "gob-smack", "blinky"})

RACERS: tuple[dict[str, Any], ...] = (
    {
        "name": "Bonejamin",
        "slug": "bonejamin",
        "sprite_key": "skeleton",
        "color": "#e8e0c9",
        "tagline": "Calcium-forward, latency-backward.",
        "backstory": (
            "Bonejamin was assembled from spare parts in a university robotics lab that "
            "lost its NSF grant and pivoted to necromancy. He races on pure spite and "
            "a firmware patch that maps 'pain' to 'motivation.'"
        ),
        "base_speed": 0.94,
        "resilience": 0.72,
        "recovery": 0.48,
        "aggression": 0.62,
        "chaos": 0.55,
        "default_odds": Decimal("4.40"),
        "sort_order": 10,
        "active": True,
    },
    {
        "name": "Spore Score",
        "slug": "spore-score",
        "sprite_key": "mushroom",
        "color": "#f15b5d",
        "tagline": "Mycelium WAN optimization.",
        "backstory": (
            "Spore Score colonized a discarded Raspberry Pi cluster and now treats every "
            "race as a distributed systems benchmark. Odds improve when humidity exceeds "
            "60% and someone nearby is brewing coffee."
        ),
        "base_speed": 1.05,
        "resilience": 0.42,
        "recovery": 0.75,
        "aggression": 0.28,
        "chaos": 0.70,
        "default_odds": Decimal("4.10"),
        "sort_order": 20,
        "active": True,
    },
    {
        "name": "Gob Smack",
        "slug": "gob-smack",
        "sprite_key": "goblin",
        "color": "#88c057",
        "tagline": "Aggro-driven sprint heuristic.",
        "backstory": (
            "Gob Smack learned racing from speedrunning glitch categories nobody else "
            "would touch. His coach is a PDF titled 'Exploits in Linear Algebra' and "
            "his pre-race ritual is yelling at the starting horn."
        ),
        "base_speed": 1.02,
        "resilience": 0.58,
        "recovery": 0.57,
        "aggression": 0.90,
        "chaos": 0.78,
        "default_odds": Decimal("4.25"),
        "sort_order": 30,
        "active": True,
    },
    {
        "name": "Blinky",
        "slug": "blinky",
        "sprite_key": "flying-eye",
        "color": "#c884f4",
        "tagline": "Always watching, rarely blinking.",
        "backstory": (
            "Blinky is a surveillance orb that achieved sentience during a GDPR audit. "
            "It predicts finish order using telemetry from every phone in the venue and "
            "still refuses to explain why it needs three lenses."
        ),
        "base_speed": 1.12,
        "resilience": 0.30,
        "recovery": 0.80,
        "aggression": 0.50,
        "chaos": 0.86,
        "default_odds": Decimal("3.80"),
        "sort_order": 40,
        "active": True,
    },
    {
        "name": "Sir Chomps",
        "slug": "sir-chomps",
        "sprite_key": "mimic",
        "color": "#c78a4d",
        "base_speed": 0.82,
        "resilience": 0.90,
        "recovery": 0.36,
        "aggression": 0.96,
        "chaos": 0.68,
        "default_odds": Decimal("5.20"),
        "sort_order": 50,
        "active": False,
    },
    {
        "name": "Rat Damon",
        "slug": "rat-damon",
        "sprite_key": "rat",
        "color": "#b7a6a1",
        "base_speed": 1.16,
        "resilience": 0.25,
        "recovery": 0.92,
        "aggression": 0.34,
        "chaos": 0.48,
        "default_odds": Decimal("3.60"),
        "sort_order": 60,
        "active": False,
    },
    {
        "name": "Gloop",
        "slug": "gloop",
        "sprite_key": "slime",
        "color": "#54d6a1",
        "base_speed": 0.88,
        "resilience": 0.95,
        "recovery": 0.44,
        "aggression": 0.40,
        "chaos": 0.60,
        "default_odds": Decimal("4.90"),
        "sort_order": 70,
        "active": False,
    },
    {
        "name": "Batthew",
        "slug": "batthew",
        "sprite_key": "bat",
        "color": "#6574cd",
        "base_speed": 1.09,
        "resilience": 0.38,
        "recovery": 0.84,
        "aggression": 0.72,
        "chaos": 0.92,
        "default_odds": Decimal("4.00"),
        "sort_order": 80,
        "active": False,
    },
)

ITEMS: tuple[dict[str, Any], ...] = (
    {
        "slug": "quantum-quencher",
        "name": "Quantum Quencher",
        "description": "Gives the racer 28% more speed for the whole race.",
        "icon": "⚡",
        "color": "#5ad1ff",
        "kind": ItemDefinition.Kind.SPEED_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 800,
        "effect_strength": 0.28,
        "sort_order": 10,
    },
    {
        "slug": "rubber-bone-broth",
        "name": "Rubber-Bone Broth",
        "description": (
            "Makes the racer tougher, quicker to recover, and better at resisting bad potions."
        ),
        "icon": "🛡",
        "color": "#e8e0c9",
        "kind": ItemDefinition.Kind.GUARD_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 800,
        "effect_strength": 0.50,
        "sort_order": 20,
    },
    {
        "slug": "potion-of-minor-inconvenience",
        "name": "Potion of Minor Inconvenience",
        "description": "Makes the racer fall and crawl until they get back up.",
        "icon": "🧪",
        "color": "#ff8f5a",
        "kind": ItemDefinition.Kind.TRIP_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 640,
        "effect_strength": 0.60,
        "sort_order": 30,
    },
    {
        "slug": "null-pointer-nectar",
        "name": "Null Pointer Nectar",
        "description": "Makes the racer run backward until they turn around.",
        "icon": "🌀",
        "color": "#c884f4",
        "kind": ItemDefinition.Kind.CONFUSION_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 800,
        "effect_strength": 0.55,
        "sort_order": 40,
    },
    {
        "slug": "maximum-ooze",
        "name": "Maximum Ooze",
        "description": (
            "Makes the racer bigger and tougher, but slightly slower and easier to hit."
        ),
        "icon": "⬆️",
        "color": "#f5a340",
        "kind": ItemDefinition.Kind.GROWTH_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 800,
        "effect_strength": 0.55,
        "sort_order": 45,
    },
    {
        "slug": "fun-size-fizz",
        "name": "Fun-Size Fizz",
        "description": "Makes the racer smaller and slightly faster, but less tough.",
        "icon": "⬇️",
        "color": "#73d9d0",
        "kind": ItemDefinition.Kind.SHRINK_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 640,
        "effect_strength": 0.52,
        "sort_order": 46,
    },
    {
        "slug": "identity-crisis-cordial",
        "name": "Identity Crisis Cordial",
        "description": (
            "Copies part of a rival's stats and name. If this racer wins, the copied rival gets "
            "the result."
        ),
        "icon": "🎭",
        "color": "#ef79c5",
        "kind": ItemDefinition.Kind.TRANSFORM_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 4_800,
        "effect_strength": 0.65,
        "sort_order": 47,
    },
    {
        "slug": "fireproof-tonic",
        "name": "Fireproof Tonic",
        "description": "Protects the racer from the first fire-pit hit.",
        "icon": "🔥",
        "color": "#ff9040",
        "kind": ItemDefinition.Kind.FIREPROOF_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 2_000,
        "effect_strength": 1.0,
        "sort_order": 50,
    },
    {
        "slug": "nitro-serum",
        "name": "Nitro Serum",
        "description": "Gives a strong burst of speed at the start, then a short slowdown.",
        "icon": "🚀",
        "color": "#fff040",
        "kind": ItemDefinition.Kind.NITRO_SERUM,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 800,
        "effect_strength": 0.70,
        "sort_order": 51,
    },
    {
        "slug": "recovery-brew",
        "name": "Recovery Brew",
        "description": "Greatly shortens the next fall or backward-running mishap.",
        "icon": "💗",
        "color": "#ff90c0",
        "kind": ItemDefinition.Kind.RECOVERY_BREW,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 640,
        "effect_strength": 0.82,
        "sort_order": 52,
    },
    {
        "slug": "ghost-draught",
        "name": "Ghost Draught",
        "description": "Lets the racer pass through the next obstacle or racer collision.",
        "icon": "👻",
        "color": "#d0e8ff",
        "kind": ItemDefinition.Kind.GHOST_DRAUGHT,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 1_600,
        "effect_strength": 1.0,
        "sort_order": 53,
    },
    {
        "slug": "second-wind",
        "name": "Second Wind",
        "description": "Gives the racer a strong speed boost when they fall behind.",
        "icon": "💨",
        "color": "#7dff9a",
        "kind": ItemDefinition.Kind.SECOND_WIND,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 800,
        "effect_strength": 0.75,
        "sort_order": 54,
    },
    {
        "slug": "phoenix-flask",
        "name": "Phoenix Flask",
        "description": "Brings the racer back once after they are knocked out or destroyed.",
        "icon": "🐦",
        "color": "#ffb040",
        "kind": ItemDefinition.Kind.PHOENIX_FLASK,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 4_800,
        "effect_strength": 1.0,
        "sort_order": 55,
    },
    {
        "slug": "banana-of-binding",
        "name": "Banana of Binding",
        "description": "Trips every racer who touches it once. Stays on the track.",
        "icon": "🍌",
        "color": "#f6c453",
        "kind": ItemDefinition.Kind.BANANA,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 1_200,
        "effect_strength": 0.78,
        "sort_order": 100,
    },
    {
        "slug": "portable-pothole",
        "name": "Portable Pothole",
        "description": (
            "Causes a hard fall and may knock racers out. Stays on the track; each racer can hit "
            "it once."
        ),
        "icon": "🕳",
        "color": "#6b6b6b",
        "kind": ItemDefinition.Kind.POTHOLE,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 2_000,
        "effect_strength": 0.92,
        "sort_order": 110,
    },
    {
        "slug": "open-source-oil-slick",
        "name": "Open-Source Oil Slick",
        "description": (
            "Spins racers around and makes them run backward. Stays on the track; each racer can "
            "hit it once."
        ),
        "icon": "🛢",
        "color": "#3f4a56",
        "kind": ItemDefinition.Kind.OIL_SLICK,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 1_600,
        "effect_strength": 0.82,
        "sort_order": 120,
    },
    {
        "slug": "questionable-boost-pad",
        "name": "Questionable Boost Pad",
        "description": (
            "Launches racers about 10% forward and gives 73% more speed for 3 seconds. Stays on "
            "the track."
        ),
        "icon": "⏩",
        "color": "#45d483",
        "kind": ItemDefinition.Kind.BOOST_PAD,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 2_400,
        "effect_strength": 0.75,
        "sort_order": 130,
    },
    {
        "slug": "spring-loaded-boxing-glove",
        "name": "Spring-Loaded Boxing Glove",
        "description": (
            "Punches the first racer backward toward the nearest fire pit, then disappears."
        ),
        "icon": "🥊",
        "color": "#ef5b5b",
        "kind": ItemDefinition.Kind.BOXING_GLOVE,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 6_400,
        "effect_strength": 0.88,
        "sort_order": 140,
    },
    {
        "slug": "detour-sign",
        "name": "Detour Sign",
        "description": "Racers must change lanes or slow down for 2 seconds. Stays on the track.",
        "icon": "↪",
        "color": "#f38c2c",
        "kind": ItemDefinition.Kind.DETOUR_SIGN,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 1_600,
        "effect_strength": 0.68,
        "sort_order": 150,
    },
    {
        "slug": "speed-bump",
        "name": "Speed Bump",
        "description": "Briefly slows every racer that crosses it without making them fall.",
        "icon": "▬",
        "color": "#c4a02c",
        "kind": ItemDefinition.Kind.SPEED_BUMP,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 1_200,
        "effect_strength": 0.68,
        "sort_order": 160,
    },
    {
        "slug": "stop-sign",
        "name": "Stop Sign",
        "description": "Briefly stops the first racer that reaches it, then disappears.",
        "icon": "🛑",
        "color": "#c42c2c",
        "kind": ItemDefinition.Kind.STOP_SIGN,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 1_600,
        "effect_strength": 0.78,
        "sort_order": 170,
    },
    {
        "slug": "glass-door",
        "name": "Glass Door",
        "description": (
            "Blocks racers until one breaks through. Failed attempts pause and switch lanes."
        ),
        "icon": "▣",
        "color": "#c8e8ff",
        "kind": ItemDefinition.Kind.GLASS_DOOR,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 2_000,
        "effect_strength": 0.78,
        "sort_order": 180,
    },
    {
        "slug": "rock-wall",
        "name": "Rock Wall",
        "description": (
            "Forces every racer that reaches it to slow down and change lanes. "
            "Stays on the track."
        ),
        "icon": "🧱",
        "color": "#888890",
        "kind": ItemDefinition.Kind.ROCK_WALL,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 2_400,
        "effect_strength": 0.82,
        "sort_order": 190,
    },
    {
        "slug": "roomba-vacuum",
        "name": "Roomba Vacuum",
        "description": "Slowly chases and removes hazards. Racers trip if they hit it.",
        "icon": "◉",
        "color": "#687078",
        "kind": ItemDefinition.Kind.ROOMBA_VACUUM,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 1_600,
        "effect_strength": 1.0,
        "sort_order": 200,
    },
    {
        "slug": "springboard",
        "name": "Springboard",
        "description": (
            "Launches every racer forward, but they may stumble when they land. Stays on the track."
        ),
        "icon": "⤴",
        "color": "#1c6b45",
        "kind": ItemDefinition.Kind.SPRINGBOARD,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 2_000,
        "effect_strength": 0.78,
        "sort_order": 210,
    },
    {
        "slug": "magnet-mine",
        "name": "Magnet Mine",
        "description": "Pulls nearby racers into one lane to cause collisions, then disappears.",
        "icon": "🧲",
        "color": "#4078ff",
        "kind": ItemDefinition.Kind.MAGNET_MINE,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 2_400,
        "effect_strength": 0.88,
        "sort_order": 220,
    },
    {
        "slug": "portal-gate",
        "name": "Portal Gate",
        "description": (
            "Teleports the first racer to a random spot farther ahead, then disappears."
        ),
        "icon": "◎",
        "color": "#7840c4",
        "kind": ItemDefinition.Kind.PORTAL_GATE,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 4_800,
        "effect_strength": 0.90,
        "sort_order": 230,
    },
)

UPGRADES: tuple[dict[str, Any], ...] = (
    {
        "slug": "expanded-pockets",
        "name": "Expanded Pockets",
        "description": "Permanently raises your bag to six item slots.",
        "kind": UpgradeDefinition.Kind.INVENTORY_CAPACITY,
        "inventory_capacity": 6,
        "price_cents": 15_000,
        "sort_order": 10,
    },
    {
        "slug": "deep-pockets",
        "name": "Deep Pockets",
        "description": "Permanently raises your bag to eight item slots.",
        "kind": UpgradeDefinition.Kind.INVENTORY_CAPACITY,
        "inventory_capacity": 8,
        "price_cents": 35_000,
        "prerequisite_slug": "expanded-pockets",
        "sort_order": 20,
    },
)

SEATS: tuple[dict[str, Any], ...] = (
    {
        "slug": "finish-barrel",
        "name": "Finish Barrel",
        "description": "Adds 5% to winning profit for every round you hold this seat.",
        "sprite_key": "rat",
        "color": "#c78a4d",
        "price_cents": 4_000,
        "payout_bonus_bps": 500,
        "sort_order": 10,
    },
    {
        "slug": "goblin-pit-rail",
        "name": "Goblin Pit Rail",
        "description": "Adds 10% to winning profit for every round you hold this seat.",
        "sprite_key": "slime",
        "color": "#88c057",
        "price_cents": 6_000,
        "payout_bonus_bps": 1_000,
        "sort_order": 20,
    },
    {
        "slug": "arcane-press-box",
        "name": "Arcane Press Box",
        "description": "Adds 15% to winning profit for every round you hold this seat.",
        "sprite_key": "bat",
        "color": "#6574cd",
        "price_cents": 8_500,
        "payout_bonus_bps": 1_500,
        "sort_order": 30,
    },
    {
        "slug": "throne-of-questionable-authority",
        "name": "Throne of Questionable Authority",
        "description": "Adds 25% to winning profit for every round you hold this seat.",
        "sprite_key": "mimic",
        "color": "#f6c453",
        "price_cents": 15_000,
        "payout_bonus_bps": 2_500,
        "sort_order": 40,
    },
)


class Command(BaseCommand):
    help = "Create the default room settings and fantasy racer roster."

    def handle(self, *args: object, **options: object) -> None:
        room = RoomSettings.load()
        room.runner_count = 4
        if settings.RACE_E2E_FAST:
            room.betting_seconds = 12
            room.lineup_seconds = 1
            room.race_seconds = 30
            room.results_seconds = 3
            room.opening_balance_cents = 50_000
            room.save(
                update_fields=[
                    "runner_count",
                    "betting_seconds",
                    "lineup_seconds",
                    "race_seconds",
                    "results_seconds",
                    "opening_balance_cents",
                    "updated_at",
                ]
            )
        else:
            room.save(update_fields=["runner_count", "updated_at"])

        racer_count = 0
        for racer_data in RACERS:
            slug = racer_data["slug"]
            defaults = dict(racer_data)
            _racer, created = Racer.objects.update_or_create(slug=slug, defaults=defaults)
            racer_count += int(created)

        Racer.objects.exclude(slug__in=CANONICAL_SLUGS).update(active=False)

        item_count = 0
        for item_data in ITEMS:
            slug = item_data["slug"]
            defaults = dict(item_data)
            _item, created = ItemDefinition.objects.update_or_create(slug=slug, defaults=defaults)
            item_count += int(created)

        seat_count = 0
        for seat_data in SEATS:
            slug = seat_data["slug"]
            defaults = dict(seat_data)
            _seat, created = SpectatorSeatDefinition.objects.update_or_create(
                slug=slug,
                defaults=defaults,
            )
            seat_count += int(created)

        upgrade_count = 0
        prerequisite_by_slug: dict[str, UpgradeDefinition] = {}
        for upgrade_data in UPGRADES:
            slug = upgrade_data["slug"]
            defaults = {
                key: value for key, value in upgrade_data.items() if key != "prerequisite_slug"
            }
            defaults["prerequisite"] = None
            upgrade, created = UpgradeDefinition.objects.update_or_create(
                slug=slug,
                defaults=defaults,
            )
            prerequisite_by_slug[slug] = upgrade
            upgrade_count += int(created)

        for upgrade_data in UPGRADES:
            prerequisite_slug = upgrade_data.get("prerequisite_slug")
            if prerequisite_slug is None:
                continue
            upgrade = prerequisite_by_slug[upgrade_data["slug"]]
            prerequisite = prerequisite_by_slug[prerequisite_slug]
            if upgrade.prerequisite_id != prerequisite.pk:
                upgrade.prerequisite = prerequisite
                upgrade.save(update_fields=["prerequisite"])

        self.stdout.write(
            self.style.SUCCESS(
                "Game data ready "
                f"({racer_count} racers created, {item_count} items, "
                f"{seat_count} seats, {upgrade_count} upgrades)."
            )
        )
