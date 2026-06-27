"""
Panchang calculation engine.

The five limbs (pancha-anga) of the Vedic calendar, calculated from real
Swiss Ephemeris Sun/Moon longitudes — the same authenticity rule as
every other module: real astronomical math first, AI interpretation
only explains the result afterward.

Formulas used (cross-checked against multiple independent published
sources during development):
  - Tithi = floor((Moon longitude - Sun longitude) mod 360 / 12) + 1
  - Yoga  = floor((Moon longitude + Sun longitude) mod 360 / (400/30)) + 1
    (13°20' = 800 arcminutes = 400/30 degrees... see note below)
  - Karana = floor((Moon longitude - Sun longitude) mod 360 / 6) + 1
  - Vaar (weekday) = the calendar weekday, each ruled by a fixed planet
  - Rahu Kaal = one-eighth of the sunrise-to-sunset daylight span, at a
    weekday-specific segment index
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import swisseph as swe

from app.vedic import NAKSHATRAS

# 13°20' expressed in degrees, used as the Yoga/Nakshatra span divisor
THIRTEEN_TWENTY = 360 / 27  # = 13.333... degrees, exactly 1/27th of the circle

TITHI_NAMES_SHUKLA = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi", "Purnima",
]
TITHI_NAMES_KRISHNA = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi", "Amavasya",
]

YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarma", "Dhriti", "Shoola", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
    "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti",
]

FAVORABLE_YOGAS = {
    "Siddhi", "Shubha", "Shukla", "Brahma", "Indra", "Saubhagya",
    "Shobhana", "Sukarma", "Dhriti", "Harshana", "Priti", "Ayushman", "Vriddhi",
}
UNFAVORABLE_YOGAS = {
    "Vyaghata", "Vajra", "Vyatipata", "Parigha", "Vaidhriti", "Atiganda",
    "Shoola", "Ganda",
}

MOVABLE_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]
FIXED_KARANAS_END = ["Shakuni", "Chatushpada", "Naga", "Kimstughna"]

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_LORDS = {
    "Monday": "Moon", "Tuesday": "Mars", "Wednesday": "Mercury",
    "Thursday": "Jupiter", "Friday": "Venus", "Saturday": "Saturn", "Sunday": "Sun",
}

# Rahu Kaal segment index (1-8, counting from sunrise) by weekday.
# Cross-checked against multiple independent published tables.
RAHU_KAAL_SEGMENT = {
    "Monday": 2, "Tuesday": 7, "Wednesday": 5, "Thursday": 6,
    "Friday": 4, "Saturday": 3, "Sunday": 8,
}


@dataclass
class PanchangResult:
    date: str
    weekday: str
    weekday_lord: str

    tithi_name: str
    tithi_number: int          # 1-15 within the paksha
    paksha: str                  # "Shukla" or "Krishna"

    nakshatra: str
    nakshatra_pada: int

    yoga_name: str
    yoga_is_favorable: bool | None  # None if neutral (neither list)

    karana_name: str

    sunrise: datetime
    sunset: datetime
    rahu_kaal_start: datetime
    rahu_kaal_end: datetime


def _sun_moon_longitudes(jd: float) -> tuple[float, float]:
    """Sidereal (Lahiri) longitudes of the Sun and Moon for a Julian day."""
    ayanamsha = swe.get_ayanamsa_ut(jd)
    sun_trop, _ = swe.calc_ut(jd, swe.SUN)
    moon_trop, _ = swe.calc_ut(jd, swe.MOON)
    sun_lon = (sun_trop[0] - ayanamsha) % 360
    moon_lon = (moon_trop[0] - ayanamsha) % 360
    return sun_lon, moon_lon


def _compute_tithi(sun_lon: float, moon_lon: float) -> tuple[str, int, str]:
    diff = (moon_lon - sun_lon) % 360
    tithi_index = int(diff // 12)  # 0-29
    if tithi_index < 15:
        paksha = "Shukla"
        name = TITHI_NAMES_SHUKLA[tithi_index]
        number = tithi_index + 1
    else:
        paksha = "Krishna"
        idx = tithi_index - 15
        name = TITHI_NAMES_KRISHNA[idx]
        number = idx + 1
    return name, number, paksha


def _compute_yoga(sun_lon: float, moon_lon: float) -> tuple[str, bool | None]:
    total = (sun_lon + moon_lon) % 360
    yoga_index = int(total // THIRTEEN_TWENTY) % 27
    name = YOGA_NAMES[yoga_index]
    if name in FAVORABLE_YOGAS:
        return name, True
    if name in UNFAVORABLE_YOGAS:
        return name, False
    return name, None


def _compute_karana(sun_lon: float, moon_lon: float) -> str:
    diff = (moon_lon - sun_lon) % 360
    karana_index = int(diff // 6)  # 0-59, 60 karanas in a lunar month

    # The four fixed karanas occupy specific slots at the start/end of the
    # cycle; the seven movable karanas cycle through the remaining 56.
    if karana_index == 0:
        return "Kimstughna"
    if karana_index == 57:
        return "Shakuni"
    if karana_index == 58:
        return "Chatushpada"
    if karana_index == 59:
        return "Naga"
    # movable karanas: indices 1-56 cycle through the 7 movable names
    movable_position = (karana_index - 1) % 7
    return MOVABLE_KARANAS[movable_position]


def _compute_nakshatra(moon_lon: float) -> tuple[str, int]:
    nak_span = 360 / 27
    nak_index = int(moon_lon // nak_span) % 27
    pada_span = nak_span / 4
    offset = moon_lon - (nak_index * nak_span)
    pada = int(offset // pada_span) + 1
    return NAKSHATRAS[nak_index], pada


def _approximate_sunrise_sunset(jd_midnight_ut: float, latitude: float, longitude: float) -> tuple[float, float]:
    """Sunrise/sunset as Julian day fractions, using Swiss Ephemeris's
    rise/set transit calculation."""
    geopos = (longitude, latitude, 0.0)
    _, sunrise_data = swe.rise_trans(jd_midnight_ut, swe.SUN, swe.CALC_RISE, geopos)
    _, sunset_data = swe.rise_trans(jd_midnight_ut, swe.SUN, swe.CALC_SET, geopos)
    return sunrise_data[0], sunset_data[0]


def _jd_to_datetime_utc(jd: float) -> datetime:
    y, m, d, h = swe.revjul(jd)
    hour = int(h)
    minute = int((h - hour) * 60)
    second = int((((h - hour) * 60) - minute) * 60)
    return datetime(y, m, d, hour, minute, second, tzinfo=ZoneInfo("UTC"))


def compute_panchang(date_str: str, latitude: float, longitude: float, tz_name: str) -> PanchangResult:
    """Full Panchang for a given calendar date at a given location."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    y, m, d = (int(x) for x in date_str.split("-"))
    local_noon = datetime(y, m, d, 12, 0, tzinfo=ZoneInfo(tz_name))
    utc_noon = local_noon.astimezone(ZoneInfo("UTC"))
    jd_noon = swe.julday(utc_noon.year, utc_noon.month, utc_noon.day,
                          utc_noon.hour + utc_noon.minute / 60)

    sun_lon, moon_lon = _sun_moon_longitudes(jd_noon)

    tithi_name, tithi_number, paksha = _compute_tithi(sun_lon, moon_lon)
    nakshatra, pada = _compute_nakshatra(moon_lon)
    yoga_name, yoga_favorable = _compute_yoga(sun_lon, moon_lon)
    karana_name = _compute_karana(sun_lon, moon_lon)

    weekday_index = datetime(y, m, d).weekday()  # 0=Monday
    weekday = WEEKDAY_NAMES[weekday_index]
    weekday_lord = WEEKDAY_LORDS[weekday]

    local_midnight = datetime(y, m, d, 0, 0, tzinfo=ZoneInfo(tz_name))
    utc_midnight = local_midnight.astimezone(ZoneInfo("UTC"))
    jd_midnight = swe.julday(utc_midnight.year, utc_midnight.month, utc_midnight.day,
                              utc_midnight.hour + utc_midnight.minute / 60)

    sunrise_jd, sunset_jd = _approximate_sunrise_sunset(jd_midnight, latitude, longitude)
    sunrise_utc = _jd_to_datetime_utc(sunrise_jd)
    sunset_utc = _jd_to_datetime_utc(sunset_jd)

    daylight_seconds = (sunset_utc - sunrise_utc).total_seconds()
    segment_seconds = daylight_seconds / 8
    segment_index = RAHU_KAAL_SEGMENT[weekday]  # 1-8
    rahu_start = sunrise_utc + timedelta(seconds=segment_seconds * (segment_index - 1))
    rahu_end = rahu_start + timedelta(seconds=segment_seconds)

    return PanchangResult(
        date=date_str,
        weekday=weekday,
        weekday_lord=weekday_lord,
        tithi_name=tithi_name,
        tithi_number=tithi_number,
        paksha=paksha,
        nakshatra=nakshatra,
        nakshatra_pada=pada,
        yoga_name=yoga_name,
        yoga_is_favorable=yoga_favorable,
        karana_name=karana_name,
        sunrise=sunrise_utc,
        sunset=sunset_utc,
        rahu_kaal_start=rahu_start,
        rahu_kaal_end=rahu_end,
    )
