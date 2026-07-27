from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.racing.models import ItemDefinition, Racer, RoomSettings, SpectatorSeatDefinition

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
        "description": "67% proc chance. On proc: +18% base speed for the whole race.",
        "icon": "⚡",
        "color": "#5ad1ff",
        "kind": ItemDefinition.Kind.SPEED_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 2_000,
        "effect_strength": 0.18,
        "sort_order": 10,
    },
    {
        "slug": "rubber-bone-broth",
        "name": "Rubber-Bone Broth",
        "description": (
            "76% proc chance. On proc: +35% resilience, +18% recovery, less chaos, "
            "and 30% better resistance to hostile potions."
        ),
        "icon": "🛡",
        "color": "#e8e0c9",
        "kind": ItemDefinition.Kind.GUARD_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 2_200,
        "effect_strength": 0.35,
        "sort_order": 20,
    },
    {
        "slug": "potion-of-minor-inconvenience",
        "name": "Potion of Minor Inconvenience",
        "description": (
            "81% base proc chance, reduced by resilience and Guard. "
            "On proc: target falls and must crawl until Get Up."
        ),
        "icon": "🧪",
        "color": "#ff8f5a",
        "kind": ItemDefinition.Kind.TRIP_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 2_200,
        "effect_strength": 0.45,
        "sort_order": 30,
    },
    {
        "slug": "null-pointer-nectar",
        "name": "Null Pointer Nectar",
        "description": (
            "78% base proc chance, reduced by resilience and Guard. "
            "On proc: target runs backward until Turn Around."
        ),
        "icon": "🌀",
        "color": "#c884f4",
        "kind": ItemDefinition.Kind.CONFUSION_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 2_400,
        "effect_strength": 0.40,
        "sort_order": 40,
    },
    {
        "slug": "maximum-ooze",
        "name": "Maximum Ooze",
        "description": (
            "79% proc chance. On proc: 32% larger, about 5% slower, tougher, "
            "and easier to collide with."
        ),
        "icon": "⬆️",
        "color": "#f5a340",
        "kind": ItemDefinition.Kind.GROWTH_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 2_400,
        "effect_strength": 0.42,
        "sort_order": 45,
    },
    {
        "slug": "fun-size-fizz",
        "name": "Fun-Size Fizz",
        "description": (
            "78% proc chance. On proc: 28% smaller, about 4% faster, harder to hit, "
            "but less resilient."
        ),
        "icon": "⬇️",
        "color": "#73d9d0",
        "kind": ItemDefinition.Kind.SHRINK_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 2_200,
        "effect_strength": 0.40,
        "sort_order": 46,
    },
    {
        "slug": "identity-crisis-cordial",
        "name": "Identity Crisis Cordial",
        "description": (
            "82% proc chance. Borrows a random rival's identity and 45% of their stats. "
            "If this body wins, the borrowed identity gets the result."
        ),
        "icon": "🎭",
        "color": "#ef79c5",
        "kind": ItemDefinition.Kind.TRANSFORM_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 3_000,
        "effect_strength": 0.50,
        "sort_order": 47,
    },
    {
        "slug": "banana-of-binding",
        "name": "Banana of Binding",
        "description": (
            "LIVE: drops 8% of the track ahead in the selected racer's path. "
            "It stays put; each racer that touches it once falls and starts crawling."
        ),
        "icon": "🍌",
        "color": "#f6c453",
        "kind": ItemDefinition.Kind.BANANA,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 5_000,
        "effect_strength": 0.65,
        "sort_order": 50,
    },
    {
        "slug": "portable-pothole",
        "name": "Portable Pothole",
        "description": (
            "LIVE: stays ahead of the selected racer. Each racer can hit it once, taking "
            "a heavy fall with more knockout risk than a banana."
        ),
        "icon": "🕳",
        "color": "#6b6b6b",
        "kind": ItemDefinition.Kind.POTHOLE,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 6_500,
        "effect_strength": 0.85,
        "sort_order": 60,
    },
    {
        "slug": "open-source-oil-slick",
        "name": "Open-Source Oil Slick",
        "description": (
            "LIVE: stays ahead of the selected racer. Each racer can trigger it once, "
            "spinning around and running backward until Turn Around."
        ),
        "icon": "🛢",
        "color": "#3f4a56",
        "kind": ItemDefinition.Kind.OIL_SLICK,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 6_000,
        "effect_strength": 0.70,
        "sort_order": 70,
    },
    {
        "slug": "questionable-boost-pad",
        "name": "Questionable Boost Pad",
        "description": (
            "LIVE: stays ahead of the selected racer. Each racer can trigger it once to jump "
            "4% of the track and gain about +18% speed for 1.5 seconds."
        ),
        "icon": "⏩",
        "color": "#45d483",
        "kind": ItemDefinition.Kind.BOOST_PAD,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 7_000,
        "effect_strength": 0.60,
        "sort_order": 80,
    },
    {
        "slug": "spring-loaded-boxing-glove",
        "name": "Spring-Loaded Boxing Glove",
        "description": (
            "LIVE: stays ahead of the selected racer. Each racer can trigger it once and get "
            "punched backward toward the nearest fire pit."
        ),
        "icon": "🥊",
        "color": "#ef5b5b",
        "kind": ItemDefinition.Kind.BOXING_GLOVE,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 8_000,
        "effect_strength": 0.75,
        "sort_order": 90,
    },
)

SEATS: tuple[dict[str, Any], ...] = (
    {
        "slug": "finish-barrel",
        "name": "Finish Barrel",
        "description": "Adds 5% to the profit from every winning bet this round.",
        "sprite_key": "rat",
        "color": "#c78a4d",
        "price_cents": 4_000,
        "payout_bonus_bps": 500,
        "sort_order": 10,
    },
    {
        "slug": "goblin-pit-rail",
        "name": "Goblin Pit Rail",
        "description": "Adds 10% to the profit from every winning bet this round.",
        "sprite_key": "slime",
        "color": "#88c057",
        "price_cents": 6_000,
        "payout_bonus_bps": 1_000,
        "sort_order": 20,
    },
    {
        "slug": "arcane-press-box",
        "name": "Arcane Press Box",
        "description": "Adds 15% to the profit from every winning bet this round.",
        "sprite_key": "bat",
        "color": "#6574cd",
        "price_cents": 8_500,
        "payout_bonus_bps": 1_500,
        "sort_order": 30,
    },
    {
        "slug": "throne-of-questionable-authority",
        "name": "Throne of Questionable Authority",
        "description": "Adds 25% to the profit from every winning bet this round.",
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
            room.race_seconds = 6
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

        self.stdout.write(
            self.style.SUCCESS(
                "Game data ready "
                f"({racer_count} racers created, {item_count} items, {seat_count} seats)."
            )
        )
