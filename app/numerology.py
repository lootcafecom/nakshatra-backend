"""
Numerology calculation engine.

Pure deterministic math — no external API, no AI. Per the master plan,
numerology's authenticity comes from showing the work: every number here
carries the visible reduction steps so a user can verify it themselves
rather than trusting an opaque result.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date

# Pythagorean letter-to-number mapping (1-9, repeating A-I, J-R, S-Z).
# This is the most common system used in Western/popular numerology apps.
# (Chaldean numerology, the older Indian-preferred system, uses a
# different 1-8 mapping — flagged as a planned alternate mode below.)
PYTHAGOREAN_MAP = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "I": 9,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "O": 6, "P": 7, "Q": 8, "R": 9,
    "S": 1, "T": 2, "U": 3, "V": 4, "W": 5, "X": 6, "Y": 7, "Z": 8,
}

VOWELS = set("AEIOU")

# Master numbers are not reduced further during digit-sum reduction.
MASTER_NUMBERS = {11, 22, 33}


@dataclass
class ReductionStep:
    """One step of a digit-sum reduction, kept so the UI can render the
    full visible working, e.g. '1995-06-15' -> '1+9+9+5+0+6+1+5' -> '36' -> '3+6' -> '9'."""
    input_value: str
    output_value: int


@dataclass
class NumerologyNumber:
    name: str               # e.g. "Life Path"
    value: int
    is_master: bool
    steps: list[ReductionStep]


def _digit_sum_reduce(n: int, allow_master: bool = True) -> tuple[int, list[ReductionStep]]:
    """Repeatedly sum digits until a single digit remains, unless a
    master number (11, 22, 33) appears, in which case reduction stops
    there per classical numerology convention."""
    steps: list[ReductionStep] = []
    current = n
    while current > 9:
        if allow_master and current in MASTER_NUMBERS:
            break
        digits = [int(d) for d in str(current)]
        next_val = sum(digits)
        steps.append(ReductionStep(input_value="+".join(str(d) for d in digits), output_value=next_val))
        current = next_val
    return current, steps


def compute_life_path(birth_date: date) -> NumerologyNumber:
    """Life Path Number: the digit-sum reduction of the full birth date.
    The most foundational number in a numerology reading."""
    date_str = birth_date.strftime("%Y-%m-%d").replace("-", "")
    digits = [int(d) for d in date_str]
    total = sum(digits)
    first_step = ReductionStep(input_value="+".join(str(d) for d in digits), output_value=total)
    value, rest_steps = _digit_sum_reduce(total)
    steps = [first_step] + rest_steps
    return NumerologyNumber(name="Life Path", value=value, is_master=value in MASTER_NUMBERS, steps=steps)


def _letters_only(name: str) -> str:
    return "".join(ch for ch in name.upper() if ch.isalpha())


def compute_expression_number(full_name: str) -> NumerologyNumber:
    """Expression (Destiny) Number: digit-sum reduction of every letter
    in the full birth name."""
    letters = _letters_only(full_name)
    values = [PYTHAGOREAN_MAP[ch] for ch in letters]
    total = sum(values)
    first_step = ReductionStep(input_value="+".join(str(v) for v in values), output_value=total)
    value, rest_steps = _digit_sum_reduce(total)
    steps = [first_step] + rest_steps
    return NumerologyNumber(name="Expression", value=value, is_master=value in MASTER_NUMBERS, steps=steps)


def compute_soul_urge_number(full_name: str) -> NumerologyNumber:
    """Soul Urge Number: digit-sum reduction of only the vowels in the name."""
    letters = _letters_only(full_name)
    vowel_values = [PYTHAGOREAN_MAP[ch] for ch in letters if ch in VOWELS]
    total = sum(vowel_values) if vowel_values else 0
    first_step = ReductionStep(input_value="+".join(str(v) for v in vowel_values), output_value=total)
    value, rest_steps = _digit_sum_reduce(total)
    steps = [first_step] + rest_steps
    return NumerologyNumber(name="Soul Urge", value=value, is_master=value in MASTER_NUMBERS, steps=steps)


def compute_personality_number(full_name: str) -> NumerologyNumber:
    """Personality Number: digit-sum reduction of only the consonants in the name."""
    letters = _letters_only(full_name)
    consonant_values = [PYTHAGOREAN_MAP[ch] for ch in letters if ch not in VOWELS]
    total = sum(consonant_values) if consonant_values else 0
    first_step = ReductionStep(input_value="+".join(str(v) for v in consonant_values), output_value=total)
    value, rest_steps = _digit_sum_reduce(total)
    steps = [first_step] + rest_steps
    return NumerologyNumber(name="Personality", value=value, is_master=value in MASTER_NUMBERS, steps=steps)


def compute_personal_year_number(birth_date: date, target_year: int) -> NumerologyNumber:
    """Personal Year Number: birth day + birth month + the target year,
    reduced. Used for yearly forecasting."""
    digits = [int(d) for d in f"{birth_date.day}{birth_date.month}{target_year}"]
    total = sum(digits)
    first_step = ReductionStep(input_value="+".join(str(d) for d in digits), output_value=total)
    # Personal Year conventionally reduces all the way down, master numbers included
    value, rest_steps = _digit_sum_reduce(total, allow_master=False)
    steps = [first_step] + rest_steps
    return NumerologyNumber(name="Personal Year", value=value, is_master=False, steps=steps)


@dataclass
class NumerologyProfile:
    life_path: NumerologyNumber
    expression: NumerologyNumber
    soul_urge: NumerologyNumber
    personality: NumerologyNumber
    personal_year: NumerologyNumber


@dataclass
class DayForecast:
    day: int
    personal_day: int
    quality: str     # "excellent" | "good" | "challenging" | "neutral"
    theme: str


PERSONAL_DAY_THEMES = {
    1: ("New beginnings, leadership, solo action", "excellent"),
    2: ("Partnership, patience, cooperation", "good"),
    3: ("Creativity, communication, social connections", "excellent"),
    4: ("Work, discipline, practical tasks", "good"),
    5: ("Change, travel, freedom, variety", "neutral"),
    6: ("Home, responsibility, nurturing", "good"),
    7: ("Reflection, study, spiritual insight", "neutral"),
    8: ("Ambition, finance, power moves", "excellent"),
    9: ("Completion, release, service to others", "neutral"),
    11: ("Intuition, inspiration, spiritual awareness", "excellent"),
    22: ("Large-scale achievement, master building", "excellent"),
    33: ("Compassion, teaching, healing", "excellent"),
}


def compute_best_days(birth_date: date, year: int, month: int) -> list[DayForecast]:
    """Personal Day Number = Personal Year + current month + current day,
    all reduced. Best days are those where the Personal Day is 1, 3, or 8.
    Challenging days are 4 and 7 (restraint/isolation energy)."""
    import calendar
    _, days_in_month = calendar.monthrange(year, month)

    personal_year = compute_personal_year_number(birth_date, year)

    forecasts: list[DayForecast] = []
    for day in range(1, days_in_month + 1):
        raw = personal_year.value + month + day
        pd_val, _ = _digit_sum_reduce(raw, allow_master=True)
        theme, quality = PERSONAL_DAY_THEMES.get(pd_val, ("General flow", "neutral"))
        forecasts.append(DayForecast(day=day, personal_day=pd_val, quality=quality, theme=theme))

    return forecasts


def compute_numerology_profile(full_name: str, birth_date: date, target_year: int) -> NumerologyProfile:
    return NumerologyProfile(
        life_path=compute_life_path(birth_date),
        expression=compute_expression_number(full_name),
        soul_urge=compute_soul_urge_number(full_name),
        personality=compute_personality_number(full_name),
        personal_year=compute_personal_year_number(birth_date, target_year),
    )
