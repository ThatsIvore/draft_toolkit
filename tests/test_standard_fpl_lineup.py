import json

from fpl_toolkit.standard_fpl_lineup import build_squad_outlook


POSITIONS = [
    "GKP", "GKP",
    "DEF", "DEF", "DEF", "DEF", "DEF",
    "MID", "MID", "MID", "MID", "MID",
    "FWD", "FWD", "FWD",
]


def _player(player_id, position, *, availability=100.0, score=60.0):
    return {
        "player_id": player_id,
        "player": f"P{player_id}",
        "club": f"T{((player_id - 1) % 5) + 1}",
        "position": position,
        "owner_entry_id": "must-not-leak",
        "owner_raw": "must-not-leak",
        "chance_next_round": availability,
        "fixtures": [
            {
                "gameweek": gameweek,
                "matches": [{"difficulty": 2 + ((player_id + gameweek) % 3)}],
            }
            for gameweek in range(2, 6)
        ],
        "intelligence": {
            "roster_score": score,
            "availability_score": availability,
            "expected_minutes": 90.0 if availability >= 75 else 50.0,
            "floor_score": score,
            "upside_score": score,
            "sample_confidence": 80.0,
        },
    }


def _squad():
    return [
        _player(player_id, position, score=75.0 - player_id)
        for player_id, position in enumerate(POSITIONS, start=1)
    ]


def test_builds_four_round_legal_private_outlook_without_owner_identifiers():
    outlook = build_squad_outlook(_squad(), [2, 3, 4, 5])

    assert outlook["is_valid"] is True
    assert outlook["gameweeks"] == [2, 3, 4, 5]
    assert len(outlook["rounds"]) == 4
    assert sum(player["starts"] for player in outlook["core_starters"] + outlook["rotation_players"]) == 44
    for round_row in outlook["rounds"]:
        assert len(round_row["starters"]) == 11
        assert len(round_row["bench"]) == 3
        assert round_row["reserve_goalkeeper"] is not None
        starter_ids = {player["player_id"] for player in round_row["starters"]}
        assert round_row["captain"]["player_id"] in starter_ids
        assert round_row["vice_captain"]["player_id"] in starter_ids
        assert round_row["captain"]["player_id"] != round_row["vice_captain"]["player_id"]
        assert len(round_row["captaincy_shortlist"]) == 5
    serialized = json.dumps(outlook)
    assert "owner_entry_id" not in serialized
    assert "owner_raw" not in serialized
    assert "projected FPL points" in outlook["note"]


def test_outlook_surfaces_high_pressure_when_risky_starters_have_no_cover():
    squad = _squad()
    squad[0]["intelligence"]["availability_score"] = 70.0
    squad[0]["intelligence"]["expected_minutes"] = 50.0
    squad[7]["intelligence"]["availability_score"] = 70.0
    squad[7]["intelligence"]["expected_minutes"] = 50.0
    for player in squad[-4:]:
        player["intelligence"]["availability_score"] = 0.0
        player["intelligence"]["expected_minutes"] = 0.0

    outlook = build_squad_outlook(squad, [2])
    round_row = outlook["rounds"][0]

    assert round_row["selection_pressure"] == "HIGH"
    assert len(round_row["availability_risks"]) >= 2
    assert round_row["playable_outfield_bench_count"] == 0
    assert {reason for player in round_row["availability_risks"] for reason in player["risk_reasons"]} == {
        "availability",
        "minutes",
    }


def test_empty_horizon_fails_closed():
    outlook = build_squad_outlook(_squad(), [])

    assert outlook["is_valid"] is False
    assert outlook["rounds"] == []
    assert outlook["core_starters"] == []
