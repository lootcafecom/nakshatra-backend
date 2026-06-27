"""
Remedy and gemstone engine.

Per the master plan's authenticity rule: which planets are "weak" in a
person's chart is determined by real calculated chart data (reusing
vedic.py's compute_birth_chart — house placement and debilitation are
checked directly against the calculated positions, not guessed). The
remedy/gemstone/mantra tables below are fixed classical data, compiled
from multiple cross-checked sources. AI's role (in interpretation.py)
is only to explain why a given remedy applies to this person's actual
calculated weak planets — it never invents the remedy data itself.
"""

from __future__ import annotations
from dataclasses import dataclass
from app.vedic import BirthChart

DUSTHANA_HOUSES = {6, 8, 12}

EXALTATION_SIGN = {
    "Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn", "Mercury": "Virgo",
    "Jupiter": "Cancer", "Venus": "Pisces", "Saturn": "Libra",
}
DEBILITATION_SIGN = {
    "Sun": "Libra", "Moon": "Scorpio", "Mars": "Cancer", "Mercury": "Pisces",
    "Jupiter": "Capricorn", "Venus": "Virgo", "Saturn": "Aries",
}


@dataclass
class GemstoneInfo:
    planet: str
    gemstone_english: str
    gemstone_sanskrit: str
    metal: str
    finger: str
    weekday: str
    substitute: str


GEMSTONES: dict[str, GemstoneInfo] = {
    "Sun": GemstoneInfo("Sun", "Ruby", "Manik", "Gold or copper", "Ring finger", "Sunday", "Red spinel or garnet"),
    "Moon": GemstoneInfo("Moon", "Pearl", "Moti", "Silver", "Little finger", "Monday", "Moonstone"),
    "Mars": GemstoneInfo("Mars", "Red Coral", "Moonga", "Gold or copper", "Ring finger", "Tuesday", "Red carnelian"),
    "Mercury": GemstoneInfo("Mercury", "Emerald", "Panna", "Gold or silver", "Little finger", "Wednesday", "Peridot"),
    "Jupiter": GemstoneInfo("Jupiter", "Yellow Sapphire", "Pukhraj", "Gold", "Index finger", "Thursday", "Citrine"),
    "Venus": GemstoneInfo("Venus", "Diamond", "Heera", "Platinum or silver", "Middle finger", "Friday", "White sapphire or zircon"),
    "Saturn": GemstoneInfo("Saturn", "Blue Sapphire", "Neelam", "Silver", "Middle finger", "Saturday", "Amethyst"),
    "Rahu": GemstoneInfo("Rahu", "Hessonite", "Gomed", "Silver", "Middle finger", "Saturday", "Smoky quartz"),
    "Ketu": GemstoneInfo("Ketu", "Cat's Eye", "Lehsunia", "Silver or gold", "Middle finger", "Thursday (evening)", "Chrysoberyl substitute"),
}


@dataclass
class MantraInfo:
    planet: str
    beej_mantra: str
    deity: str
    recitation_count: int


MANTRAS: dict[str, MantraInfo] = {
    "Sun": MantraInfo("Sun", "Om Hraam Hreem Hraum Sah Suryaya Namah", "Surya", 108),
    "Moon": MantraInfo("Moon", "Om Shraam Shreem Shraum Sah Chandraya Namah", "Chandra", 108),
    "Mars": MantraInfo("Mars", "Om Kraam Kreem Kraum Sah Bhaumaya Namah", "Mangal", 108),
    "Mercury": MantraInfo("Mercury", "Om Braam Breem Braum Sah Budhaya Namah", "Budha", 108),
    "Jupiter": MantraInfo("Jupiter", "Om Graam Greem Graum Sah Gurave Namah", "Brihaspati", 108),
    "Venus": MantraInfo("Venus", "Om Draam Dreem Draum Sah Shukraya Namah", "Shukra", 108),
    "Saturn": MantraInfo("Saturn", "Om Praam Preem Praum Sah Shanaye Namah", "Shani", 108),
    "Rahu": MantraInfo("Rahu", "Om Bhraam Bhreem Bhraum Sah Rahave Namah", "Rahu", 108),
    "Ketu": MantraInfo("Ketu", "Om Shraam Shreem Shraum Sah Ketave Namah", "Ketu", 108),
}


