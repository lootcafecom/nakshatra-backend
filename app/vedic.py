"""
Vedic astrology calculation engine.

This module is the *only* place planetary positions get calculated.
Everything downstream (the API layer, the AI interpretation prompts)
consumes structured output from here and never recomputes or guesses
positions itself. This separation is the authenticity guarantee from
the master plan: AI interprets, it never calculates.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo
import swisseph as swe

# Lahiri ayanamsha is the most widely used standard in Indian Vedic
# astrology (used by most panchang publishers and astrology software).
swe.set_sid_mode(swe.SIDM_LAHIRI)

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

SIGN_LORDS = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

# Each nakshatra's ruling planet, in the fixed classical cycle used to
# derive Vimshottari Dasha order. The cycle repeats every 9 nakshatras.
NAKSHATRA_LORDS_CYCLE = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury",
]

# Vimshottari Dasha total years per planet — fixed classical values,
# total = 120 years for one full cycle.
DASHA_YEARS = {
    "Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
    "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17,
}
DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]

PLANETS = {
    "Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN,
}
# Rahu (mean lunar north node) is computed by Swiss Ephemeris directly;
# Ketu is always exactly 180° opposite Rahu — this is a fixed astronomical
# relationship, not an approximation.


@dataclass
class PlanetPosition:
    name: str
    longitude: float          # 0-360, sidereal (Lahiri)
    sign: str
    sign_degree: float        # 0-30 degrees within the sign
    nakshatra: str
    nakshatra_pada: int        # 1-4
    house: int                  # 1-12, relative to ascendant
    retrograde: bool


@dataclass
class DashaPeriod:
    planet: str
    start: datetime
    end: datetime


@dataclass
class AntarDasha:
    """Sub-period (Bhukti) within a Mahadasha. Calculated as the
    proportional share of the Mahadasha duration for each planet in
    the classical 9-planet cycle, starting from the Mahadasha planet
    itself and cycling through the Dasha order."""
    mahadasha_planet: str
    antardasha_planet: str
    start: datetime
    end: datetime


@dataclass
class BirthChart:
    julian_day: float
    ascendant_sign: str
    ascendant_degree: float
    planets: list[PlanetPosition] = field(default_factory=list)
    moon_nakshatra: str = ""
    moon_nakshatra_pada: int = 1
    dasha_timeline: list[DashaPeriod] = field(default_factory=list)
    current_dasha: str = ""
    antardasha_timeline: list[AntarDasha] = field(default_factory=list)
    current_antardasha: str = ""


def compute_antardasha(mahadasha: DashaPeriod) -> list[AntarDasha]:
    """
    Antardasha (Bhukti) — sub-periods within a Mahadasha.
    Formula: sub_period_days = (maha_planet_years × sub_planet_years / 120) × 365.25
    This gives each sub-period as a fraction of the full 120-year cycle,
    then scaled to the mahadasha's actual elapsed duration.
    Cross-checked: Rahu (18yr) Mahadasha → Rahu/Rahu sub-period = 18×18/120 = 2.7 years ≈ 986 days.
    """
    start_idx = DASHA_ORDER.index(mahadasha.planet)
    maha_years = DASHA_YEARS[mahadasha.planet]

    antardashas: list[AntarDasha] = []
    cursor = mahadasha.start

    for i in range(9):
        idx = (start_idx + i) % 9
        sub_planet = DASHA_ORDER[idx]
        sub_years = DASHA_YEARS[sub_planet]
        # classical formula: maha_years × sub_years / 120 years
        sub_duration_years = (maha_years * sub_years) / 120.0
        from datetime import timedelta
        end = cursor + timedelta(days=sub_duration_years * 365.25)
        antardashas.append(AntarDasha(
            mahadasha_planet=mahadasha.planet,
            antardasha_planet=sub_planet,
            start=cursor,
            end=end,
        ))
        cursor = end

    return antardashas


def _sign_index(longitude: float) -> int:
    return int(longitude // 30) % 12


def _nakshatra_index(longitude: float) -> int:
    # each nakshatra spans 360/27 = 13.3333... degrees
    return int(longitude // (360 / 27)) % 27


def _pada(longitude: float) -> int:
    # each pada spans 360/108 = 3.3333... degrees, 4 padas per nakshatra
    span = 360 / 108
    nak_start = _nakshatra_index(longitude) * (360 / 27)
    offset = longitude - nak_start
    return int(offset // span) + 1


def _house_of(longitude: float, asc_longitude: float) -> int:
    """Whole-sign house system: the ascendant's sign is house 1, and
    houses follow sequentially around the zodiac. This is the house
    system most commonly used in Vedic (Jyotisha) practice."""
    asc_sign = _sign_index(asc_longitude)
    planet_sign = _sign_index(longitude)
    return ((planet_sign - asc_sign) % 12) + 1


def compute_julian_day(birth_dt_local: datetime, tz_name: str) -> float:
    """Convert a local birth datetime + IANA timezone name to the UT
    Julian day Swiss Ephemeris expects."""
    local = birth_dt_local.replace(tzinfo=ZoneInfo(tz_name))
    utc = local.astimezone(ZoneInfo("UTC"))
    hour_decimal = utc.hour + utc.minute / 60 + utc.second / 3600
    return swe.julday(utc.year, utc.month, utc.day, hour_decimal)


def compute_ascendant(jd: float, lat: float, lon: float) -> tuple[float, float]:
    """Returns (sidereal ascendant longitude, ayanamsha value used)."""
    ayanamsha = swe.get_ayanamsa_ut(jd)
    # Whole-sign / Placidus cusps via swe.houses; cusps[0] is the Ascendant (tropical)
    cusps, ascmc = swe.houses(jd, lat, lon, b"P")
    tropical_asc = ascmc[0]
    sidereal_asc = (tropical_asc - ayanamsha) % 360
    return sidereal_asc, ayanamsha


def compute_planet_positions(jd: float, asc_longitude: float) -> list[PlanetPosition]:
    ayanamsha = swe.get_ayanamsa_ut(jd)
    positions: list[PlanetPosition] = []

    for name, code in PLANETS.items():
        result, _flag = swe.calc_ut(jd, code)
        tropical_lon = result[0]
        speed = result[3]
        sidereal_lon = (tropical_lon - ayanamsha) % 360
        positions.append(_build_position(name, sidereal_lon, asc_longitude, retrograde=speed < 0))

    # Rahu — mean lunar north node
    rahu_result, _flag = swe.calc_ut(jd, swe.MEAN_NODE)
    rahu_tropical = rahu_result[0]
    rahu_sidereal = (rahu_tropical - ayanamsha) % 360
    positions.append(_build_position("Rahu", rahu_sidereal, asc_longitude, retrograde=True))

    # Ketu — always exactly 180 degrees from Rahu
    ketu_sidereal = (rahu_sidereal + 180) % 360
    positions.append(_build_position("Ketu", ketu_sidereal, asc_longitude, retrograde=True))

    return positions


def _build_position(name: str, sidereal_lon: float, asc_longitude: float, retrograde: bool) -> PlanetPosition:
    sign_idx = _sign_index(sidereal_lon)
    nak_idx = _nakshatra_index(sidereal_lon)
    return PlanetPosition(
        name=name,
        longitude=round(sidereal_lon, 4),
        sign=ZODIAC_SIGNS[sign_idx],
        sign_degree=round(sidereal_lon % 30, 2),
        nakshatra=NAKSHATRAS[nak_idx],
        nakshatra_pada=_pada(sidereal_lon),
        house=_house_of(sidereal_lon, asc_longitude),
        retrograde=retrograde,
    )


def compute_vimshottari_dasha(moon_longitude: float, birth_dt_utc: datetime) -> tuple[list[DashaPeriod], str]:
    """
    Vimshottari Dasha: a fixed 120-year cycle of planetary periods, the
    most widely used predictive timing system in Vedic astrology. The
    starting planet and how much of its period remains at birth are
    both determined by the Moon's exact nakshatra position — this is
    classical method, not an approximation.
    """
    nak_idx = _nakshatra_index(moon_longitude)
    nak_span = 360 / 27
    nak_start_lon = nak_idx * nak_span
    fraction_elapsed = (moon_longitude - nak_start_lon) / nak_span  # 0 to 1

    starting_lord = NAKSHATRA_LORDS_CYCLE[nak_idx % 9]
    start_order_idx = DASHA_ORDER.index(starting_lord)

    # the remaining fraction of the starting dasha at birth
    first_full_years = DASHA_YEARS[starting_lord]
    elapsed_years = first_full_years * fraction_elapsed
    remaining_years = first_full_years - elapsed_years

    timeline: list[DashaPeriod] = []
    cursor = birth_dt_utc
    # first (partial) period
    end = _add_years(cursor, remaining_years)
    timeline.append(DashaPeriod(planet=starting_lord, start=cursor, end=end))
    cursor = end

    # subsequent full periods, cycling through DASHA_ORDER, for 100 years of timeline
    idx = start_order_idx
    for _ in range(12):
        idx = (idx + 1) % len(DASHA_ORDER)
        planet = DASHA_ORDER[idx]
        years = DASHA_YEARS[planet]
        end = _add_years(cursor, years)
        timeline.append(DashaPeriod(planet=planet, start=cursor, end=end))
        cursor = end

    now = datetime.now(ZoneInfo("UTC"))
    current = next((p.planet for p in timeline if p.start <= now <= p.end), timeline[0].planet)

    return timeline, current


def _add_years(dt: datetime, years: float) -> datetime:
    # 365.25-day year, consistent with classical dasha-duration convention
    from datetime import timedelta
    return dt + timedelta(days=years * 365.25)


def compute_birth_chart(
    birth_date: str,      # "YYYY-MM-DD"
    birth_time: str,      # "HH:MM"
    latitude: float,
    longitude: float,
    tz_name: str,
) -> BirthChart:
    """Main entry point: full birth chart from raw birth data."""
    y, m, d = (int(x) for x in birth_date.split("-"))
    hh, mm = (int(x) for x in birth_time.split(":"))
    birth_dt_local = datetime(y, m, d, hh, mm)

    jd = compute_julian_day(birth_dt_local, tz_name)
    asc_longitude, _ayanamsha = compute_ascendant(jd, latitude, longitude)
    planets = compute_planet_positions(jd, asc_longitude)

    moon = next(p for p in planets if p.name == "Moon")
    birth_dt_utc = birth_dt_local.replace(tzinfo=ZoneInfo(tz_name)).astimezone(ZoneInfo("UTC"))
    dasha_timeline, current_dasha = compute_vimshottari_dasha(moon.longitude, birth_dt_utc)

    return BirthChart(
        julian_day=jd,
        ascendant_sign=ZODIAC_SIGNS[_sign_index(asc_longitude)],
        ascendant_degree=round(asc_longitude % 30, 2),
        planets=planets,
        moon_nakshatra=moon.nakshatra,
        moon_nakshatra_pada=moon.nakshatra_pada,
        dasha_timeline=dasha_timeline,
        current_dasha=current_dasha,
        antardasha_timeline=_build_antardasha_timeline(dasha_timeline, birth_dt_utc),
        current_antardasha=_find_current_antardasha(dasha_timeline),
    )


def _build_antardasha_timeline(dasha_timeline: list[DashaPeriod], birth_dt_utc: datetime) -> list[AntarDasha]:
    """Compute antardasha sub-periods for the current and next Mahadasha."""
    now = datetime.now(ZoneInfo("UTC"))
    result: list[AntarDasha] = []
    for dasha in dasha_timeline:
        # only compute for current and immediately next mahadasha to keep payload lean
        if dasha.end >= now:
            result.extend(compute_antardasha(dasha))
            if dasha.start > now:
                break  # we've included the next full mahadasha, stop there
    return result


def _find_current_antardasha(dasha_timeline: list[DashaPeriod]) -> str:
    now = datetime.now(ZoneInfo("UTC"))
    current_maha = next((d for d in dasha_timeline if d.start <= now <= d.end), None)
    if not current_maha:
        return ""
    antars = compute_antardasha(current_maha)
    current_antar = next((a for a in antars if a.start <= now <= a.end), None)
    return current_antar.antardasha_planet if current_antar else ""
