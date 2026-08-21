from fpl_toolkit.optimizer import recommend_lineup
from fpl_toolkit.privacy import sanitize_public_report


def _player(player_id, position, score, chance=100, fixture=3):
    return {
        "player_id": player_id,
        "player": f"P{player_id}",
        "position": position,
        "chance_next_round": chance,
        "fixtures": [{"gameweek": 1, "matches": [{"difficulty": fixture}]}],
        "intelligence": {
            "availability_score": chance,
            "expected_minutes": 90 if chance else 0,
            "floor_score": score,
            "upside_score": score,
            "roster_score": score,
        },
    }


def _standard_squad():
    players = [
        _player(1, "GKP", 80),
        _player(2, "GKP", 60),
    ]
    players += [_player(i, "DEF", 90 - i) for i in range(3, 8)]
    players += [_player(i, "MID", 95 - i) for i in range(8, 13)]
    players += [_player(i, "FWD", 92 - i) for i in range(13, 16)]
    return players


def test_optimizer_returns_legal_eleven_and_ordered_bench():
    result = recommend_lineup(_standard_squad(), 1)
    assert result["is_valid"] is True
    assert len(result["starters"]) == 11
    assert len(result["bench"]) == 3
    assert result["reserve_goalkeeper"]["position"] == "GKP"
    assert [row["selection"]["bench_order"] for row in result["bench"]] == [1, 2, 3]

    positions = [row["position"] for row in result["starters"]]
    assert positions.count("GKP") == 1
    assert 3 <= positions.count("DEF") <= 5
    assert 2 <= positions.count("MID") <= 5
    assert 1 <= positions.count("FWD") <= 3
    assert positions.count("DEF") + positions.count("MID") + positions.count("FWD") == 10


def test_optimizer_penalizes_unavailable_player():
    squad = _standard_squad()
    # Make one midfielder historically elite but ruled out.
    target = next(player for player in squad if player["player_id"] == 8)
    target["chance_next_round"] = 0
    target["intelligence"].update({
        "availability_score": 0,
        "expected_minutes": 0,
        "floor_score": 100,
        "upside_score": 100,
        "roster_score": 100,
    })
    result = recommend_lineup(squad, 1)
    starter_ids = {row["player_id"] for row in result["starters"]}
    assert 8 not in starter_ids


def test_optimizer_uses_next_gameweek_fixture_not_four_week_average():
    squad = _standard_squad()
    # Two comparable defenders: one has the easy immediate fixture.
    easy = next(player for player in squad if player["player_id"] == 6)
    hard = next(player for player in squad if player["player_id"] == 7)
    easy["intelligence"].update({"floor_score": 60, "upside_score": 60, "roster_score": 60})
    hard["intelligence"].update({"floor_score": 60, "upside_score": 60, "roster_score": 60})
    easy["fixtures"] = [{"gameweek": 1, "matches": [{"difficulty": 1}]}]
    hard["fixtures"] = [{"gameweek": 1, "matches": [{"difficulty": 5}]}]
    result = recommend_lineup(squad, 1)
    scores = result["player_scores"]
    assert scores["6"]["start_score"] > scores["7"]["start_score"]


def test_optimizer_returns_invalid_for_incomplete_squad_shape():
    result = recommend_lineup([_player(1, "GKP", 80), _player(2, "DEF", 80)], 1)
    assert result["is_valid"] is False
    assert result["starters"] == []


def test_recommended_lineup_is_redacted_for_public_report():
    squad = _standard_squad()
    for player in squad:
        player["owner_name"] = "Private"
        player["owner_entry_id"] = 336654
    recommended = recommend_lineup(squad, 1)
    public = sanitize_public_report({
        "my_squad": [],
        "available_players": [],
        "injury_watch": [],
        "league_activity": [],
        "recommended_lineup": recommended,
    })
    assert "owner_name" not in public["recommended_lineup"]["starters"][0]
    assert "owner_entry_id" not in public["recommended_lineup"]["bench"][0]
    assert "owner_name" not in public["recommended_lineup"]["reserve_goalkeeper"]
