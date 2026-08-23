from fpl_toolkit.intelligence import attach_intelligence
from fpl_toolkit.recent_match_evidence import (
    build_recent_match_evidence,
    completed_gameweeks,
    fetch_completed_event_live,
)


def _player(player_id, position="MID"):
    return {
        "player_id": player_id,
        "player": f"Player {player_id}",
        "position": position,
        "minutes": 900,
        "starts": 10,
        "total_points": 50,
        "points_per_game": 5,
        "goals_scored": 2,
        "assists": 2,
        "expected_goal_involvements": 4,
        "chance_next_round": 100,
        "fixtures": [],
    }


def _event(gameweek, stats_by_id):
    return (
        gameweek,
        {
            "elements": [
                {"id": player_id, "stats": stats}
                for player_id, stats in stats_by_id.items()
            ]
        },
    )


def _stats(points, bps, xgi, minutes=90, starts=1, played=True):
    return {
        "total_points": points,
        "bps": bps,
        "expected_goal_involvements": str(xgi),
        "minutes": minutes,
        "starts": starts,
        "bonus": max(0, points - 8),
        "played": played,
    }


def test_only_final_checked_gameweeks_are_eligible():
    bootstrap = {
        "events": [
            {"id": 1, "finished": True, "data_checked": True},
            {"id": 2, "finished": True, "data_checked": False},
            {"id": 3, "finished": False, "data_checked": True},
            {"id": 4, "finished": True, "data_checked": True},
            {"id": 5, "finished": True, "data_checked": True},
            {"id": 6, "finished": True, "data_checked": True},
            {"id": 7, "finished": True, "data_checked": True},
        ]
    }

    assert completed_gameweeks(bootstrap) == [4, 5, 6, 7]


def test_fetch_fails_closed_when_feed_is_unavailable():
    class Client:
        pass

    bootstrap = {"events": [{"id": 1, "finished": True, "data_checked": True}]}

    assert fetch_completed_event_live(Client(), bootstrap) == ([], "client_unavailable")


def test_recent_grades_are_position_relative_recency_weighted_and_capped():
    players = [_player(1), _player(2)]
    events = [
        _event(1, {1: _stats(2, 10, 0.0), 2: _stats(10, 40, 1.0)}),
        _event(2, {1: _stats(12, 45, 1.2), 2: _stats(2, 8, 0.0)}),
        _event(3, {1: _stats(12, 45, 1.2), 2: _stats(2, 8, 0.0)}),
    ]

    evidence = build_recent_match_evidence(players, events)

    assert evidence[1]["grade"] == "A"
    assert evidence[1]["score"] > evidence[2]["score"]
    assert evidence[1]["confidence"] == 100.0
    assert 0 < evidence[1]["adjustment"] <= 5
    assert -5 <= evidence[2]["adjustment"] < 0
    assert [row["gameweek"] for row in evidence[1]["gameweeks"]] == [3, 2, 1]


def test_non_appearance_is_not_given_a_grade_or_form_adjustment():
    players = [_player(1)]
    events = [_event(1, {1: _stats(0, 0, 0, minutes=0, starts=0, played=False)})]

    evidence = build_recent_match_evidence(players, events)[1]

    assert evidence["grade"] is None
    assert evidence["adjustment"] == 0
    assert evidence["confidence"] == 0
    assert evidence["gameweeks"][0]["grade"] is None


def test_same_shared_evidence_adjusts_both_game_modes_identically():
    players = [_player(1), _player(2)]
    evidence = build_recent_match_evidence(
        players,
        [
            _event(1, {1: _stats(10, 40, 1.0), 2: _stats(2, 8, 0.0)}),
            _event(2, {1: _stats(10, 40, 1.0), 2: _stats(2, 8, 0.0)}),
            _event(3, {1: _stats(10, 40, 1.0), 2: _stats(2, 8, 0.0)}),
        ],
    )

    draft = attach_intelligence(players, my_entry_id="draft", recent_match_evidence=evidence)
    standard = attach_intelligence(players, my_entry_id="standard", recent_match_evidence=evidence)

    assert draft[0]["intelligence"]["recent_match_evidence"] == standard[0]["intelligence"]["recent_match_evidence"]
    assert draft[0]["intelligence"]["baseline_score"] == standard[0]["intelligence"]["baseline_score"]
