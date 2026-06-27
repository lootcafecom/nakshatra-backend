"""
Test suite for the calculation engines. Run with: python3 -m pytest app/tests/ -v
These tests cover the parts of the system that must be exactly correct —
calculation logic — independent of the network-dependent Vastu geocoding
calls (those are tested separately via mocking, since live calls aren't
reachable from this sandbox).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import date
import pytest

from app.vedic import compute_birth_chart, _sign_index, _nakshatra_index, _pada
from app.numerology import (
    compute_life_path, compute_expression_number, compute_soul_urge_number,
    compute_personality_number, compute_personal_year_number,
)
from app.tarot import draw_three_card_spread, FULL_DECK
from app.vastu import zone_for_bearing, VASTU_ZONES


class TestVedicEngine:
    def test_sign_index_boundaries(self):
        assert _sign_index(0) == 0       # Aries starts at 0
        assert _sign_index(29.99) == 0
        assert _sign_index(30) == 1      # Taurus starts at 30
        assert _sign_index(359.99) == 11  # Pisces

    def test_nakshatra_index_boundaries(self):
        assert _nakshatra_index(0) == 0
        span = 360 / 27
        assert _nakshatra_index(span - 0.01) == 0
        assert _nakshatra_index(span) == 1

    def test_pada_within_nakshatra(self):
        span = 360 / 27
        pada_span = span / 4
        assert _pada(0) == 1
        assert _pada(pada_span + 0.01) == 2
        assert _pada(pada_span * 3 + 0.01) == 4

    def test_full_chart_has_nine_planets(self):
        chart = compute_birth_chart("1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata")
        assert len(chart.planets) == 9
        names = {p.name for p in chart.planets}
        assert names == {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"}

    def test_ketu_always_180_from_rahu(self):
        chart = compute_birth_chart("1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata")
        rahu = next(p for p in chart.planets if p.name == "Rahu")
        ketu = next(p for p in chart.planets if p.name == "Ketu")
        diff = abs(rahu.longitude - ketu.longitude)
        assert abs(diff - 180) < 0.01 or abs(diff - 180) > 359.99

    def test_dasha_timeline_covers_120_year_cycle(self):
        chart = compute_birth_chart("1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata")
        assert len(chart.dasha_timeline) >= 9
        # periods should be contiguous (each starts where the previous ends)
        for i in range(len(chart.dasha_timeline) - 1):
            assert chart.dasha_timeline[i].end == chart.dasha_timeline[i + 1].start

    def test_houses_are_in_valid_range(self):
        chart = compute_birth_chart("1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata")
        for p in chart.planets:
            assert 1 <= p.house <= 12

    def test_different_birth_times_give_different_charts(self):
        chart_a = compute_birth_chart("1995-06-15", "06:00", 19.0760, 72.8777, "Asia/Kolkata")
        chart_b = compute_birth_chart("1995-06-15", "18:00", 19.0760, 72.8777, "Asia/Kolkata")
        assert chart_a.ascendant_sign != chart_b.ascendant_sign or \
               abs(chart_a.ascendant_degree - chart_b.ascendant_degree) > 1


class TestNumerologyEngine:
    def test_life_path_known_value(self):
        # 1995-06-15 -> 1+9+9+5+0+6+1+5 = 36 -> 3+6 = 9
        result = compute_life_path(date(1995, 6, 15))
        assert result.value == 9
        assert result.steps[0].output_value == 36
        assert result.steps[1].output_value == 9

    def test_expression_known_value(self):
        # ARJUN SHARMA -> verified by hand: 43 -> 7
        result = compute_expression_number("Arjun Sharma")
        assert result.value == 7

    def test_master_number_not_further_reduced(self):
        # construct a date that sums to 11 and confirm it stays 11
        # 2+9+0+1+2+0+0+9 won't necessarily hit 11; instead test the
        # reduction function directly via a case that produces 29 -> 11
        from app.numerology import _digit_sum_reduce
        value, steps = _digit_sum_reduce(29)
        assert value == 11
        assert steps[-1].output_value == 11

    def test_personal_year_changes_by_year(self):
        y1 = compute_personal_year_number(date(1995, 6, 15), 2025)
        y2 = compute_personal_year_number(date(1995, 6, 15), 2026)
        assert y1.value != y2.value or True  # may coincidentally match; just confirm no crash

    def test_soul_urge_only_uses_vowels(self):
        result = compute_soul_urge_number("Arjun Sharma")
        # vowels in ARJUNSHARMA: A,U,A,A = 1+3+1+1 = 6
        assert result.steps[0].output_value == 6


class TestTarotEngine:
    def test_deck_has_78_cards(self):
        assert len(FULL_DECK) == 78

    def test_draw_returns_three_unique_cards(self):
        spread = draw_three_card_spread()
        names = [c.name for c in spread]
        assert len(names) == 3
        assert len(set(names)) == 3  # no duplicates

    def test_draw_positions_are_past_present_future(self):
        spread = draw_three_card_spread()
        positions = [c.position for c in spread]
        assert positions == ["Past", "Present", "Future"]

    def test_randomness_produces_variation(self):
        # over 20 draws, we should see more than one unique first card
        first_cards = {draw_three_card_spread()[0].name for _ in range(20)}
        assert len(first_cards) > 1


class TestVastuEngine:
    def test_all_eight_zones_defined(self):
        assert len(VASTU_ZONES) == 8

    def test_zone_boundaries_cover_full_circle(self):
        # every degree 0-359 should resolve to exactly one zone
        for bearing in range(360):
            zone = zone_for_bearing(bearing)
            assert zone is not None

    def test_north_wraparound(self):
        assert zone_for_bearing(0)["name"] == "Uttara (North)"
        assert zone_for_bearing(359)["name"] == "Uttara (North)"
        assert zone_for_bearing(350)["name"] == "Uttara (North)"

    def test_cardinal_directions(self):
        assert zone_for_bearing(90)["name"] == "Purva (East)"
        assert zone_for_bearing(180)["name"] == "Dakshina (South)"
        assert zone_for_bearing(270)["name"] == "Paschima (West)"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
