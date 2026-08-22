from fpl_toolkit.h2h import build_h2h_matchup, build_h2h_outlook, player_projected_points


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
                "gameweek": gameweek,
                "matches": [
                    {
                        "opponent": "OPP",
                        "venue": "H",
                        "difficulty": difficulty,
                    }
                ],
            }
            for gameweek in range(1, 5)
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


def test_h2h_embeds_the_opponent_decision_profile_without_changing_current_projection():
    mine = _squad(1, 501, 336654, 85, 2)
    opponent = _squad(101, 502, 888888, 70, 4)
    profile = {
        "team_name": "Opponent XI",
        "decision_threat": {"level": "HIGH", "projected_points_adjustment": 1.2, "evidence": "LOW"},
    }

    result = build_h2h_matchup(
        _league(),
        "336654",
        mine,
        mine + opponent,
        [],
        1,
        manager_profiles={"888888": profile},
    )

    assert result["opponent_profile"] == profile
    assert result["matchup"]["opponent"]["projection"].get("decision_adjustment") is None


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


def test_builds_four_gameweek_outlook_and_preserves_frozen_current_forecast():
    league = _league()
    league["league_entries"].extend([
        {"id": 503, "entry_id": 777777, "entry_name": "GW2 Opponent"},
        {"id": 504, "entry_id": 666666, "entry_name": "GW3 Opponent"},
        {"id": 505, "entry_id": 555555, "entry_name": "GW4 Opponent"},
    ])
    league["matches"].extend([
        {"event": 2, "league_entry_1": 503, "league_entry_2": 501, "finished": False},
        {"event": 3, "league_entry_1": 501, "league_entry_2": 504, "finished": False},
        {"event": 4, "league_entry_1": 505, "league_entry_2": 501, "finished": False},
    ])
    league["standings"].extend([
        {"league_entry": 503, "rank": 3, "total": 0, "points_for": 0},
        {"league_entry": 504, "rank": 1, "total": 0, "points_for": 0},
        {"league_entry": 505, "rank": 5, "total": 0, "points_for": 0},
    ])
    mine = _squad(1, 501, 336654, 85, 2)
    opponents = (
        _squad(101, 502, 888888, 70, 4)
        + _squad(201, 503, 777777, 92, 2)
        + _squad(301, 504, 666666, 82, 3)
        + _squad(401, 505, 555555, 62, 5)
    )
    frozen = {
        "gameweek": 1,
        "forecast": {
            "recommended": {"projected_total": 44.0, "range_low": 30.0, "range_high": 58.0},
            "h2h": {"projected_opponent_total": 41.0, "projected_edge": 3.0},
        },
    }

    outlook = build_h2h_outlook(league, "336654", mine, mine + opponents, [1, 2, 3, 4], frozen)

    assert outlook["model"] == "v1.1"
    assert outlook["available"] is True
    assert len(outlook["gameweeks"]) == 4
    assert all(card["available"] for card in outlook["gameweeks"])
    assert outlook["gameweeks"][0]["my"]["total"] == 44.0
    assert outlook["gameweeks"][0]["opponent_projection"]["total"] == 41.0
    assert outlook["gameweeks"][0]["projection_source"] == "frozen_gameweek_forecast"
    assert outlook["gameweeks"][1]["opponent"]["display_name"] == "GW2 Opponent"
    assert outlook["gameweeks"][1]["projection_source"] == "current_rosters"
    assert sum(outlook["summary"]["signals"].values()) == 4
    assert outlook["summary"]["toughest_matchup"]["gameweek"] in {1, 2, 3, 4}
    assert outlook["summary"]["recurring_weakness"] is None


def test_future_outlook_applies_a_bounded_transparent_manager_adjustment_only_after_current_gw():
    league = _league()
    league["league_entries"].append({"id": 503, "entry_id": 777777, "entry_name": "GW2 Opponent"})
    league["matches"].append({"event": 2, "league_entry_1": 503, "league_entry_2": 501, "finished": False})
    mine = _squad(1, 501, 336654, 80, 3)
    opponents = _squad(101, 502, 888888, 75, 3) + _squad(201, 503, 777777, 75, 3)
    profiles = {
        "888888": {"decision_threat": {"level": "HIGH", "projected_points_adjustment": 1.5}},
        "777777": {"decision_threat": {"level": "HIGH", "projected_points_adjustment": 1.5}},
    }

    outlook = build_h2h_outlook(
        league,
        "336654",
        mine,
        mine + opponents,
        [1, 2],
        manager_profiles=profiles,
    )

    current, future = outlook["gameweeks"]
    assert current["decision_adjustment"] == 0.0
    assert current["opponent_projection"].get("roster_total") is None
    assert future["decision_adjustment"] == 1.5
    assert future["opponent_projection"]["total"] == future["opponent_projection"]["roster_total"] + 1.5
    assert future["projection_source"] == "current_roster_plus_decision_profile"


def test_four_gameweek_outlook_only_labels_a_repeated_negative_position():
    league = _league()
    league["league_entries"].extend([
        {"id": 503, "entry_id": 777777, "entry_name": "GW2 Opponent"},
        {"id": 504, "entry_id": 666666, "entry_name": "GW3 Opponent"},
        {"id": 505, "entry_id": 555555, "entry_name": "GW4 Opponent"},
    ])
    league["matches"].extend([
        {"event": 2, "league_entry_1": 503, "league_entry_2": 501},
        {"event": 3, "league_entry_1": 501, "league_entry_2": 504},
        {"event": 4, "league_entry_1": 505, "league_entry_2": 501},
    ])
    mine = _squad(1, 501, 336654, 65, 3)
    opponents = (
        _squad(101, 502, 888888, 90, 3)
        + _squad(201, 503, 777777, 90, 3)
        + _squad(301, 504, 666666, 90, 3)
        + _squad(401, 505, 555555, 90, 3)
    )

    outlook = build_h2h_outlook(league, "336654", mine, mine + opponents, [1, 2, 3, 4])

    weakness = outlook["summary"]["recurring_weakness"]
    assert weakness["position"] in {"GKP", "DEF", "MID", "FWD"}
    assert weakness["average_projected_edge"] < 0
    assert weakness["trailing_gameweeks"] == 4
