from fpl_toolkit.h2h import build_h2h_matchup, player_projected_points


POSITIONS = ["GKP", "GKP"] + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3


def _player(player_id, position, owner_raw, owner_entry_id, base, difficulty):
    return {
        "player_id": player_id,
        "player": f"P{player_id}",
        "position": position,
        "club": "TST",
        "team_code": 1,
        "owner_raw": owner_raw,
        "owner_entry_id": owner_entry_id,
        "chance_next_round": 100,
        "fixtures": [
            {
                "gameweek": 1,
                "matches": [
                    {
                        "opponent": "OPP",
                        "venue": "H",
                        "difficulty": difficulty,
                    }
                ],
            }
        ],
        "intelligence": {
            "availability_score": 100,
            "expected_minutes": 90,
            "floor_score": base,
            "upside_score": base,
            "roster_score": base,
            "sample_confidence": 100,
            "role_evidence": "HIGH",
            "points_per_90": base / 18.0,
        },
    }


def _squad(start_id, owner_raw, owner_entry_id, base, difficulty):
    return [
        _player(start_id + index, position, owner_raw, owner_entry_id, base, difficulty)
        for index, position in enumerate(POSITIONS)
    ]


def _league():
    return {
        "league_entries": [
            {"id": 501, "entry_id": 336654, "entry_name": "Mine"},
            {"id": 502, "entry_id": 888888, "entry_name": "Opponent XI"},
        ],
        "matches": [
            {
                "event": 1,
                "league_entry_1": 501,
                "league_entry_2": 502,
                "league_entry_1_points": 0,
                "league_entry_2_points": 0,
                "finished": False,
            }
        ],
        "standings": [
            {"league_entry": 501, "rank": 2, "total": 0, "points_for": 0},
            {"league_entry": 502, "rank": 4, "total": 0, "points_for": 0},
        ],
    }


def test_player_projection_uses_points_minutes_fixture_and_evidence():
    player = _player(1, "MID", 501, 336654, 90, 2)
    projection = player_projected_points(player, 1)

    assert projection["projected_points"] > 0
    assert projection["range_low"] < projection["projected_points"] < projection["range_high"]
    assert projection["expected_minutes"] == 90
    assert projection["role_evidence"] == "HIGH"


def test_builds_scouting_h2h_matchup_from_league_match_and_ownership():
    mine = _squad(1, 501, 336654, 85, 2)
    opponent = _squad(101, 502, 888888, 70, 4)
    result = build_h2h_matchup(
        _league(),
        "336654",
        mine,
        mine + opponent,
        [],
        1,
    )

    assert result["available"] is True
    assert result["model"] == "v1.0"
    assert result["gameweek"] == 1
    assert result["result"] == {"status": "SCHEDULED", "source": "league_details", "my_points": 0.0, "opponent_points": 0.0, "finished": False}
    assert result["opponent"]["display_name"] == "Opponent XI"
    assert result["opponent"]["league_entry_id"] == "502"
    assert len(result["opponent_squad"]) == 15
    assert result["my_lineup"]["is_valid"] is True
    assert result["opponent_lineup"]["is_valid"] is True
    assert result["matchup"]["signal"] == "EDGE"
    assert result["matchup"]["start_score_edge"] > 0
    assert result["matchup"]["projected_points_edge"] > 0
    assert result["matchup"]["my"]["projection"]["total"] > result["matchup"]["opponent"]["projection"]["total"]
    assert result["matchup"]["pressure"]["level"] == "LOW"
    assert len(result["matchup"]["position_edges"]) == 4
    assert len(result["opponent_threats"]) == 3
    assert result["scouting"]["opponent"]["strongest_group"] in {"GKP", "DEF", "MID", "FWD"}
    assert result["scouting"]["opponent"]["weakest_starter"] is not None
    assert result["tactical_priorities"][0]["action"] == "HOLD SHAPE"


def test_scout_simulates_supported_free_agent_move_when_trailing():
    mine = _squad(1, 501, 336654, 62, 4)
    opponent = _squad(101, 502, 888888, 86, 2)
    candidate = _player(999, "FWD", None, None, 96, 1)
    candidate["replacement"] = {
        "action": "CONSIDER",
        "drop_player_id": 13,
        "drop_player": "P13",
        "combined_delta": 20.0,
    }

    result = build_h2h_matchup(
        _league(),
        "336654",
        mine,
        mine + opponent + [candidate],
        [candidate],
        1,
    )

    move = result["scouting"]["best_matchup_move"]
    assert result["available"] is True
    assert result["matchup"]["projected_points_edge"] < 0
    assert result["matchup"]["pressure"]["level"] in {"HIGH", "VERY HIGH"}
    assert move is not None
    assert move["add_player_id"] == 999
    assert move["drop_player_id"] == 13
    assert move["projected_points_delta"] > 0
    assert move["roster_value_delta"] > 0
    assert any(priority.get("counter") for priority in result["tactical_priorities"])


def test_h2h_refuses_incomplete_opponent_ownership():
    mine = _squad(1, 501, 336654, 85, 2)
    opponent = _squad(101, 502, 888888, 70, 4)[:10]
    result = build_h2h_matchup(
        _league(),
        "336654",
        mine,
        mine + opponent,
        [],
        1,
    )

    assert result["available"] is False
    assert result["model"] == "v1.0"
    assert "ownership resolved to only 10 players" in result["reason"]
