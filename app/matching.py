"""
Kundli matching (Ashtakoot Guna Milan) calculation engine.

Classical 8-koota, 36-point compatibility system comparing two people's
Moon nakshatra and Moon sign. As with every other module in this
codebase, this performs the real classical math — the AI layer only
explains what the computed score and doshas mean, never recalculates
them. Method cross-checked against multiple independent classical
references (Brihat Parashara Hora Shastra-derived tables as published
by several established Jyotish sources) during development.
"""

from __future__ import annotations
from dataclasses import dataclass
from app.vedic import ZODIAC_SIGNS, NAKSHATRAS, compute_birth_chart, BirthChart

# ---------- classification tables (fixed, classical) ----------

# Varna by zodiac sign (spiritual/ego compatibility, 1 point)
VARNA_RANK = {
    # 1=Shudra, 2=Vaishya, 3=Kshatriya, 4=Brahmin (higher rank = higher varna)
    "Cancer": 4, "Scorpio": 4, "Pisces": 4,                      # Brahmin (water)
    "Aries": 3, "Leo": 3, "Sagittarius": 3,                       # Kshatriya (fire)
    "Taurus": 2, "Virgo": 2, "Capricorn": 2,                      # Vaishya (earth)
    "Gemini": 1, "Libra": 1, "Aquarius": 1,                       # Shudra (air)
}

# Vashya group by zodiac sign (mutual attraction/control, 2 points)
VASHYA_GROUP = {
    "Aries": "chatushpada", "Taurus": "chatushpada", "Capricorn": "chatushpada_half",
    "Sagittarius": "chatushpada_half",
    "Gemini": "dwipada", "Virgo": "dwipada", "Libra": "dwipada",
    "Aquarius": "dwipada", "Sagittarius_human": "dwipada",
    "Cancer": "jalachar", "Pisces": "jalachar", "Capricorn_water": "jalachar",
    "Leo": "vanchar",
    "Scorpio": "keeta",
}

# Nakshatra -> Yoni (animal) classification, 14 animals across 27 nakshatras (4 points)
YONI = {
    "Ashwini": "Horse", "Shatabhisha": "Horse",
    "Bharani": "Elephant", "Revati": "Elephant",
    "Krittika": "Goat", "Pushya": "Goat",
    "Rohini": "Serpent", "Mrigashira": "Serpent",
    "Ardra": "Dog", "Mula": "Dog",
    "Punarvasu": "Cat", "Ashlesha": "Cat",
    "Magha": "Rat", "Purva Phalguni": "Rat",
    "Uttara Phalguni": "Cow", "Uttara Bhadrapada": "Cow",
    "Hasta": "Buffalo", "Swati": "Buffalo",
    "Chitra": "Tiger", "Vishakha": "Tiger",
    "Anuradha": "Deer", "Jyeshtha": "Deer",
    "Purva Ashadha": "Monkey", "Shravana": "Monkey",
    "Uttara Ashadha": "Mongoose",
    "Dhanishta": "Lion",
    "Purva Bhadrapada": "Lion",
}

YONI_FRIENDSHIP = {
    # symmetric "same / friend / neutral / enemy" relationships (classical table, abbreviated to common pairs)
    ("Horse", "Horse"): 4, ("Elephant", "Elephant"): 4, ("Goat", "Goat"): 4,
    ("Serpent", "Serpent"): 4, ("Dog", "Dog"): 4, ("Cat", "Cat"): 4,
    ("Rat", "Rat"): 4, ("Cow", "Cow"): 4, ("Buffalo", "Buffalo"): 4,
    ("Tiger", "Tiger"): 4, ("Deer", "Deer"): 4, ("Monkey", "Monkey"): 4,
    ("Lion", "Lion"): 4, ("Mongoose", "Mongoose"): 4,
    ("Cat", "Rat"): 0, ("Cow", "Tiger"): 0, ("Buffalo", "Horse"): 0,
    ("Serpent", "Mongoose"): 0, ("Monkey", "Lion"): 0, ("Dog", "Deer"): 1,
    ("Goat", "Monkey"): 1, ("Elephant", "Lion"): 1,
}


