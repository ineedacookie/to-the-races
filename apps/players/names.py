from __future__ import annotations

import secrets

ADJECTIVES = (
    "Bouncy",
    "Brave",
    "Breezy",
    "Cheeky",
    "Cosmic",
    "Dizzy",
    "Fizzy",
    "Jolly",
    "Lucky",
    "Mighty",
    "Muddy",
    "Nimble",
    "Rowdy",
    "Sleepy",
    "Sneaky",
    "Sparkly",
    "Spicy",
    "Turbo",
    "Wobbly",
    "Zippy",
)

CREATURES = (
    "Bat",
    "Dragon",
    "Goblin",
    "Griffin",
    "Imp",
    "Mimic",
    "Moth",
    "Mushroom",
    "Newt",
    "Ogre",
    "Phoenix",
    "Rat",
    "Skeleton",
    "Slime",
    "Sprite",
    "Toad",
    "Troll",
    "Unicorn",
    "Wisp",
    "Wyvern",
)


def random_nickname() -> str:
    suffix = secrets.randbelow(90) + 10
    return f"{secrets.choice(ADJECTIVES)}-{secrets.choice(CREATURES)}-{suffix}"
