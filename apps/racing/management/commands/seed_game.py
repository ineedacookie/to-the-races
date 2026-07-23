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
        "description": "Schrödinger's electrolytes: fast until observed.",
        "icon": "⚡",
        "color": "#5ad1ff",
        "kind": ItemDefinition.Kind.SPEED_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 800,
        "effect_strength": 0.18,
        "sort_order": 10,
    },
    {
        "slug": "rubber-bone-broth",
        "name": "Rubber-Bone Broth",
        "description": "Calcium gelatin for impact absorption.",
        "icon": "🛡",
        "color": "#e8e0c9",
        "kind": ItemDefinition.Kind.GUARD_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 600,
        "effect_strength": 0.35,
        "sort_order": 20,
    },
    {
        "slug": "potion-of-minor-inconvenience",
        "name": "Potion of Minor Inconvenience",
        "description": "Guaranteed face-plant, statistically minor.",
        "icon": "🧪",
        "color": "#ff8f5a",
        "kind": ItemDefinition.Kind.TRIP_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 500,
        "effect_strength": 0.45,
        "sort_order": 30,
    },
    {
        "slug": "null-pointer-nectar",
        "name": "Null Pointer Nectar",
        "description": "Segmentation fault, but make it sporty.",
        "icon": "🌀",
        "color": "#c884f4",
        "kind": ItemDefinition.Kind.CONFUSION_TONIC,
        "target": ItemDefinition.Target.RACER,
        "price_cents": 700,
        "effect_strength": 0.40,
        "sort_order": 40,
    },
    {
        "slug": "banana-of-binding",
        "name": "Banana of Binding",
        "description": "Peel once, regret thrice.",
        "icon": "🍌",
        "color": "#f6c453",
        "kind": ItemDefinition.Kind.BANANA,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 400,
        "effect_strength": 0.65,
        "sort_order": 50,
    },
    {
        "slug": "portable-pothole",
        "name": "Portable Pothole",
        "description": "Infrastructure-as-a-trap.",
        "icon": "🕳",
        "color": "#6b6b6b",
        "kind": ItemDefinition.Kind.POTHOLE,
        "target": ItemDefinition.Target.TRACK,
        "price_cents": 600,
        "effect_strength": 0.85,
        "sort_order": 60,
    },
)

SEATS: tuple[dict[str, Any], ...] = (
    {
        "slug": "finish-barrel",
        "name": "Finish Barrel",
        "description": "Upside-down viewing with maximum splash risk.",
        "sprite_key": "rat",
        "color": "#c78a4d",
        "price_cents": 500,
        "sort_order": 10,
    },
    {
        "slug": "goblin-pit-rail",
        "name": "Goblin Pit Rail",
        "description": "Front-row heckling above the chaos trench.",
        "sprite_key": "slime",
        "color": "#88c057",
        "price_cents": 1_000,
        "sort_order": 20,
    },
    {
        "slug": "arcane-press-box",
        "name": "Arcane Press Box",
        "description": "Spell-checked commentary and free tea.",
        "sprite_key": "bat",
        "color": "#6574cd",
        "price_cents": 2_000,
        "sort_order": 30,
    },
    {
        "slug": "throne-of-questionable-authority",
        "name": "Throne of Questionable Authority",
        "description": "One seat to rule the snack table.",
        "sprite_key": "mimic",
        "color": "#f6c453",
        "price_cents": 5_000,
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
            room.save(
                update_fields=[
                    "runner_count",
                    "betting_seconds",
                    "lineup_seconds",
                    "race_seconds",
                    "results_seconds",
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