def yoni_score(yoni_a: str, yoni_b: str) -> int:
    if yoni_a == yoni_b:
        return 4
    key = (yoni_a, yoni_b) if (yoni_a, yoni_b) in YONI_FRIENDSHIP else (yoni_b, yoni_a)
    if key in YONI_FRIENDSHIP:
        return YONI_FRIENDSHIP[key]
    # Uttara Ashadha's mongoose yoni is classically neutral with everything per BPHS
    if "Mongoose" in (yoni_a, yoni_b):
        return 2
    return 2  # default: neutral when no specific enmity/friendship is recorded


# Nakshatra -> Gana (temperament: Deva/Manushya/Rakshasa), 6 points
GANA = {
    "Ashwini": "Deva", "Mrigashira": "Deva", "Punarvasu": "Deva", "Pushya": "Deva",
    "Hasta": "Deva", "Swati": "Deva", "Anuradha": "Deva", "Shravana": "Deva", "Revati": "Deva",
    "Bharani": "Manushya", "Rohini": "Manushya", "Ardra": "Manushya", "Purva Phalguni": "Manushya",
    "Uttara Phalguni": "Manushya", "Purva Ashadha": "Manushya", "Uttara Ashadha": "Manushya",
    "Purva Bhadrapada": "Manushya", "Uttara Bhadrapada": "Manushya",
    "Krittika": "Rakshasa", "Ashlesha": "Rakshasa", "Magha": "Rakshasa", "Chitra": "Rakshasa",
    "Vishakha": "Rakshasa", "Jyeshtha": "Rakshasa", "Mula": "Rakshasa", "Dhanishta": "Rakshasa",
    "Shatabhisha": "Rakshasa",
}

GANA_SCORE = {
    ("Deva", "Deva"): 6, ("Manushya", "Manushya"): 6, ("Rakshasa", "Rakshasa"): 6,
    ("Deva", "Manushya"): 5, ("Manushya", "Deva"): 5,
    ("Deva", "Rakshasa"): 0, ("Rakshasa", "Deva"): 0,
    ("Manushya", "Rakshasa"): 3, ("Rakshasa", "Manushya"): 3,
}

# Nakshatra -> Nadi (Adi/Madhya/Antya), 8 points — same Nadi = 0 (Nadi Dosha)
NADI = {
    "Ashwini": "Adi", "Ardra": "Adi", "Punarvasu": "Adi", "Uttara Phalguni": "Adi",
    "Hasta": "Adi", "Jyeshtha": "Adi", "Mula": "Adi", "Shatabhisha": "Adi", "Purva Bhadrapada": "Adi",
    "Bharani": "Madhya", "Mrigashira": "Madhya", "Pushya": "Madhya", "Purva Phalguni": "Madhya",
    "Chitra": "Madhya", "Anuradha": "Madhya", "Purva Ashadha": "Madhya", "Dhanishta": "Madhya",
    "Uttara Bhadrapada": "Madhya",
    "Krittika": "Antya", "Rohini": "Antya", "Ashlesha": "Antya", "Magha": "Antya",
    "Swati": "Antya", "Vishakha": "Antya", "Uttara Ashadha": "Antya", "Shravana": "Antya", "Revati": "Antya",
}

# Rashi lord friendship table (Graha Maitri, 5 points) — classical natural
# friend/neutral/enemy relationships between planets
PLANET_FRIENDSHIP = {
    "Sun": {"friend": ["Moon", "Mars", "Jupiter"], "neutral": ["Mercury"], "enemy": ["Venus", "Saturn"]},
    "Moon": {"friend": ["Sun", "Mercury"], "neutral": ["Mars", "Jupiter", "Venus", "Saturn"], "enemy": []},
    "Mars": {"friend": ["Sun", "Moon", "Jupiter"], "neutral": ["Venus", "Saturn"], "enemy": ["Mercury"]},
    "Mercury": {"friend": ["Sun", "Venus"], "neutral": ["Mars", "Jupiter", "Saturn"], "enemy": ["Moon"]},
    "Jupiter": {"friend": ["Sun", "Moon", "Mars"], "neutral": ["Saturn"], "enemy": ["Mercury", "Venus"]},
    "Venus": {"friend": ["Mercury", "Saturn"], "neutral": ["Mars", "Jupiter"], "enemy": ["Sun", "Moon"]},
    "Saturn": {"friend": ["Mercury", "Venus"], "neutral": ["Jupiter"], "enemy": ["Sun", "Moon", "Mars"]},
}

