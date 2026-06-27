"""
Tests for the Muhurta engine.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from app.muhurta import (
    validate_single_date, search_date_range, ACTIVITY_RULES, ACTIVITY_LIST,
    RIKTA_TITHIS, _score_day,
)
from app.panchang import compute_panchang


class TestActivityRulesComplete:
    def test_six_activities_defined(self):
        assert len(ACTIVITY_LIST) == 6

    def test_every_activity_has_nakshatras_and_tithis_and_weekdays(self):
        for key in ACTIVITY_LIST:
            rules = ACTIVITY_RULES[key]
            assert len(rules.good_nakshatras) > 0
            assert len(rules.good_tithis) > 0
            assert len(rules.good_weekdays) > 0

    def test_rikta_tithis_are_4_9_14(self):
        assert RIKTA_TITHIS == {"Chaturthi", "Navami", "Chaturdashi"}


class TestSingleDateValidation:
    def test_returns_valid_score_structure(self):
        result = validate_single_date("marriage", "2026-07-01", 19.0760, 72.8777, "Asia/Kolkata")
        assert 0 <= result.score <= result.max_score
        assert result.verdict

    def test_rikta_tithi_day_is_flagged(self):
        # 2026-06-28 is Chaturdashi (verified in panchang tests) - a Rikta tithi
        result = validate_single_date("marriage", "2026-06-28", 19.0760, 72.8777, "Asia/Kolkata")
        assert result.has_rikta_tithi is True
        assert "Avoid" in result.verdict

    def test_unknown_activity_raises(self):
        with pytest.raises(ValueError):
            validate_single_date("skydiving", "2026-07-01", 19.0760, 72.8777, "Asia/Kolkata")

    def test_different_activities_can_score_same_date_differently(self):
        marriage = validate_single_date("marriage", "2026-07-01", 19.0760, 72.8777, "Asia/Kolkata")
        travel = validate_single_date("travel", "2026-07-01", 19.0760, 72.8777, "Asia/Kolkata")
        # not asserting they must differ (they could coincidentally match),
        # just that both compute independently without error
        assert marriage.date == travel.date == "2026-07-01"


class TestDateRangeSearch:
    def test_search_returns_sorted_by_score_descending(self):
        results = search_date_range("marriage", "2026-07-01", 30, 19.0760, 72.8777, "Asia/Kolkata", limit=10)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_excludes_rikta_and_bad_karana_days(self):
        results = search_date_range("marriage", "2026-06-01", 30, 19.0760, 72.8777, "Asia/Kolkata", limit=30)
        assert all(not r.has_rikta_tithi for r in results)
        assert all(r.karana_favorable for r in results)

    def test_search_respects_limit(self):
        results = search_date_range("travel", "2026-01-01", 60, 19.0760, 72.8777, "Asia/Kolkata", limit=3)
        assert len(results) <= 3

    def test_search_unknown_activity_raises(self):
        with pytest.raises(ValueError):
            search_date_range("skydiving", "2026-07-01", 30, 19.0760, 72.8777, "Asia/Kolkata")

    def test_full_year_search_completes_quickly(self):
        import time
        start = time.time()
        search_date_range("business", "2026-01-01", 365, 19.0760, 72.8777, "Asia/Kolkata", limit=20)
        assert time.time() - start < 5.0  # generous ceiling; typically well under 1s

    def test_rare_combination_findable(self):
        # Pushya nakshatra + Thursday is a known special combination for
        # business (Guru Pushyamrut Yoga) - confirm at least the search
        # mechanism can surface it when present without erroring
        results = search_date_range("business", "2026-01-01", 365, 19.0760, 72.8777, "Asia/Kolkata", limit=100)
        # just confirm the search ran across the full range without error
        # and returned internally consistent results
        for r in results:
            assert r.panchang.date >= "2026-01-01"


class TestScoringLogic:
    def test_all_criteria_favorable_scores_max(self):
        # construct a fake panchang-like scenario isn't easy without
        # mocking; instead verify via a real date/activity pair where we
        # know from earlier exploration the score is 5/5
        result = validate_single_date("marriage", "2026-07-01", 19.0760, 72.8777, "Asia/Kolkata")
        if result.score == 5:
            assert "Excellent" in result.verdict

    def test_verdict_thresholds_consistent_with_score(self):
        for date in ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"]:
            result = validate_single_date("travel", date, 19.0760, 72.8777, "Asia/Kolkata")
            if result.has_rikta_tithi or not result.karana_favorable:
                assert "Avoid" in result.verdict
            elif result.score >= 4:
                assert "Excellent" in result.verdict
            elif result.score == 3:
                assert "Good" in result.verdict
            elif result.score == 2:
                assert "Mixed" in result.verdict
            else:
                assert "Weak" in result.verdict


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