@dataclass
class CharityInfo:
    planet: str
    item: str
    weekday: str


CHARITY: dict[str, CharityInfo] = {
    "Sun": CharityInfo("Sun", "Wheat, jaggery, or copper items", "Sunday"),
    "Moon": CharityInfo("Moon", "White rice, milk, or white cloth", "Monday"),
    "Mars": CharityInfo("Mars", "Red lentils (masoor dal) or red cloth", "Tuesday"),
    "Mercury": CharityInfo("Mercury", "Green gram (moong dal) or green cloth", "Wednesday"),
    "Jupiter": CharityInfo("Jupiter", "Turmeric, yellow lentils, or yellow cloth", "Thursday"),
    "Venus": CharityInfo("Venus", "White sweets, rice, or white cloth", "Friday"),
    "Saturn": CharityInfo("Saturn", "Black sesame seeds or black lentils (urad dal)", "Saturday"),
    "Rahu": CharityInfo("Rahu", "Mustard oil or black/grey cloth", "Saturday"),
    "Ketu": CharityInfo("Ketu", "Black mustard seeds or a multicolored blanket", "Thursday"),
}


@dataclass
class PlanetConcern:
    planet: str
    reason: str
    house: int
    sign: str
    is_debilitated: bool
    is_in_dusthana: bool
    is_retrograde: bool
    gemstone: GemstoneInfo
    mantra: MantraInfo
    charity: CharityInfo


@dataclass
class RemedyProfile:
    name: str
    concerns: list[PlanetConcern]
    strongest_planet: str | None


def _identify_concerns(chart: BirthChart) -> list[PlanetConcern]:
    concerns: list[PlanetConcern] = []

    for p in chart.planets:
        is_debilitated = DEBILITATION_SIGN.get(p.name) == p.sign
        is_in_dusthana = p.house in DUSTHANA_HOUSES

        # Rahu and Ketu are shadow points that always move retrograde —
        # that fact is astronomically constant and not a meaningful signal
        # on its own, so it's never used here as the basis for flagging
        # them. They are classically always considered to warrant some
        # remedial attention (per Navagraha tradition), so they're
        # included regardless, but their "retrograde" status is not
        # reported as a reason — only an actual dusthana placement is.
        is_shadow_planet = p.name in ("Rahu", "Ketu")
        retrograde_is_meaningful = p.retrograde and not is_shadow_planet

        if not (is_debilitated or is_in_dusthana or retrograde_is_meaningful or is_shadow_planet):
            continue

        reasons = []
        if is_debilitated:
            reasons.append(f"debilitated in {p.sign}")
        if is_in_dusthana:
            reasons.append(f"placed in the {p.house}th house (a dusthana)")
        if retrograde_is_meaningful:
            reasons.append("retrograde")
        if is_shadow_planet and not reasons:
            reasons.append("a shadow planet classically given remedial attention regardless of placement")
        reason = " and ".join(reasons)

        concerns.append(PlanetConcern(
            planet=p.name,
            reason=reason,
            house=p.house,
            sign=p.sign,
            is_debilitated=is_debilitated,
            is_in_dusthana=is_in_dusthana,
            is_retrograde=retrograde_is_meaningful,
            gemstone=GEMSTONES[p.name],
            mantra=MANTRAS[p.name],
            charity=CHARITY[p.name],
        ))

    concerns.sort(key=lambda c: (not c.is_debilitated, not c.is_in_dusthana))
    return concerns


def _find_strongest_planet(chart: BirthChart) -> str | None:
    for p in chart.planets:
        if EXALTATION_SIGN.get(p.name) == p.sign:
            return p.name
    return None


def compute_remedy_profile(name: str, chart: BirthChart) -> RemedyProfile:
    concerns = _identify_concerns(chart)
    strongest = _find_strongest_planet(chart)
    return RemedyProfile(name=name, concerns=concerns, strongest_planet=strongest)