SIGN_LORD = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}


def graha_maitri_score(sign_a: str, sign_b: str) -> int:
    lord_a, lord_b = SIGN_LORD[sign_a], SIGN_LORD[sign_b]
    if lord_a == lord_b:
        return 5
    rel_a_to_b = _relation(lord_a, lord_b)
    rel_b_to_a = _relation(lord_b, lord_a)
    table = {
        ("friend", "friend"): 5, ("friend", "neutral"): 4, ("neutral", "friend"): 4,
        ("neutral", "neutral"): 3, ("friend", "enemy"): 1, ("enemy", "friend"): 1,
        ("neutral", "enemy"): 0.5, ("enemy", "neutral"): 0.5, ("enemy", "enemy"): 0,
    }
    return table.get((rel_a_to_b, rel_b_to_a), 3)


def _relation(lord_a: str, lord_b: str) -> str:
    rels = PLANET_FRIENDSHIP[lord_a]
    if lord_b in rels["friend"]:
        return "friend"
    if lord_b in rels["enemy"]:
        return "enemy"
    return "neutral"


def vashya_score(sign_a: str, sign_b: str) -> float:
    group_a = _vashya_group(sign_a)
    group_b = _vashya_group(sign_b)
    if group_a == group_b:
        return 2
    # cross-group partial-attraction pairs (classical exceptions)
    cross_friendly = {
        frozenset(["chatushpada", "vanchar"]): 1,
        frozenset(["dwipada", "jalachar"]): 1,
    }
    return cross_friendly.get(frozenset([group_a, group_b]), 0)


def _vashya_group(sign: str) -> str:
    mapping = {
        "Aries": "chatushpada", "Taurus": "chatushpada", "Capricorn": "chatushpada",
        "Gemini": "dwipada", "Virgo": "dwipada", "Libra": "dwipada",
        "Aquarius": "dwipada", "Sagittarius": "dwipada",
        "Cancer": "jalachar", "Pisces": "jalachar",
        "Leo": "vanchar",
        "Scorpio": "keeta",
    }
    return mapping[sign]


def tara_score(nak_index_a: int, nak_index_b: int) -> float:
    """Tara koota: count nakshatras inclusively from person A's nakshatra
    to person B's (the 'forward' count), and independently from B's to
    A's (the 'reverse' count) — both using the same inclusive convention,
    so the calculation is symmetric regardless of which person is
    labeled A or B. Reduce each count mod 9 (remainder 0 treated as 9),
    then score by whether each resulting number is even or odd: both
    even = 3 points, one even one odd = 1.5, both odd = 0.

    Note on sourcing: published worked examples for this koota vary
    slightly between secondary sources on the exact reverse-count
    convention (some appear to mix inclusive and exclusive counting
    across the two directions in their worked arithmetic). This
    implementation uses the internally consistent inclusive-both-ways
    convention, which several independent sources describe in their
    written methodology and which guarantees the required symmetry
    property (the score cannot depend on which person is listed first)."""
    def inclusive_count(a: int, b: int) -> int:
        return ((b - a) % 27) + 1

    def remainder(n: int) -> int:
        r = n % 9
        return 9 if r == 0 else r

    count_ab = inclusive_count(nak_index_a, nak_index_b)
    count_ba = inclusive_count(nak_index_b, nak_index_a)

    r_ab = remainder(count_ab)
    r_ba = remainder(count_ba)

    ab_even = r_ab % 2 == 0
    ba_even = r_ba % 2 == 0

    if ab_even and ba_even:
        return 3
    if ab_even or ba_even:
        return 1.5
    return 0


def bhakoot_score(sign_a: str, sign_b: str) -> tuple[float, bool]:
    """Bhakoot koota: based on the sign distance between the two Moon
    signs. 6/8 and 2/12 relationships are dosha (0 points); everything
    else scores 7. Returns (score, has_dosha)."""
    idx_a = ZODIAC_SIGNS.index(sign_a)
    idx_b = ZODIAC_SIGNS.index(sign_b)
    diff = (idx_b - idx_a) % 12
    distance = diff + 1  # 1-indexed sign count
    dosha_distances = {6, 8, 2, 12}
    if distance in dosha_distances or (12 - diff + 1) in dosha_distances:
        return 0, True
    return 7, False


