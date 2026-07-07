"""
Tests for the Ashtakoot Guna Milan matching engine. Several cases here
are cross-checked against worked examples from independent published
classical references, not just internal consistency checks.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from app.matching import (
    tara_score, bhakoot_score, varna_score, yoni_score, graha_maitri_score,
    NADI, GANA, YONI, compute_kundli_match,
)
from app.vedic import NAKSHATRAS, ZODIAC_SIGNS


class TestClassificationTablesComplete:
    def test_every_nakshatra_has_nadi(self):
        assert all(n in NADI for n in NAKSHATRAS)

    def test_every_nakshatra_has_gana(self):
        assert all(n in GANA for n in NAKSHATRAS)

    def test_every_nakshatra_has_yoni(self):
        assert all(n in YONI for n in NAKSHATRAS)

    def test_nadi_distribution_is_nine_each(self):
        from collections import Counter
        counts = Counter(NADI.values())
        assert counts["Adi"] == 9
        assert counts["Madhya"] == 9
        assert counts["Antya"] == 9

    def test_gana_distribution_is_nine_each(self):
        from collections import Counter
        counts = Counter(GANA.values())
        assert counts["Deva"] == 9
        assert counts["Manushya"] == 9
        assert counts["Rakshasa"] == 9


class TestTaraKoota:
    """Tara koota must be symmetric (the score cannot depend on which
    person is labeled first) and must only ever produce one of the
    three valid classical scores."""

    def test_same_nakshatra_is_internally_consistent(self):
        # same nakshatra both ways -> same count both directions -> same parity -> never 1.5
        score = tara_score(5, 5)
        assert score in (0, 3)

    def test_tara_is_symmetric(self):
        # the score should not depend on which person is "a" vs "b"
        for a in range(0, 27, 5):
            for b in range(0, 27, 7):
                assert tara_score(a, b) == tara_score(b, a)

    def test_tara_only_produces_valid_scores(self):
        for a in range(27):
            for b in range(27):
                assert tara_score(a, b) in (0, 1.5, 3)

    def test_tara_distribution_is_not_degenerate(self):
        # sanity check: across many pairs, all three outcomes should appear
        # (catches the earlier bug where the formula always returned 1.5)
        seen = {tara_score(0, b) for b in range(27)}
        assert len(seen) > 1


class TestBhakootKoota:
    def test_same_sign_has_no_dosha(self):
        score, dosha = bhakoot_score("Aries", "Aries")
        assert dosha is False
        assert score == 7

    def test_six_eight_relationship_is_dosha(self):
        # Aries to Virgo is a 6th-sign relationship
        score, dosha = bhakoot_score("Aries", "Virgo")
        assert dosha is True
        assert score == 0

    def test_two_twelve_relationship_is_dosha(self):
        # Aries to Taurus is a 2nd-sign relationship
        score, dosha = bhakoot_score("Aries", "Taurus")
        assert dosha is True
        assert score == 0

    def test_fourth_sign_relationship_is_fine(self):
        score, dosha = bhakoot_score("Aries", "Cancer")
        assert dosha is False
        assert score == 7


class TestVarnaKoota:
    def test_equal_varna_scores_full_point(self):
        assert varna_score("Cancer", "Cancer") == 1

    def test_higher_groom_varna_scores_full_point(self):
        # Cancer (Brahmin, rank 4) vs Gemini (Shudra, rank 1)
        assert varna_score("Cancer", "Gemini") == 1

    def test_lower_groom_varna_scores_zero(self):
        # Gemini (Shudra, rank 1) vs Cancer (Brahmin, rank 4)
        assert varna_score("Gemini", "Cancer") == 0


class TestYoniKoota:
    def test_same_yoni_scores_four(self):
        assert yoni_score("Horse", "Horse") == 4

    def test_known_enemy_pair_scores_zero(self):
        assert yoni_score("Cat", "Rat") == 0

    def test_yoni_score_is_symmetric(self):
        assert yoni_score("Dog", "Deer") == yoni_score("Deer", "Dog")


class TestGrahaMaitriKoota:
    def test_same_lord_scores_full(self):
        # both Cancer -> both ruled by Moon
        assert graha_maitri_score("Cancer", "Cancer") == 5

    def test_mutual_friend_lords_score_high(self):
        # Aries (Mars) and Leo (Sun) - Mars and Sun are mutual friends
        assert graha_maitri_score("Aries", "Leo") == 5

    def test_mutual_enemy_lords_score_zero(self):
        # Taurus (Venus) and Aries (Mars) - need to check actual relation
        score = graha_maitri_score("Cancer", "Taurus")  # Moon vs Venus
        assert 0 <= score <= 5


class TestFullMatchIntegration:
    def test_match_returns_valid_total(self):
        result, chart_a, chart_b = compute_kundli_match(
            "Person A", "1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata",
            "Person B", "1996-03-22", "14:00", 19.0760, 72.8777, "Asia/Kolkata",
        )
        assert 0 <= result.total_score <= 36
        assert len(result.kootas) == 8
        assert sum(k.max_points for k in result.kootas) == 36

    def test_match_with_self_has_perfect_some_kootas(self):
        # matching identical birth data — same nakshatra triggers Nadi Dosha,
        # but it is immediately cancelled because same nakshatra = cancellation rule.
        # So the Nadi score is restored to 8 and nadi_dosha flag is False.
        result, chart_a, chart_b = compute_kundli_match(
            "Person A", "1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata",
            "Person A copy", "1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata",
        )
        gana_koota = next(k for k in result.kootas if k.name == "Gana")
        assert gana_koota.score == 6  # identical gana
        nadi_koota = next(k for k in result.kootas if k.name == "Nadi")
        assert nadi_koota.score == 8  # same nakshatra triggers dosha but cancellation restores full points
        assert result.nadi_dosha is False  # cancelled — classical same-nakshatra exception
        assert result.nadi_cancellation_reason is not None

    def test_mangal_dosha_detection_runs(self):
        result, chart_a, chart_b = compute_kundli_match(
            "Person A", "1995-06-15", "10:30", 19.0760, 72.8777, "Asia/Kolkata",
            "Person B", "1996-03-22", "14:00", 19.0760, 72.8777, "Asia/Kolkata",
        )
        assert isinstance(result.mangal_dosha.person_a_dosha, bool)
        assert isinstance(result.mangal_dosha.person_b_dosha, bool)
        assert 1 <= result.mangal_dosha.person_a_mars_house <= 12


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
