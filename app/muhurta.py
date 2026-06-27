"""
Muhurta (auspicious timing) calculation engine.

Per the master plan's authenticity rule, this module never invents a
verdict — it scores real, already-computed Panchang data (from
panchang.py) against classical rule sets compiled from cross-checked
sources for each activity type. AI's only role (in interpretation.py)
is to explain the score, and to map a free-text activity description
onto one of these known rule sets. AI never assigns the score itself.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.panchang import compute_panchang, PanchangResult

RIKTA_TITHIS = {"Chaturthi", "Navami", "Chaturdashi"}


@dataclass
class ActivityRules:
    key: str
    label: str
    good_nakshatras: set[str]
    good_tithis: set[str]
    good_weekdays: set[str]
    avoid_karanas: set[str] = field(default_factory=lambda: {"Vishti"})
    avoid_tithis: set[str] = field(default_factory=lambda: set(RIKTA_TITHIS))
    notes: str = ""


ACTIVITY_RULES: dict[str, ActivityRules] = {
    "marriage": ActivityRules(
        key="marriage",
        label="Marriage",
        good_nakshatras={
            "Rohini", "Mrigashira", "Magha", "Uttara Phalguni", "Hasta", "Swati",
            "Anuradha", "Mula", "Uttara Ashadha", "Uttara Bhadrapada", "Revati",
        },
        good_tithis={"Dwitiya", "Tritiya", "Panchami", "Saptami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi"},
        good_weekdays={"Monday", "Wednesday", "Thursday", "Friday"},
        avoid_karanas={"Vishti", "Shakuni", "Chatushpada", "Naga"},
        notes="Also classically requires Venus and Jupiter not be combust (Tara Asta) — not checked by this engine; consult a Jyotish practitioner for that layer.",
    ),
    "housewarming": ActivityRules(
        key="housewarming",
        label="Housewarming (Griha Pravesh)",
        good_nakshatras={
            "Rohini", "Mrigashira", "Chitra", "Anuradha", "Pushya",
            "Uttara Phalguni", "Uttara Ashadha", "Uttara Bhadrapada", "Revati", "Dhanishta",
        },
        good_tithis={"Dwitiya", "Tritiya", "Panchami", "Dashami", "Ekadashi", "Trayodashi"},
        good_weekdays={"Monday", "Wednesday", "Thursday", "Friday"},
        notes="Sunday and Saturday are generally avoided; Tuesday is most strongly avoided.",
    ),
    "business": ActivityRules(
        key="business",
        label="Starting a business",
        good_nakshatras={
            "Pushya", "Rohini", "Hasta", "Ashwini", "Chitra", "Swati", "Anuradha", "Revati",
        },
        good_tithis={"Dwitiya", "Tritiya", "Panchami", "Saptami", "Dashami", "Ekadashi", "Trayodashi"},
        good_weekdays={"Wednesday", "Thursday", "Friday"},
        notes="Pushya Nakshatra falling on a Thursday (Guru Pushyamrut Yoga) is considered exceptionally favorable.",
    ),
    "travel": ActivityRules(
        key="travel",
        label="Travel / journey",
        good_nakshatras={
            "Ashwini", "Mrigashira", "Pushya", "Hasta", "Anuradha", "Shravana", "Revati",
            "Punarvasu", "Dhanishta",
        },
        good_tithis={"Dwitiya", "Tritiya", "Panchami", "Saptami", "Dashami", "Ekadashi", "Trayodashi"},
        good_weekdays={"Monday", "Wednesday", "Thursday", "Friday"},
        notes="Never begin travel during Rahu Kaal — this is the most widely observed travel restriction.",
    ),
    "education": ActivityRules(
        key="education",
        label="Starting education / a course",
        good_nakshatras={
            "Ashwini", "Rohini", "Punarvasu", "Hasta", "Swati", "Anuradha", "Mula",
            "Uttara Bhadrapada", "Pushya", "Shravana", "Mrigashira",
        },
        good_tithis={"Panchami", "Saptami", "Dashami", "Ekadashi"},
        good_weekdays={"Wednesday", "Thursday", "Friday"},
    ),
    "naming": ActivityRules(
        key="naming",
        label="Naming ceremony (Namkaran)",
        good_nakshatras={
            "Ashwini", "Shatabhisha", "Swati", "Chitra", "Revati", "Hasta", "Pushya",
            "Rohini", "Mrigashira", "Anuradha", "Uttara Ashadha", "Uttara Phalguni",
            "Uttara Bhadrapada", "Shravana",
        },
        good_tithis={"Dwitiya", "Tritiya", "Panchami", "Saptami", "Dashami", "Ekadashi", "Trayodashi"},
        good_weekdays={"Monday", "Wednesday", "Thursday", "Friday"},
        avoid_tithis=set(),
        notes="Traditionally performed on the 10th-12th day after birth; the date is often constrained by that window more than by Muhurta alone.",
    ),
}

ACTIVITY_LIST = list(ACTIVITY_RULES.keys())


@dataclass
class MuhurtaScore:
    date: str
    weekday: str
    score: int
    max_score: int
    nakshatra_favorable: bool
    tithi_favorable: bool
    weekday_favorable: bool
    karana_favorable: bool
    has_rikta_tithi: bool
    panchang: PanchangResult
    verdict: str


def _score_day(panchang: PanchangResult, rules: ActivityRules) -> MuhurtaScore:
    nakshatra_ok = panchang.nakshatra in rules.good_nakshatras
    tithi_ok = panchang.tithi_name in rules.good_tithis
    weekday_ok = panchang.weekday in rules.good_weekdays
    karana_ok = panchang.karana_name not in rules.avoid_karanas
    has_rikta = panchang.tithi_name in rules.avoid_tithis
    yoga_ok = panchang.yoga_is_favorable is not False

    criteria = [nakshatra_ok, tithi_ok, weekday_ok, karana_ok, yoga_ok]
    score = sum(1 for c in criteria if c)

    if has_rikta or not karana_ok:
        verdict = "Avoid — contains a classically prohibited element."
    elif score >= 4:
        verdict = "Excellent — strongly favorable across most criteria."
    elif score == 3:
        verdict = "Good — favorable on balance."
    elif score == 2:
        verdict = "Mixed — some support, some friction."
    else:
        verdict = "Weak — largely unfavorable for this activity."

    return MuhurtaScore(
        date=panchang.date,
        weekday=panchang.weekday,
        score=score,
        max_score=len(criteria),
        nakshatra_favorable=nakshatra_ok,
        tithi_favorable=tithi_ok,
        weekday_favorable=weekday_ok,
        karana_favorable=karana_ok,
        has_rikta_tithi=has_rikta,
        panchang=panchang,
        verdict=verdict,
    )


def validate_single_date(
    activity_key: str, date_str: str, latitude: float, longitude: float, tz_name: str,
) -> MuhurtaScore:
    if activity_key not in ACTIVITY_RULES:
        raise ValueError(f"Unknown activity type: {activity_key}")
    rules = ACTIVITY_RULES[activity_key]
    panchang = compute_panchang(date_str, latitude, longitude, tz_name)
    return _score_day(panchang, rules)


def search_date_range(
    activity_key: str, start_date: str, num_days: int,
    latitude: float, longitude: float, tz_name: str,
    limit: int = 10,
) -> list[MuhurtaScore]:
    if activity_key not in ACTIVITY_RULES:
        raise ValueError(f"Unknown activity type: {activity_key}")
    rules = ACTIVITY_RULES[activity_key]

    y, m, d = (int(x) for x in start_date.split("-"))
    start = datetime(y, m, d)

    results: list[MuhurtaScore] = []
    for offset in range(num_days):
        day = start + timedelta(days=offset)
        date_str = day.strftime("%Y-%m-%d")
        panchang = compute_panchang(date_str, latitude, longitude, tz_name)
        results.append(_score_day(panchang, rules))

    viable = [r for r in results if not (r.has_rikta_tithi or not r.karana_favorable)]
    viable.sort(key=lambda r: (-r.score, r.date))
    return viable[:limit]
