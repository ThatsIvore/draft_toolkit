from fpl_toolkit.baseline import baseline_lookup, capture_performance_baseline
from fpl_toolkit.intelligence import attach_intelligence


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
