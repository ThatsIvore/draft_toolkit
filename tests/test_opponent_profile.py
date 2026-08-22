import json
from pathlib import Path

from fpl_toolkit.opponent_profile import (
    build_manager_profiles,
    draft_profiles,
    expand_draft_picks,
    lineup_decision,
    update_manager_history,
)


def _player(player_id, name, position, baseline, event_points=0):
    return {
        "player_id": player_id,
        "player": name,
        "position": position,
        "event_points": event_points,
        "intelligence": {"baseline_score": baseline, "roster_score": baseline},
    }


def test_supplied_draft_has_90_unique_picks_and_correct_snake_order():
    draft = json.loads(Path("data/draft/league-draft.json").read_text(encoding="utf-8"))

    picks = expand_draft_picks(draft)

    assert len(picks) == 90
    assert len({pick["player"] for pick in picks}) == 90
    assert [pick["draft_code"] for pick in picks[:6]] == ["DG", "HL", "IR", "MF", "BP", "ÞH"]
    assert [pick["draft_code"] for pick in picks[6:12]] == ["ÞH", "BP", "MF", "IR", "HL", "DG"]
    assert [pick["player"] for pick in picks[12:18]] == ["Cunha", "Gibbs-White", "Gyökeres", "O'Reilly", "Calafiori", "Rice"]
    assert picks[0]["player_id"] == 411
    assert sum(pick["player_id"] is None for pick in picks) == 2


def test_draft_profile_resolves_players_and_keeps_adjustment_small():
    draft = {
        "teams": [
            {"draft_slot": 1, "draft_code": "AA", "team_name": "Alpha"},
            {"draft_slot": 2, "draft_code": "BB", "team_name": "Beta"},
        ],
        "rounds": [["A1", "B1"], ["B2", "A2"]],
    }
    ownership = [
        _player(1, "A1", "MID", 90),
        _player(2, "B1", "MID", 60),
        _player(3, "B2", "DEF", 55),
        _player(4, "A2", "DEF", 80),
    ]

    profiles = draft_profiles(draft, ownership)

    assert profiles["AA"]["resolved_picks"] == 2
    assert profiles["AA"]["score"] > profiles["BB"]["score"]
    assert profiles["AA"]["projected_points_adjustment"] <= 0.6
    assert profiles["BB"]["projected_points_adjustment"] >= -0.6


def test_manager_history_pairs_observed_adds_and_drops_without_real_names():
    league = {
        "league_entries": [
            {"id": 501, "entry_id": 111, "entry_name": "Alpha", "player_first_name": "Private", "player_last_name": "Name"}
        ]
    }
    ownership = [
        _player(1, "Add", "MID", 70),
        _player(2, "Drop", "MID", 55),
    ]
    changes = [
        {"type": "add", "player_id": 1, "to_owner": "111"},
        {"type": "drop", "player_id": 2, "from_owner": "111"},
    ]

    history = update_manager_history(
        None,
        league,
        ownership,
        changes,
        captured_at="2026-08-22T12:00:00+00:00",
        gameweek=1,
    )

    manager = history["managers"]["111"]
    assert manager["team_name"] == "Alpha"
    assert "player_first_name" not in manager
    assert manager["transactions"][0]["value_delta"] == 15.0
    assert [row["player"] for row in manager["transactions"][0]["adds"]] == ["Add"]
    assert [row["player"] for row in manager["transactions"][0]["drops"]] == ["Drop"]


def test_lineup_decision_measures_points_left_out_of_the_best_legal_xi():
    positions = ["GKP", "GKP"] + ["DEF"] * 5 + ["MID"] * 5 + ["FWD"] * 3
    squad = [
        _player(index, f"P{index}", position, 50, event_points=index)
        for index, position in enumerate(positions, start=1)
    ]
    lineup = {
        "gameweek": 1,
        "is_exact": True,
        "starters": squad[:11],
        "bench": squad[11:],
    }

    decision = lineup_decision(lineup)

    assert decision is not None
    assert decision["best_possible_points"] > decision["submitted_points"]
    assert decision["points_left_on_bench"] > 0
    assert 0 <= decision["efficiency"] <= 100


def test_manager_profile_uses_team_name_and_shrinks_early_evidence():
    league = {
        "league_entries": [
            {"id": 501, "entry_id": 111, "entry_name": "Alpha", "player_first_name": "A", "player_last_name": "A"}
        ]
    }
    draft = {
        "teams": [{"draft_slot": 1, "draft_code": "AA", "team_name": "Alpha"}],
        "rounds": [["A1"]],
    }
    ownership = [_player(1, "A1", "MID", 80)]
    history = update_manager_history(
        None,
        league,
        ownership,
        [],
        captured_at="2026-08-22T12:00:00+00:00",
        gameweek=1,
    )

    profiles = build_manager_profiles(league, ownership, draft, history)
    profile = profiles["111"]

    assert profile["team_name"] == "Alpha"
    assert profile["draft"]["draft_code"] == "AA"
    assert profile["decision_threat"]["evidence"] == "LOW"
    assert abs(profile["decision_threat"]["projected_points_adjustment"]) <= 0.6


def test_draft_mapping_survives_a_team_rename_via_transient_manager_initials():
    league = {
        "league_entries": [{
            "id": 501,
            "entry_id": 111,
            "entry_name": "Renamed team",
            "player_first_name": "Ivor Storm",
            "player_last_name": "Ross",
        }]
    }
    draft = {
        "teams": [{"draft_slot": 1, "draft_code": "IR", "team_name": "FC FC"}],
        "rounds": [["A1"]],
    }

    profile = build_manager_profiles(
        league,
        [_player(1, "A1", "MID", 80)],
        draft,
        None,
    )["111"]

    assert profile["team_name"] == "Renamed team"
    assert profile["draft"]["draft_code"] == "IR"


def test_collection_workflow_persists_manager_decisions_with_the_other_states():
    workflow = Path(".github/workflows/collect.yml").read_text(encoding="utf-8")

    assert workflow.count("data/state/manager-decisions.json") == 2