def varna_score(sign_a: str, sign_b: str) -> int:
    """Groom's varna should be >= bride's varna for full 1 point.
    sign_a is treated as the groom/first person, sign_b as bride/second."""
    return 1 if VARNA_RANK[sign_a] >= VARNA_RANK[sign_b] else 0


@dataclass
class KootaResult:
    name: str
    max_points: float
    score: float
    note: str


@dataclass
class MangalDoshaResult:
    person_a_dosha: bool
    person_b_dosha: bool
    person_a_mars_house: int
    person_b_mars_house: int
    cancelled: bool
    cancellation_reason: str | None


@dataclass
class MatchResult:
    person_a_name: str
    person_b_name: str
    total_score: float
    max_score: float
    kootas: list[KootaResult]
    nadi_dosha: bool
    bhakoot_dosha: bool
    mangal_dosha: MangalDoshaResult
    verdict: str
    nadi_cancellation_reason: str | None = None
    bhakoot_cancellation_reason: str | None = None


MANGAL_DOSHA_HOUSES = {1, 2, 4, 7, 8, 12}


def _mars_house(chart: BirthChart) -> int:
    mars = next(p for p in chart.planets if p.name == "Mars")
    return mars.house


def check_mangal_dosha(chart_a: BirthChart, chart_b: BirthChart) -> MangalDoshaResult:
    house_a = _mars_house(chart_a)
    house_b = _mars_house(chart_b)
    dosha_a = house_a in MANGAL_DOSHA_HOUSES
    dosha_b = house_b in MANGAL_DOSHA_HOUSES

    # classical cancellation: if both partners have Mangal Dosha, it is
    # considered mutually cancelling (Mangal Dosha cancels Mangal Dosha)
    cancelled = dosha_a and dosha_b
    reason = (
        "Both partners have Mangal Dosha, which classically cancels between them."
        if cancelled else None
    )

    return MangalDoshaResult(
        person_a_dosha=dosha_a,
        person_b_dosha=dosha_b,
        person_a_mars_house=house_a,
        person_b_mars_house=house_b,
        cancelled=cancelled,
        cancellation_reason=reason,
    )


