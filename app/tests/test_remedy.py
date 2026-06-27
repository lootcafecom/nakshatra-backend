"""
Tests for the remedy/gemstone engine.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from app.vedic import compute_birth_chart
from app.remedy import (
    compute_remedy_profile, GEMSTONES, MANTRAS, CHARITY,
    EXALTATION_SIGN, DEBILITATION_SIGN, DUSTHANA_HOUSES,
)


class TestLookupTablesComplete:
    def test_all_nine_planets_have_gemstones(self):
        expected = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"}
        assert set(GEMSTONES.keys()) == expected

    def test_all_nine_planets_have_mantras(self):
        expected = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"}
        assert set(MANTRAS.keys()) == expected

    def test_all_nine_planets_have_charity(self):
        expected = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"}
        assert set(CHARITY.keys()) == expected

    def test_seven_classical_planets_have_exaltation_debilitation(self):
        seven = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"}
        assert set(EXALTATION_SIGN.keys()) == seven
        assert set(DEBILITATION_SIGN.keys()) == seven

    def test_dusthana_houses_are_6_8_12(self):
        assert DUSTHANA_HOUSES == {6, 8, 12}


class TestRemedyProfileGeneration:
    def test_rahu_and_ketu_always_included(self):
        chart = compute_birth_chart("1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata")
        profile = compute_remedy_profile("Test", chart)
        flagged = {c.planet for c in profile.concerns}
        assert "Rahu" in flagged
        assert "Ketu" in flagged

    def test_rahu_ketu_reason_does_not_claim_meaningless_retrograde(self):
        chart = compute_birth_chart("1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata")
        profile = compute_remedy_profile("Test", chart)
        rahu_concern = next(c for c in profile.concerns if c.planet == "Rahu")
        assert rahu_concern.is_retrograde is False

    def test_every_concern_has_full_remedy_data(self):
        chart = compute_birth_chart("1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata")
        profile = compute_remedy_profile("Test", chart)
        for c in profile.concerns:
            assert c.gemstone is not None
            assert c.mantra is not None
            assert c.charity is not None
            assert c.gemstone.planet == c.planet
            assert c.mantra.planet == c.planet
            assert c.charity.planet == c.planet

    def test_different_charts_produce_different_concerns(self):
        chart_a = compute_birth_chart("1990-01-01", "06:00", 28.7041, 77.1025, "Asia/Kolkata")
        chart_b = compute_birth_chart("1985-05-15", "12:00", 28.7041, 77.1025, "Asia/Kolkata")
        profile_a = compute_remedy_profile("A", chart_a)
        profile_b = compute_remedy_profile("B", chart_b)
        concerns_a = {c.planet for c in profile_a.concerns}
        concerns_b = {c.planet for c in profile_b.concerns}
        assert concerns_a != concerns_b or profile_a.strongest_planet != profile_b.strongest_planet

    def test_debilitated_planets_sorted_first(self):
        chart = compute_birth_chart("1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata")
        profile = compute_remedy_profile("Test", chart)
        debilitated_indices = [i for i, c in enumerate(profile.concerns) if c.is_debilitated]
        non_debilitated_indices = [i for i, c in enumerate(profile.concerns) if not c.is_debilitated]
        if debilitated_indices and non_debilitated_indices:
            assert max(debilitated_indices) < min(non_debilitated_indices) or not non_debilitated_indices

    def test_strongest_planet_is_none_or_valid(self):
        chart = compute_birth_chart("1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata")
        profile = compute_remedy_profile("Test", chart)
        if profile.strongest_planet is not None:
            assert profile.strongest_planet in EXALTATION_SIGN


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
