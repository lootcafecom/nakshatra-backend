"""
AI interpretation layer.

Per the master plan's core rule: the model never calculates anything in
this module. Every prompt receives already-computed structured data
(from vedic.py, numerology.py, tarot.py, vastu.py) and is instructed
only to explain what it means. This file builds those prompts; the
actual API call lives in main.py.
"""

from __future__ import annotations
from app.vedic import BirthChart
from app.numerology import NumerologyProfile
from app.tarot import DrawnCard
from app.vastu import VastuProfile

LANGUAGE_NAMES = {
    "hi": "Hindi", "ta": "Tamil", "te": "Telugu", "kn": "Kannada",
    "ml": "Malayalam", "bn": "Bengali", "mr": "Marathi", "en": "English",
    "gu": "Gujarati",
}

BASE_SYSTEM_PROMPT = """You are a knowledgeable astrology guide writing for Nakshatra, \
a platform that combines Vedic astrology, numerology, tarot, and Vastu Shastra.

Strict rules:
- You are given already-calculated data (planetary positions, numbers, cards, \
directions). Never recalculate, second-guess, or contradict this data — only \
interpret what it means for the person.
- Ground interpretations in classical sources where relevant (Brihat Parashara \
Hora Shastra for Vedic astrology, the Rider-Waite tradition for tarot, the \
Vastu Shastra and Brihat Samhita for directional guidance), naming the source \
naturally rather than as a citation.
- Write warmly and specifically to this person — never generic sun-sign-column \
language.
- Do not add disclaimers about being an AI or about astrology's scientific status.
- Write your entire response in {language_name}. Keep proper nouns that are \
Sanskrit astrological terms (Rashi, Nakshatra, Dasha, the planet names, etc.) \
in their original form even when writing in another language — only the \
surrounding explanation should be translated.
"""


def _lang_name(language_code: str) -> str:
    return LANGUAGE_NAMES.get(language_code, "English")


def build_vedic_prompt(name: str, chart: BirthChart, language_code: str) -> tuple[str, str]:
    system = BASE_SYSTEM_PROMPT.format(language_name=_lang_name(language_code))

    planet_lines = "\n".join(
        f"- {p.name}: {p.sign} {p.sign_degree}°, house {p.house}, "
        f"Nakshatra {p.nakshatra} pada {p.nakshatra_pada}"
        f"{' (retrograde)' if p.retrograde else ''}"
        for p in chart.planets
    )

    user = f"""Person: {name}

Calculated birth chart data (Lahiri ayanamsha, sidereal):
- Ascendant (Lagna): {chart.ascendant_sign} at {chart.ascendant_degree}°
- Moon Nakshatra: {chart.moon_nakshatra}, pada {chart.moon_nakshatra_pada}
- Current Vimshottari Dasha: {chart.current_dasha}

Planetary positions:
{planet_lines}

Using only this data, write a reading covering:
1. What the Ascendant and Moon Nakshatra together suggest about this person's nature
2. The most significant planetary placement and what it means for them
3. What the current {chart.current_dasha} Mahadasha period suggests for this phase of life
4. One practical, grounded piece of guidance for the months ahead

Around 250 words."""

    return system, user


def build_numerology_prompt(name: str, profile: NumerologyProfile, language_code: str) -> tuple[str, str]:
    system = BASE_SYSTEM_PROMPT.format(language_name=_lang_name(language_code))

    user = f"""Person: {name}

Calculated numerology numbers (Pythagorean system, full reduction shown):
- Life Path Number: {profile.life_path.value}
- Expression Number: {profile.expression.value}
- Soul Urge Number: {profile.soul_urge.value}
- Personality Number: {profile.personality.value}
- Personal Year Number: {profile.personal_year.value}

Using only these numbers, write a reading covering:
1. What the Life Path number reveals as their core direction in life
2. How the Expression and Soul Urge numbers together describe their outer \
talents versus inner desires
3. What the current Personal Year number suggests is the theme of this year for them
4. One practical insight tying these numbers together

Around 220 words."""

    return system, user


def build_tarot_prompt(name: str, cards: list[DrawnCard], language_code: str) -> tuple[str, str]:
    system = BASE_SYSTEM_PROMPT.format(language_name=_lang_name(language_code))

    card_lines = "\n".join(
        f"- {c.position}: {c.name}{' (reversed)' if c.reversed else ' (upright)'} "
        f"— associated with {', '.join(c.keywords)}"
        for c in cards
    )

    user = f"""Person: {name}

Drawn cards (three-card Past / Present / Future spread, genuinely randomized):
{card_lines}

Using only these three cards, write a reading covering:
1. What the Past card suggests has shaped their current situation
2. What the Present card reveals about where they stand right now
3. What the Future card points toward
4. One unified message drawing the three cards together

Around 220 words."""

    return system, user


def build_vastu_prompt(name: str, vastu: VastuProfile, language_code: str) -> tuple[str, str]:
    system = BASE_SYSTEM_PROMPT.format(language_name=_lang_name(language_code))

    zone_lines = "\n".join(
        f"- {z['name']}: ruled by {z['ruling']}" for z in vastu.zones[:8]
    )

    user = f"""Person: {name}
Location: {vastu.place.place_name}
True magnetic declination at this location: {vastu.magnetic_declination}° \
(the real difference between compass north and true north here)

Vastu directional zones for this location:
{zone_lines}

Using only this data, write guidance covering:
1. Why true magnetic declination matters for getting Vastu directions \
right at this specific location
2. What each major zone (Ishanya/Northeast, Agneya/Southeast, \
Nairutya/Southwest, Vayavya/Northwest) is best used for in their home
3. One practical correction or placement tip they can apply this week

Around 220 words."""

    return system, user
