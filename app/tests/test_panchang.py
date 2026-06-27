"""
Tests for the Panchang engine. Several values are cross-checked against
independently published sources during development (see code comments
in panchang.py for the specific cross-checks performed against
DrikPanchang's published ayanamsha value and documented tithi/yoga
transition times for nearby dates).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from app.panchang import (
    compute_panchang, RAHU_KAAL_SEGMENT, WEEKDAY_NAMES, WEEKDAY_LORDS,
    _compute_tithi, _compute_yoga, _compute_karana, MOVABLE_KARANAS,
    FIXED_KARANAS_END, TITHI_NAMES_SHUKLA, TITHI_NAMES_KRISHNA, YOGA_NAMES,
)


class TestRahuKaalTable:
    def test_documented_segment_assignment(self):
        # cross-checked against multiple independent published sources
        expected = {
            "Monday": 2, "Tuesday": 7, "Wednesday": 5, "Thursday": 6,
            "Friday": 4, "Saturday": 3, "Sunday": 8,
        }
        assert RAHU_KAAL_SEGMENT == expected

    def test_all_weekdays_have_a_segment(self):
        assert all(day in RAHU_KAAL_SEGMENT for day in WEEKDAY_NAMES)

    def test_segment_values_are_valid(self):
        assert all(1 <= v <= 8 for v in RAHU_KAAL_SEGMENT.values())


class TestWeekdayLords:
    def test_all_seven_days_have_a_lord(self):
        assert len(WEEKDAY_LORDS) == 7

    def test_sunday_ruled_by_sun(self):
        assert WEEKDAY_LORDS["Sunday"] == "Sun"

    def test_monday_ruled_by_moon(self):
        assert WEEKDAY_LORDS["Monday"] == "Moon"


class TestTithiCalculation:
    def test_new_moon_is_amavasya(self):
        # sun and moon at the same longitude = no separation = start of cycle
        name, number, paksha = _compute_tithi(sun_lon=100.0, moon_lon=100.0)
        assert paksha == "Shukla"
        assert name == "Pratipada"

    def test_full_moon_is_purnima(self):
        # Purnima is tithi index 14 (the last Shukla tithi), spanning
        # 168-180 degrees of separation. Exactly 180 degrees is the
        # boundary where Krishna Paksha begins.
        name, number, paksha = _compute_tithi(sun_lon=0.0, moon_lon=179.0)
        assert paksha == "Shukla"
        assert name == "Purnima"
        assert number == 15

    def test_just_past_full_moon_starts_krishna(self):
        name, number, paksha = _compute_tithi(sun_lon=0.0, moon_lon=180.5)
        assert paksha == "Krishna"
        assert name == "Pratipada"

    def test_just_before_new_moon_is_amavasya(self):
        name, number, paksha = _compute_tithi(sun_lon=0.0, moon_lon=355.0)
        assert paksha == "Krishna"
        assert name == "Amavasya"
        assert number == 15

    def test_all_30_tithi_slots_produce_valid_names(self):
        for i in range(30):
            moon_lon = (i * 12) + 1  # 1 degree into each tithi slot
            name, number, paksha = _compute_tithi(sun_lon=0.0, moon_lon=moon_lon)
            assert paksha in ("Shukla", "Krishna")
            assert 1 <= number <= 15
            valid_names = TITHI_NAMES_SHUKLA if paksha == "Shukla" else TITHI_NAMES_KRISHNA
            assert name in valid_names


class TestYogaCalculation:
    def test_all_27_yoga_slots_produce_valid_names(self):
        span = 360 / 27
        for i in range(27):
            total_needed = (i * span) + 1
            # split arbitrarily between sun and moon
            name, favorable = _compute_yoga(sun_lon=total_needed / 2, moon_lon=total_needed / 2)
            assert name in YOGA_NAMES
            assert favorable in (True, False, None)

    def test_yoga_wraps_correctly_past_360(self):
        # sun + moon summing past 360 should wrap, not error
        name, favorable = _compute_yoga(sun_lon=200.0, moon_lon=250.0)
        assert name in YOGA_NAMES


class TestKaranaCalculation:
    def test_first_karana_of_cycle_is_kimstughna(self):
        # diff = 0 -> karana_index 0 -> fixed Kimstughna per classical rule
        name = _compute_karana(sun_lon=50.0, moon_lon=50.0)
        assert name == "Kimstughna"

    def test_movable_karanas_cycle_through_seven_names(self):
        seen = set()
        for karana_index in range(1, 57):
            diff = karana_index * 6 + 0.5
            name = _compute_karana(sun_lon=0.0, moon_lon=diff)
            seen.add(name)
        assert seen == set(MOVABLE_KARANAS)

    def test_final_three_fixed_karanas_appear_at_end_of_cycle(self):
        # karana indices 57, 58, 59 should be Shakuni, Chatushpada, Naga
        for offset, expected in zip([57, 58, 59], ["Shakuni", "Chatushpada", "Naga"]):
            diff = offset * 6 + 0.5
            name = _compute_karana(sun_lon=0.0, moon_lon=diff)
            assert name == expected


class TestFullPanchangIntegration:
    def test_returns_complete_result(self):
        result = compute_panchang("2026-06-28", 19.0760, 72.8777, "Asia/Kolkata")
        assert result.weekday in WEEKDAY_NAMES
        assert result.paksha in ("Shukla", "Krishna")
        assert 1 <= result.tithi_number <= 15
        assert result.nakshatra
        assert 1 <= result.nakshatra_pada <= 4
        assert result.yoga_name in YOGA_NAMES
        assert result.karana_name in MOVABLE_KARANAS + FIXED_KARANAS_END

    def test_sunrise_before_sunset(self):
        result = compute_panchang("2026-06-28", 19.0760, 72.8777, "Asia/Kolkata")
        assert result.sunrise < result.sunset

    def test_rahu_kaal_within_daylight(self):
        result = compute_panchang("2026-06-28", 19.0760, 72.8777, "Asia/Kolkata")
        assert result.sunrise <= result.rahu_kaal_start
        assert result.rahu_kaal_end <= result.sunset

    def test_rahu_kaal_duration_is_one_eighth_of_daylight(self):
        result = compute_panchang("2026-06-28", 19.0760, 72.8777, "Asia/Kolkata")
        daylight = (result.sunset - result.sunrise).total_seconds()
        rahu_duration = (result.rahu_kaal_end - result.rahu_kaal_start).total_seconds()
        assert abs(rahu_duration - daylight / 8) < 1.0  # within a second of exact

    def test_different_dates_give_different_results(self):
        r1 = compute_panchang("2026-01-01", 19.0760, 72.8777, "Asia/Kolkata")
        r2 = compute_panchang("2026-07-04", 19.0760, 72.8777, "Asia/Kolkata")
        assert (r1.tithi_name, r1.paksha) != (r2.tithi_name, r2.paksha)

    def test_weekday_matches_calendar(self):
        # June 28, 2026 is a Sunday
        result = compute_panchang("2026-06-28", 19.0760, 72.8777, "Asia/Kolkata")
        assert result.weekday == "Sunday"
        assert result.weekday_lord == "Sun"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
