from copy import deepcopy

import pytest

from fpl_toolkit.intelligence import attach_intelligence, usage_scores
from fpl_toolkit.h2h import player_projected_points
from fpl_toolkit.outcomes import build_outcome_diagnostics


def player(player_id=1, minutes=90, starts=1, matches=1):
    return {
        "player_id": player_id, "player": "Example", "position": "MID",
        "minutes": minutes, "starts": starts, "total_points": 6,
        "chance_next_round": 100, "event_points": 9,
        "fixtures": [{"gameweek": 1, "matches": [
            {"difficulty": 3, "opponent": "TST", "venue": "H"}
            for _ in range(matches)
        ]}],
        "intelligence": {"points_per_90": 6, "expected_minutes": 90,
                         "availability_score": 100, "sample_confidence": 100},
    }


def report(gameweek=1):
    row = player()
    row["fixtures"][0]["gameweek"] = gameweek
    return {
        "current_gameweek": gameweek, "decision_gameweek": gameweek,
        "decision_gameweek_phase": "SCHEDULED", "generated_at": "2026-09-09T10:00:00Z",
        "my_squad": [row], "recommended_lineup": {"starters": [row]},
    }


def test_identical_evidence_has_identical_scores_regardless_of_ids():
    rows = attach_intelligence([player(i) for i in (1, 23, 999)], current_gameweek=3)
    assert rows[0]["intelligence"] == rows[1]["intelligence"] == rows[2]["intelligence"]
    renamed = attach_intelligence([player(i) for i in (5000, 8, 2)], current_gameweek=3)
    assert rows[0]["intelligence"] == renamed[0]["intelligence"]


def test_one_start_does_not_establish_a_certain_role():
    occasional = usage_scores(player(), current_gameweek=10)
    regular = usage_scores(player(minutes=900, starts=10), current_gameweek=10)
    assert occasional[0] < regular[0]
    assert occasional[1] < regular[1]


def test_absences_reduce_a_historical_role_even_with_zero_season_minutes():
    prior = {"minutes": 2700, "starts": 30}
    row = player(minutes=0, starts=0)
    early = usage_scores({**row, "_completed_fixture_counts": {"1": 1}}, prior, 2)
    later = usage_scores({**row, "_completed_fixture_counts": {str(i): 1 for i in range(1, 9)}}, prior, 9)
    assert later[0] < early[0]
    assert later[1] < early[1]
    assert later[1] < 30


def test_finalized_recent_role_excludes_partial_live_minutes_and_counts_doubles():
    row = {**player(), "_completed_fixture_counts": {"1": 2, "2": 0}}
    recent = {"gameweeks": [{"gameweek": 1, "minutes": 90, "starts": 1},
                            {"gameweek": 2, "minutes": 0, "starts": 0}]}
    first = usage_scores(row, current_gameweek=3, recent_match_evidence=recent)
    partial = usage_scores({**row, "minutes": 130, "starts": 2}, current_gameweek=3, recent_match_evidence=recent)
    assert first == partial
    assert first[1] == pytest.approx(52.5)  # two prior matches + two actual opportunities


def test_double_projection_sums_fixture_opportunities_and_blank_is_zero():
    single = player_projected_points(player(), 1)
    double = player_projected_points(player(matches=2), 1)
    blank = player_projected_points(player(matches=0), 1)
    assert double["projected_points"] == 2 * single["projected_points"]
    assert double["expected_gameweek_minutes"] == 180
    assert blank["projected_points"] == blank["range_low"] == blank["range_high"] == 0
    mixed = player(matches=2)
    mixed["fixtures"][0]["matches"][1]["difficulty"] = 5
    hard = player()
    hard["fixtures"][0]["matches"][0]["difficulty"] = 5
    assert player_projected_points(mixed, 1)["projected_points"] == pytest.approx(
        single["projected_points"] + player_projected_points(hard, 1)["projected_points"], abs=0.1
    )


def test_next_week_forecast_is_frozen_before_rollover():
    next_report = report(2)
    first = build_outcome_diagnostics(None, report(), "LIVE", decision_report=next_report)
    frozen = deepcopy(first["pending_forecasts"]["2"])
    next_report["my_squad"][0]["intelligence"]["points_per_90"] = 99
    repeated = build_outcome_diagnostics({"outcome_diagnostics": first}, report(), "FINAL", decision_report=next_report)
    assert repeated["pending_forecasts"]["2"] == frozen
    live = build_outcome_diagnostics({"outcome_diagnostics": repeated}, next_report, "LIVE")
    assert live["current"]["forecast"] == frozen
    assert live["current"]["forecast"]["calibration_eligible"]
    assert live["pending_forecasts"] == {}


def test_legacy_zero_forecasts_are_excluded_without_rewriting_values():
    first = build_outcome_diagnostics(None, report(), "SCHEDULED")
    forecast = first["current"]["forecast"]
    forecast.pop("model")
    forecast["recommended"]["projected_total"] = 0
    original = deepcopy(forecast["recommended"])
    first["history"] = [deepcopy(first["current"])]
    result = build_outcome_diagnostics({"outcome_diagnostics": first}, report(), "FINAL")
    assert result["current"]["forecast"]["recommended"] == original
    assert not result["current"]["evaluation"]["calibration_eligible"]
    assert not result["history"][0]["evaluation"]["calibration_eligible"]
    assert first["current"]["forecast"]["calibration_eligible"]  # inputs not mutated


def test_dropped_forecast_player_retains_actual_points_from_complete_pool():
    first = build_outcome_diagnostics(None, report(), "SCHEDULED")
    final = report()
    final["my_squad"] = []
    result = build_outcome_diagnostics({"outcome_diagnostics": first}, final, "FINAL", scoring_players=[player()])
    assert result["current"]["actual"]["recommended_points"] == 9
    missing = build_outcome_diagnostics({"outcome_diagnostics": first}, final, "FINAL", scoring_players=[])
    assert missing["current"]["actual"]["recommended_points"] is None
    assert missing["current"]["evaluation"]["recommended_absolute_error"] is None
    assert not missing["current"]["evaluation"]["calibration_eligible"]


def test_post_deadline_scheduled_capture_and_missing_fixtures_are_excluded():
    late = {**report(), "_forecast_before_deadline": False}
    assert not build_outcome_diagnostics(None, late, "SCHEDULED")["current"]["forecast"]["calibration_eligible"]
    missing = report()
    missing["my_squad"][0]["fixtures"] = []
    assert not build_outcome_diagnostics(None, missing, "SCHEDULED")["current"]["forecast"]["calibration_eligible"]
