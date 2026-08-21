from fpl_toolkit.optimizer import recommend_lineup
from fpl_toolkit.privacy import sanitize_public_report


def _player(player_id, position, score, chance=100, fixture=3, confidence=100, evidence=None):
    if evidence is None:
        evidence = "HIGH" if confidence >= 70 else "MEDIUM" if confidence >= 40 else "LOW"
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
            "sample_confidence": confidence,
            "role_evidence": evidence,
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
    assert result["model"] == "v0.6.1"
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
    easy = next(player for player in squad if player["player_id"] == 6)
    hard = next(player for player in squad if player["player_id"] == 7)
    easy["intelligence"].update({"floor_score": 60, "upside_score": 60, "roster_score": 60})
    hard["intelligence"].update({"floor_score": 60, "upside_score": 60, "roster_score": 60})
    easy["fixtures"] = [{"gameweek": 1, "matches": [{"difficulty": 1}]}]
    hard["fixtures"] = [{"gameweek": 1, "matches": [{"difficulty": 5}]}]
    result = recommend_lineup(squad, 1)
    scores = result["player_scores"]
    assert scores["6"]["start_score"] > scores["7"]["start_score"]


def test_low_sample_player_needs_clear_advantage_to_displace_established_option():
    squad = _standard_squad()
    established = next(player for player in squad if player["player_id"] == 14)
    low_sample = next(player for player in squad if player["player_id"] == 15)
    established["intelligence"].update({
        "floor_score": 70,
        "upside_score": 70,
        "roster_score": 70,
        "sample_confidence": 60,
        "role_evidence": "MEDIUM",
    })
    low_sample["intelligence"].update({
        "floor_score": 72,
        "upside_score": 72,
        "roster_score": 72,
        "sample_confidence": 25,
        "role_evidence": "LOW",
    })
    result = recommend_lineup(squad, 1)
    scores = result["player_scores"]
    assert scores["14"]["evidence_factor"] > scores["15"]["evidence_factor"]
    assert scores["14"]["start_score"] > scores["15"]["start_score"]


def test_optimizer_flags_narrow_same_position_selection_as_close_call():
    squad = _standard_squad()
    starter = next(player for player in squad if player["player_id"] == 13)
    alternative = next(player for player in squad if player["player_id"] == 14)
    starter["intelligence"].update({
        "floor_score": 70,
        "upside_score": 70,
        "roster_score": 70,
        "sample_confidence": 60,
        "role_evidence": "MEDIUM",
    })
    alternative["intelligence"].update({
        "floor_score": 69,
        "upside_score": 69,
        "roster_score": 69,
        "sample_confidence": 55,
        "role_evidence": "MEDIUM",
    })
    result = recommend_lineup(squad, 1)
    pairs = {(call["starter_player_id"], call["alternative_player_id"]) for call in result["close_calls"]}
    assert (13, 14) in pairs
    call = next(call for call in result["close_calls"] if call["starter_player_id"] == 13 and call["alternative_player_id"] == 14)
    assert call["margin"] <= 2.0


def test_optimizer_returns_invalid_for_incomplete_squad_shape():
    result = recommend_lineup([_player(1, "GKP", 80), _player(2, "DEF", 80)], 1)
    assert result["is_valid"] is False
    assert result["starters"] == []
    assert result["close_calls"] == []


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
