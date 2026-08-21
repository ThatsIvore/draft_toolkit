from fpl_toolkit.planner import build_schedule_planner, player_schedule_score


def _player(player_id, position, score=70, difficulties=(3, 3, 3, 3), confidence=80, availability=100):
    return {
        "player_id": player_id,
        "player": f"P{player_id}",
        "club": "TST",
        "team_code": 100 + player_id,
        "position": position,
        "chance_next_round": availability,
        "fixtures": [
            {
                "gameweek": index + 1,
                "matches": [{"opponent": f"O{index + 1}", "venue": "H", "difficulty": difficulty}],
            }
            for index, difficulty in enumerate(difficulties)
        ],
        "intelligence": {
            "availability_score": availability,
            "expected_minutes": 90 if availability else 0,
            "floor_score": score,
            "upside_score": score,
            "roster_score": score,
            "sample_confidence": confidence,
            "role_evidence": "HIGH" if confidence >= 70 else "MEDIUM" if confidence >= 40 else "LOW",
        },
    }


def _squad():
    players = [_player(1, "GKP", 75), _player(2, "GKP", 65)]
    players += [_player(i, "DEF", 78 - i) for i in range(3, 8)]
    players += [_player(i, "MID", 85 - i) for i in range(8, 13)]
    players += [_player(i, "FWD", 82 - i) for i in range(13, 16)]
    return players


def test_schedule_score_prefers_easy_fixture_with_equal_player_quality():
    easy = _player(100, "MID", 70, difficulties=(1, 3, 3, 3))
    hard = _player(101, "MID", 70, difficulties=(5, 3, 3, 3))
    assert player_schedule_score(easy, 1)["schedule_score"] > player_schedule_score(hard, 1)["schedule_score"]


def test_planner_marks_weakest_gameweek_from_legal_schedule_lineups():
    squad = _squad()
    for player in squad:
        player["fixtures"][2]["matches"][0]["difficulty"] = 5
    planner = build_schedule_planner(squad, [], [1, 2, 3, 4])
    assert planner["model"] == "v0.7"
    assert planner["weakest_gameweek"] == 3
    assert len(planner["weeks"]) == 4
    assert all(week["formation"] for week in planner["weeks"])


def test_planner_streamer_targets_compare_same_position_schedule_window():
    squad = _squad()
    weak_mid = next(player for player in squad if player["player_id"] == 12)
    weak_mid["fixtures"] = [
        {"gameweek": gw, "matches": [{"opponent": "HARD", "venue": "A", "difficulty": 5}]}
        for gw in (1, 2, 3, 4)
    ]
    candidate = _player(200, "MID", 72, difficulties=(2, 2, 2, 2), confidence=80)
    planner = build_schedule_planner(squad, [candidate], [1, 2, 3, 4])
    target = next(item for item in planner["streamer_targets"] if item["add_player_id"] == 200)
    assert target["drop_player_id"] == 12
    assert target["position"] == "MID"
    assert target["schedule_delta"] >= 6
    assert target["label"] == "SCHEDULE UPGRADE"


def test_planner_keeps_start_score_and_roster_value_separate():
    player = _player(300, "FWD", 80, difficulties=(5, 1, 1, 1), confidence=80)
    planner = build_schedule_planner([player], [], [1, 2, 3, 4])
    row = planner["roster_rows"][0]
    assert row["roster_value"] == 80
    assert row["next_start_score"] != row["average_schedule_score"]
    assert "not projected FPL points" in planner["note"]
