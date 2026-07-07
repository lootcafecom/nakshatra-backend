"""
Tarot card data and draw engine.

Card data and meanings are public-domain Rider-Waite material — names,
keywords, and divinatory meanings, not reproduced text from any
copyrighted guidebook. The draw itself is genuinely randomized; nothing
about the AI interpretation layer influences which cards are drawn.
"""

from __future__ import annotations
from dataclasses import dataclass
import random

MAJOR_ARCANA = [
    {"name": "The Fool", "keywords": ["new beginnings", "spontaneity", "innocence"]},
    {"name": "The Magician", "keywords": ["willpower", "resourcefulness", "manifestation"]},
    {"name": "The High Priestess", "keywords": ["intuition", "the unconscious", "mystery"]},
    {"name": "The Empress", "keywords": ["abundance", "nurturing", "fertility"]},
    {"name": "The Emperor", "keywords": ["authority", "structure", "stability"]},
    {"name": "The Hierophant", "keywords": ["tradition", "convention", "belonging"]},
    {"name": "The Lovers", "keywords": ["union", "choice", "alignment of values"]},
    {"name": "The Chariot", "keywords": ["willpower", "victory through control", "drive"]},
    {"name": "Strength", "keywords": ["quiet courage", "patience", "inner resolve"]},
    {"name": "The Hermit", "keywords": ["introspection", "solitude", "inner guidance"]},
    {"name": "Wheel of Fortune", "keywords": ["cycles", "fate", "turning points"]},
    {"name": "Justice", "keywords": ["fairness", "cause and effect", "truth"]},
    {"name": "The Hanged Man", "keywords": ["surrender", "a new perspective", "pause"]},
    {"name": "Death", "keywords": ["endings", "transformation", "release"]},
    {"name": "Temperance", "keywords": ["balance", "moderation", "patience"]},
    {"name": "The Devil", "keywords": ["attachment", "restriction", "shadow self"]},
    {"name": "The Tower", "keywords": ["sudden upheaval", "revelation", "awakening"]},
    {"name": "The Star", "keywords": ["hope", "renewal", "quiet faith"]},
    {"name": "The Moon", "keywords": ["uncertainty", "the subconscious", "illusion"]},
    {"name": "The Sun", "keywords": ["clarity", "vitality", "success"]},
    {"name": "Judgement", "keywords": ["reckoning", "awakening", "reflection"]},
    {"name": "The World", "keywords": ["completion", "wholeness", "arrival"]},
]

SUITS = ["Cups", "Pentacles", "Swords", "Wands"]
SUIT_THEME = {
    "Cups": "emotion and relationships",
    "Pentacles": "material life and resources",
    "Swords": "thought and conflict",
    "Wands": "ambition and creative energy",
}
RANKS = ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven",
         "Eight", "Nine", "Ten", "Page", "Knight", "Queen", "King"]


def _build_minor_arcana() -> list[dict]:
    cards = []
    for suit in SUITS:
        for rank in RANKS:
            cards.append({
                "name": f"{rank} of {suit}",
                "keywords": [SUIT_THEME[suit]],
            })
    return cards


FULL_DECK = MAJOR_ARCANA + _build_minor_arcana()
assert len(FULL_DECK) == 78, "Tarot deck must contain exactly 78 cards"


@dataclass
class DrawnCard:
    name: str
    keywords: list[str]
    reversed: bool
    position: str   # e.g. "Past", "Present", "Future"


def draw_three_card_spread(rng: random.Random | None = None) -> list[DrawnCard]:
    """A genuine random draw, no two cards repeated, each independently
    upright or reversed. Pass an rng for reproducible tests; omit it for
    real randomness in production."""
    rng = rng or random.Random()
    deck_copy = list(FULL_DECK)
    rng.shuffle(deck_copy)
    drawn_raw = deck_copy[:3]
    positions = ["Past", "Present", "Future"]
    return [
        DrawnCard(
            name=card["name"],
            keywords=card["keywords"],
            reversed=rng.random() < 0.5,
            position=positions[i],
        )
        for i, card in enumerate(drawn_raw)
    ]


def draw_single_card(rng: random.Random | None = None) -> list[DrawnCard]:
    """Single daily focus card."""
    rng = rng or random.Random()
    deck_copy = list(FULL_DECK)
    rng.shuffle(deck_copy)
    card = deck_copy[0]
    return [DrawnCard(name=card["name"], keywords=card["keywords"],
                      reversed=rng.random() < 0.5, position="Daily Focus")]


def draw_five_card_spread(rng: random.Random | None = None) -> list[DrawnCard]:
    """5-card situation spread: Situation, Action, Embrace, Release, Outcome."""
    rng = rng or random.Random()
    deck_copy = list(FULL_DECK)
    rng.shuffle(deck_copy)
    positions = ["Situation", "Action", "What to Embrace", "What to Release", "Outcome"]
    return [
        DrawnCard(name=deck_copy[i]["name"], keywords=deck_copy[i]["keywords"],
                  reversed=rng.random() < 0.5, position=positions[i])
        for i in range(5)
    ]


def draw_celtic_cross(rng: random.Random | None = None) -> list[DrawnCard]:
    """10-card Celtic Cross spread — the most comprehensive traditional spread."""
    rng = rng or random.Random()
    deck_copy = list(FULL_DECK)
    rng.shuffle(deck_copy)
    positions = [
        "Present (The Heart)", "Challenge (Crossing)", "Foundation (Root)",
        "Recent Past", "Possible Future", "Near Future",
        "Your Attitude", "Environment", "Hopes & Fears", "Final Outcome",
    ]
    return [
        DrawnCard(name=deck_copy[i]["name"], keywords=deck_copy[i]["keywords"],
                  reversed=rng.random() < 0.5, position=positions[i])
        for i in range(10)
    ]


SPREAD_FUNCTIONS = {
    "single": draw_single_card,
    "three": draw_three_card_spread,
    "five": draw_five_card_spread,
    "celtic": draw_celtic_cross,
}
