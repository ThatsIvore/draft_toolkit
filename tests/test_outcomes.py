from fpl_toolkit.outcomes import build_outcome_diagnostics, gameweek_phase


def _report(phase="SCHEDULED", points=0, h2h_points=(0, 0)):
    player = {
        "player_id": 1,
        "player": "Alpha",
        "position": "MID",
        "event_points": points,
        "chance_next_round": 100,
        "fixtures": [{"gameweek": 1, "matches": [{"opponent": "OPP", "venue": "H", "difficulty": 3}]}],
        "intelligence": {
            "points_per_90": 6,
            "expected_minutes": 90,
            "availability_score": 100,
            "sample_confidence": 100,
            "role_evidence": "HIGH",
            "floor_score": 70,
            "upside_score": 70,
        },
    }
    return {
        "generated_at": "2026-08-21T10:00:00+00:00",
        "current_gameweek": 1,
        "my_squad": [player],
        "lineup": {"is_exact": True, "event_points_total": points, "starters": [player], "bench": []},
        "recommended_lineup": {"formation": "3-5-2", "starters": [player]},
        "h2h_matchup": {
            "result": {"status": phase, "my_points": h2h_points[0], "opponent_points": h2h_points[1]},
            "matchup": {
                "signal": "EDGE",
                "projected_points_edge": 4.0,
                "my": {"projection": {"total": 6.0, "range_low": 4.0, "range_high": 8.0, "players": [
                    {"player_id": 1, "player": "Alpha", "position": "MID", "projected_points": 6.0, "range_low": 4.0, "range_high": 8.0}
                ]}},
                "opponent": {"projection": {"total": 2.0}},
            },
        },
    }


def test_gameweek_phase_covers_scheduled_live_and_final():
    assert gameweek_phase([{"event": 1, "started": False, "finished": False}], 1) == "SCHEDULED"
    assert gameweek_phase([{"event": 1, "started": True, "finished": False}], 1) == "LIVE"
    assert gameweek_phase([{"event": 1, "started": True, "finished": True}], 1) == "FINAL"


def test_pre_gameweek_forecast_is_frozen_during_live_play():
    scheduled = build_outcome_diagnostics(None, _report(), "SCHEDULED")
    previous_state = {"outcome_diagnostics": scheduled}
    live_report = _report("LIVE", points=10, h2h_points=(10, 3))
    live_report["h2h_matchup"]["matchup"]["my"]["projection"]["total"] = 99.0

    live = build_outcome_diagnostics(previous_state, live_report, "LIVE")

    assert live["current"]["forecast"]["recommended"]["projected_total"] == 6.0
    assert live["current"]["forecast"]["calibration_eligible"] is True
    assert live["current"]["actual"]["recommended_points"] == 10.0
    assert live["current"]["evaluation"]["complete"] is False


def test_final_result_evaluates_the_frozen_forecast():
    scheduled = build_outcome_diagnostics(None, _report(), "SCHEDULED")
    final = build_outcome_diagnostics(
        {"outcome_diagnostics": scheduled},
        _report("FINAL", points=9, h2h_points=(9, 5)),
        "FINAL",
    )

    current = final["current"]
    assert current["actual"]["official_points"] == 9.0
    assert current["actual"]["h2h_result"] == "WIN"
    assert current["evaluation"]["recommended_absolute_error"] == 3.0
    assert current["evaluation"]["h2h_result_correct"] is True


def test_mid_gameweek_first_capture_is_not_a_calibration_sample():
    diagnostics = build_outcome_diagnostics(None, _report("LIVE", points=4), "LIVE")

    assert diagnostics["current"]["forecast"]["calibration_eligible"] is False
    assert "excluded" in diagnostics["note"]


def test_zero_zero_live_league_score_uses_a_labelled_lineup_estimate():
    report = _report("LIVE", points=7, h2h_points=(0, 0))
    report["h2h_matchup"]["opponent_lineup"] = {
        "starters": [{"player_id": 99, "event_points": 4}]
    }

    diagnostics = build_outcome_diagnostics(None, report, "LIVE")
    actual = diagnostics["current"]["actual"]

    assert actual["h2h_my_points"] == 7.0
    assert actual["h2h_opponent_points"] == 4.0
    assert actual["h2h_result"] == "WIN"
    assert actual["h2h_score_source"] == "estimated_lineups"
