from fpl_toolkit.intelligence import attach_intelligence


def _fixtures(difficulty=3):
    return [{"gameweek": gw, "matches": [{"difficulty": difficulty}]} for gw in range(1, 5)]


def test_partial_season_rate_is_not_crushed_by_raw_total():
    players = [
        {
            "player_id": 1,
            "player": "Partial Upside",
            "position": "MID",
            "total_points": 82,
            "minutes": 900,
            "starts": 10,
            "goals_scored": 6,
            "assists": 4,
            "expected_goal_involvements": "9.0",
            "chance_next_round": 100,
            "fixtures": _fixtures(3),
        },
        {
            "player_id": 2,
            "player": "Full Season Floor",
            "position": "MID",
            "total_points": 125,
            "minutes": 2700,
            "starts": 30,
            "goals_scored": 3,
            "assists": 4,
            "expected_goal_involvements": "6.0",
            "chance_next_round": 100,
            "fixtures": _fixtures(3),
        },
        {
            "player_id": 3,
            "player": "Low Rate",
            "position": "MID",
            "total_points": 90,
            "minutes": 2700,
            "starts": 30,
            "goals_scored": 1,
            "assists": 2,
            "expected_goal_involvements": "3.0",
            "chance_next_round": 100,
            "fixtures": _fixtures(3),
        },
    ]
    enriched = attach_intelligence(players)
    by_name = {row["player"]: row["intelligence"] for row in enriched}
    partial = by_name["Partial Upside"]
    full = by_name["Full Season Floor"]
    assert partial["points_per_90"] > full["points_per_90"]
    assert partial["upside_score"] > full["upside_score"]
    assert partial["baseline_score"] > by_name["Low Rate"]["baseline_score"]


def test_floor_and_upside_are_separate_dimensions():
    players = [
        {
            "player_id": 1,
            "player": "Reliable",
            "position": "MID",
            "total_points": 130,
            "minutes": 2800,
            "starts": 32,
            "goals_scored": 2,
            "assists": 5,
            "chance_next_round": 100,
            "fixtures": _fixtures(3),
        },
        {
            "player_id": 2,
            "player": "Explosive",
            "position": "MID",
            "total_points": 85,
            "minutes": 1050,
            "starts": 12,
            "goals_scored": 7,
            "assists": 4,
            "chance_next_round": 100,
            "fixtures": _fixtures(2),
        },
    ]
    enriched = attach_intelligence(players)
    by_name = {row["player"]: row["intelligence"] for row in enriched}
    assert by_name["Explosive"]["upside_score"] > by_name["Reliable"]["upside_score"]
    assert by_name["Reliable"]["sample_confidence"] > by_name["Explosive"]["sample_confidence"]
