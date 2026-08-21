from fpl_toolkit.baseline import baseline_lookup, capture_performance_baseline
from fpl_toolkit.intelligence import attach_intelligence, usage_scores


def _fixtures():
    return [{"gameweek": gw, "matches": [{"difficulty": 3}]} for gw in range(1, 5)]


def test_capture_performance_baseline_keeps_previous_season_inputs():
    players = [{
        "player_id": 7,
        "player": "Prior Player",
        "club": "TST",
        "position": "MID",
        "total_points": 120,
        "minutes": 1800,
        "starts": 20,
        "goals_scored": 6,
        "assists": 5,
        "expected_goal_involvements": "10.5",
        "points_per_game": "6.0",
        "news": "not persisted here",
    }]
    captured = capture_performance_baseline(players)
    assert captured[0]["total_points"] == 120
    assert captured[0]["minutes"] == 1800
    assert "news" not in captured[0]
    assert baseline_lookup(captured)[7]["starts"] == 20


def test_new_season_single_match_does_not_erase_prior_rate():
    prior = {
        "player_id": 1,
        "player": "Established",
        "position": "MID",
        "total_points": 180,
        "minutes": 1800,
        "starts": 20,
        "goals_scored": 8,
        "assists": 8,
        "expected_goal_involvements": "15.0",
        "points_per_game": "9.0",
    }
    current = {
        "player_id": 1,
        "player": "Established",
        "position": "MID",
        "total_points": 1,
        "minutes": 90,
        "starts": 1,
        "goals_scored": 0,
        "assists": 0,
        "expected_goal_involvements": "0.1",
        "points_per_game": "1.0",
        "chance_next_round": 100,
        "fixtures": _fixtures(),
    }
    intel = attach_intelligence(
        [current],
        performance_baseline={1: prior},
        current_gameweek=1,
    )[0]["intelligence"]
    assert intel["historical_prior_active"] is True
    assert intel["points_per_90"] > 7.0
    assert intel["role_evidence"] in {"MEDIUM", "HIGH"}


def test_preseason_uses_current_previous_season_payload_directly():
    player = {
        "player_id": 1,
        "player": "Preseason",
        "position": "FWD",
        "total_points": 100,
        "minutes": 1000,
        "starts": 12,
        "goals_scored": 7,
        "assists": 2,
        "chance_next_round": 100,
        "fixtures": _fixtures(),
    }
    intel = attach_intelligence(
        [player],
        performance_baseline={1: dict(player)},
        current_gameweek=0,
    )[0]["intelligence"]
    assert intel["historical_prior_active"] is False
    assert intel["points_per_90"] == 9.0


def test_usage_prior_shrinks_a_small_sample_toward_the_fallback():
    current = {"starts": 0, "minutes": 0, "chance_next_round": 100, "fixtures": _fixtures()}
    prior = {"starts": 3, "minutes": 270}

    start_probability, expected_minutes = usage_scores(current, prior, current_gameweek=1)

    assert 70 < start_probability < 85
    assert 60 < expected_minutes < 75


def test_active_partial_match_does_not_change_usage_estimate():
    prior = {"starts": 10, "minutes": 900}
    scheduled = {
        "starts": 0,
        "minutes": 0,
        "chance_next_round": 100,
        "fixtures": [{"gameweek": 1, "matches": [{"started": False, "finished": False}]}],
    }
    active = {
        **scheduled,
        "starts": 1,
        "minutes": 45,
        "fixtures": [{"gameweek": 1, "matches": [{"started": True, "finished": False}]}],
    }

    assert usage_scores(active, prior, current_gameweek=1) == usage_scores(scheduled, prior, current_gameweek=1)


def test_finished_first_match_blends_usage_gradually():
    prior = {"starts": 10, "minutes": 900}
    finished = {
        "starts": 1,
        "minutes": 45,
        "chance_next_round": 100,
        "fixtures": [{"gameweek": 1, "matches": [{"started": True, "finished": True}]}],
    }

    start_probability, expected_minutes = usage_scores(finished, prior, current_gameweek=1)

    assert 80 < start_probability < 100
    assert 80 < expected_minutes < 90
