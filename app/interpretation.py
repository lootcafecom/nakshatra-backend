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
from app.matching import MatchResult
from app.panchang import PanchangResult
from app.muhurta import MuhurtaScore, ACTIVITY_RULES
from app.remedy import RemedyProfile

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


def build_matching_prompt(match: MatchResult, language_code: str) -> tuple[str, str]:
    system = BASE_SYSTEM_PROMPT.format(language_name=_lang_name(language_code))

    koota_lines = "\n".join(
        f"- {k.name} ({k.score}/{k.max_points}): {k.note}" for k in match.kootas
    )

    mangal_lines = (
        f"{match.person_a_name}: Mars in house {match.mangal_dosha.person_a_mars_house}"
        f"{' (Mangal Dosha present)' if match.mangal_dosha.person_a_dosha else ' (no Mangal Dosha)'}\n"
        f"{match.person_b_name}: Mars in house {match.mangal_dosha.person_b_mars_house}"
        f"{' (Mangal Dosha present)' if match.mangal_dosha.person_b_dosha else ' (no Mangal Dosha)'}"
    )
    if match.mangal_dosha.cancellation_reason:
        mangal_lines += f"\nCancellation: {match.mangal_dosha.cancellation_reason}"

    user = f"""Compatibility reading for {match.person_a_name} and {match.person_b_name}.

Calculated Ashtakoot Guna Milan score: {match.total_score} out of {match.max_score}.
Classical verdict band: {match.verdict}

Koota-by-koota breakdown:
{koota_lines}

Nadi Dosha present: {match.nadi_dosha}
Bhakoot Dosha present: {match.bhakoot_dosha}

Mangal Dosha (Kuja Dosha) check:
{mangal_lines}

Using only this data, write a compatibility reading covering:
1. What the overall score and verdict band mean for this couple
2. Which 2-3 kootas are the strongest and what they suggest about the relationship
3. Which kootas are weakest, and if any dosha (Nadi, Bhakoot, or Mangal) is present, \
explain what it means plainly and whether it is cancelled
4. One grounded, practical closing thought — not generic reassurance, but \
specific to what this particular koota breakdown shows

Around 280 words. Be honest about weak areas rather than glossing over them, \
while keeping the tone warm and constructive."""

    return system, user


def build_activity_mapping_prompt(free_text: str) -> tuple[str, str]:
    """Maps free-text activity description to the closest known rule
    set key. This is the one place AI output determines which
    *category* of rules to apply — it never sets the score itself,
    only picks which classical rule set is the best match."""
    activity_options = "\n".join(
        f"- {key}: {rules.label}" for key, rules in ACTIVITY_RULES.items()
    )

    system = f"""You map a person's free-text description of a planned activity \
to the closest matching category from this fixed list:

{activity_options}

Respond with ONLY the category key (e.g. "marriage"), nothing else — no \
punctuation, no explanation, no preamble. If nothing matches reasonably \
well, respond with exactly: none"""

    user = f"Activity description: {free_text}"
    return system, user


def build_muhurta_single_prompt(activity_label: str, score: MuhurtaScore, language_code: str) -> tuple[str, str]:
    system = BASE_SYSTEM_PROMPT.format(language_name=_lang_name(language_code))

    user = f"""Muhurta check for {activity_label} on {score.date} ({score.weekday}).

Calculated Panchang for this date:
- Tithi: {score.panchang.tithi_name} ({'favorable' if score.tithi_favorable else 'not favorable'} for {activity_label})
- Nakshatra: {score.panchang.nakshatra} ({'favorable' if score.nakshatra_favorable else 'not favorable'})
- Weekday: {score.weekday} ({'favorable' if score.weekday_favorable else 'not favorable'})
- Karana: {score.panchang.karana_name} ({'acceptable' if score.karana_favorable else 'classically avoided'})
- Yoga: {score.panchang.yoga_name}

Overall score: {score.score} out of {score.max_score} criteria matched.
Verdict: {score.verdict}

Using only this data, explain:
1. Whether this date is genuinely well-suited for {activity_label}, and why
2. Which specific factor helps the most, and which (if any) is the weak point
3. One practical note — e.g. a time-of-day consideration like avoiding Rahu Kaal \
({score.panchang.rahu_kaal_start.strftime('%H:%M')}-{score.panchang.rahu_kaal_end.strftime('%H:%M')})

Around 180 words. Be direct about whether this date is actually good or not — \
don't soften a genuinely weak verdict."""

    return system, user