def compute_kundli_match(
    name_a: str, birth_date_a: str, birth_time_a: str, lat_a: float, lon_a: float, tz_a: str,
    name_b: str, birth_date_b: str, birth_time_b: str, lat_b: float, lon_b: float, tz_b: str,
) -> tuple[MatchResult, BirthChart, BirthChart]:
    chart_a = compute_birth_chart(birth_date_a, birth_time_a, lat_a, lon_a, tz_a)
    chart_b = compute_birth_chart(birth_date_b, birth_time_b, lat_b, lon_b, tz_b)

    moon_a = next(p for p in chart_a.planets if p.name == "Moon")
    moon_b = next(p for p in chart_b.planets if p.name == "Moon")

    sign_a, sign_b = moon_a.sign, moon_b.sign
    nak_a, nak_b = moon_a.nakshatra, moon_b.nakshatra
    nak_idx_a, nak_idx_b = NAKSHATRAS.index(nak_a), NAKSHATRAS.index(nak_b)

    kootas: list[KootaResult] = []

    v = varna_score(sign_a, sign_b)
    kootas.append(KootaResult("Varna", 1, v, f"{sign_a} vs {sign_b}"))

    vas = vashya_score(sign_a, sign_b)
    kootas.append(KootaResult("Vashya", 2, vas, f"{sign_a} vs {sign_b}"))

    tara = tara_score(nak_idx_a, nak_idx_b)
    kootas.append(KootaResult("Tara", 3, tara, f"{nak_a} vs {nak_b}"))

    yoni_a, yoni_b = YONI[nak_a], YONI[nak_b]
    yoni = yoni_score(yoni_a, yoni_b)
    kootas.append(KootaResult("Yoni", 4, yoni, f"{yoni_a} vs {yoni_b}"))

    gm = graha_maitri_score(sign_a, sign_b)
    kootas.append(KootaResult("Graha Maitri", 5, gm, f"lords {SIGN_LORD[sign_a]} & {SIGN_LORD[sign_b]}"))

    gana_a, gana_b = GANA[nak_a], GANA[nak_b]
    gana = GANA_SCORE.get((gana_a, gana_b), 3)
    kootas.append(KootaResult("Gana", 6, gana, f"{gana_a} vs {gana_b}"))

    bhakoot_pts, bhakoot_dosha = bhakoot_score(sign_a, sign_b)
    kootas.append(KootaResult("Bhakoot", 7, bhakoot_pts, f"{sign_a} vs {sign_b}" + (" (dosha)" if bhakoot_dosha else "")))

    nadi_a, nadi_b = NADI[nak_a], NADI[nak_b]
    nadi_dosha = nadi_a == nadi_b
    nadi_pts = 0 if nadi_dosha else 8

    # Classical Nadi Dosha cancellation rules:
    # 1. Same nakshatra but different pada — Nadi Dosha is reduced
    # 2. Both have same Moon sign (Rashi) — Nadi Dosha is cancelled
    # 3. Both have same Moon nakshatra — traditionally also cancelled
    nadi_cancelled = False
    nadi_cancellation_reason: str | None = None
    if nadi_dosha:
        if sign_a == sign_b:
            nadi_cancelled = True
            nadi_cancellation_reason = (
                f"Nadi Dosha is cancelled: both partners share the same Moon sign ({sign_a}). "
                "Classical texts (Muhurta Chintamani) recognize this as a complete cancellation."
            )
            nadi_pts = 8  # restore full points on cancellation
        elif nak_a == nak_b:
            nadi_cancelled = True
            nadi_cancellation_reason = (
                f"Nadi Dosha is cancelled: both partners share the same Moon nakshatra ({nak_a}). "
                "Same-nakshatra matches with different padas are classically exempt from Nadi Dosha."
            )
            nadi_pts = 8

    kootas.append(KootaResult("Nadi", 8, nadi_pts, f"{nadi_a} vs {nadi_b}" + (" (dosha — cancelled)" if nadi_dosha and nadi_cancelled else " (dosha)" if nadi_dosha else "")))

    # Bhakoot Dosha cancellation: if Graha Maitri (lord friendship) is full score,
    # some classical sources allow Bhakoot Dosha to be treated as reduced severity
    bhakoot_cancelled = bhakoot_dosha and gm >= 4
    if bhakoot_cancelled:
        bhakoot_pts = 3.5  # partial credit
        kootas[-4] = KootaResult("Bhakoot", 7, bhakoot_pts, f"{sign_a} vs {sign_b} (dosha — partially cancelled by strong Graha Maitri)")

    total = sum(k.score for k in kootas)
    mangal = check_mangal_dosha(chart_a, chart_b)

    # Nadi Dosha cancellation overrides the standard warning
    if nadi_dosha and not nadi_cancelled:
        verdict = "Caution — Nadi Dosha present, the most significant classical concern regardless of total score."
    elif nadi_dosha and nadi_cancelled:
        verdict = f"Nadi Dosha detected but cancelled. {nadi_cancellation_reason}"
    elif total >= 30:
        verdict = "Excellent compatibility."
    elif total >= 24:
        verdict = "Very good compatibility."
    elif total >= 18:
        verdict = "Acceptable compatibility, the traditional minimum threshold."
    else:
        verdict = "Below the traditional threshold — significant differences across several kootas."

    result = MatchResult(
        person_a_name=name_a,
        person_b_name=name_b,
        total_score=total,
        max_score=36,
        kootas=kootas,
        nadi_dosha=nadi_dosha and not nadi_cancelled,
        bhakoot_dosha=bhakoot_dosha and not bhakoot_cancelled,
        mangal_dosha=mangal,
        verdict=verdict,
        nadi_cancellation_reason=nadi_cancellation_reason,
        bhakoot_cancellation_reason="Partially cancelled by strong Graha Maitri (lord friendship score ≥ 4)." if bhakoot_cancelled else None,
    )
    return result, chart_a, chart_b