def build_muhurta_search_prompt(activity_label: str, scores: list[MuhurtaScore], language_code: str) -> tuple[str, str]:
    system = BASE_SYSTEM_PROMPT.format(language_name=_lang_name(language_code))

    date_lines = "\n".join(
        f"- {s.date} ({s.weekday}): score {s.score}/{s.max_score}, "
        f"{s.panchang.tithi_name}, {s.panchang.nakshatra} — {s.verdict}"
        for s in scores[:5]
    )

    user = f"""Searched for the best dates for {activity_label}, found these top candidates:

{date_lines}

Using only this data, write a short summary covering:
1. Which date stands out as the strongest choice, and why
2. What the next best alternative offers if the top date doesn't work logistically
3. One practical closing note about confirming the exact time-of-day window \
once a date is chosen

Around 180 words."""

    return system, user


def build_remedy_prompt(profile: RemedyProfile, language_code: str) -> tuple[str, str]:
    system = BASE_SYSTEM_PROMPT.format(language_name=_lang_name(language_code))

    if not profile.concerns:
        concern_lines = "No planets were flagged as debilitated, in a dusthana house, or otherwise classically in need of remediation."
    else:
        concern_lines = "\n".join(
            f"- {c.planet} ({c.reason}): "
            f"gemstone {c.gemstone.gemstone_english} ({c.gemstone.gemstone_sanskrit}) in {c.gemstone.metal} "
            f"on the {c.gemstone.finger}, worn starting on a {c.gemstone.weekday}; "
            f"mantra '{c.mantra.beej_mantra}' ({c.mantra.recitation_count}x); "
            f"charity: {c.charity.item} on {c.charity.weekday}"
            for c in profile.concerns
        )

    strongest_line = (
        f"Strongest placement: {profile.strongest_planet} is exalted in this chart."
        if profile.strongest_planet else
        "No planet is in its exaltation sign in this chart."
    )

    user = f"""Remedy profile for {profile.name}.

{strongest_line}

Calculated planets flagged for classical remedial attention:
{concern_lines}

Using only this data, write guidance covering:
1. What these specific flagged planets suggest about where this person may \
feel friction or need extra support
2. For the single most significant flagged planet, explain the gemstone, \
mantra, and charity remedy in practical terms — what to actually do, not just \
what the stone is called
3. A brief grounding note: remedies are a classical tool for support, not a \
guarantee, and a gemstone in particular should ideally be confirmed by a \
qualified astrologer before purchase since an unsuitable stone is classically \
considered counterproductive

Around 260 words."""

    return system, user


def build_panchang_prompt(name: str, panchang: PanchangResult, language_code: str) -> tuple[str, str]:
    system = BASE_SYSTEM_PROMPT.format(language_name=_lang_name(language_code))

    yoga_quality = (
        "favorable" if panchang.yoga_is_favorable is True
        else "unfavorable" if panchang.yoga_is_favorable is False
        else "neutral"
    )

    user = f"""Daily Panchang for {name} — {panchang.date} ({panchang.weekday}, ruled by {panchang.weekday_lord}).

Calculated Panchang elements:
- Tithi: {panchang.paksha} Paksha, {panchang.tithi_name} (day {panchang.tithi_number})
- Nakshatra: {panchang.nakshatra}, pada {panchang.nakshatra_pada}
- Yoga: {panchang.yoga_name} ({yoga_quality})
- Karana: {panchang.karana_name}
- Rahu Kaal: {panchang.rahu_kaal_start.strftime('%H:%M')} to {panchang.rahu_kaal_end.strftime('%H:%M')} (local time)

Using only this data, write a short daily guidance note covering:
1. The overall character of the day given this Tithi and Nakshatra combination
2. What the Yoga suggests is favored or best avoided today
3. A reminder about the Rahu Kaal window for timing-sensitive decisions
4. One practical, specific suggestion for how to use today well

Around 180 words. Keep it grounded and specific to today's actual \
combination, not a generic daily-horoscope tone."""

    return system, user
