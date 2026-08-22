import json

import pytest

from fpl_toolkit.config import ConfigError, StandardFplSettings, standard_entry_id_from_url
from fpl_toolkit.standard_fpl import (
    StandardFplDataError,
    collect_standard_fpl,
    confirmed_squad_gameweek,
    normalize_standard_player_pool,
)


POSITIONS = {
    1: "GKP",
    2: "GKP",
    3: "DEF",
    4: "DEF",
    5: "DEF",
    6: "DEF",
    7: "DEF",
    8: "MID",
    9: "MID",
    10: "MID",
    11: "MID",
    12: "MID",
    13: "FWD",
    14: "FWD",
    15: "FWD",
}


def _bootstrap():
    type_id = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
    return {
        "events": [
            {"id": 1, "is_current": True, "is_next": False, "finished": False},
            {"id": 2, "is_current": False, "is_next": True, "finished": False},
            {"id": 3, "is_current": False, "is_next": False, "finished": False},
            {"id": 4, "is_current": False, "is_next": False, "finished": False},
            {"id": 5, "is_current": False, "is_next": False, "finished": False},
        ],
        "teams": [
            {"id": team_id, "name": f"Team {team_id}", "short_name": f"T{team_id}", "code": 100 + team_id}
            for team_id in range(1, 5)
        ],
        "element_types": [
            {"id": 1, "singular_name_short": "GKP"},
            {"id": 2, "singular_name_short": "DEF"},
            {"id": 3, "singular_name_short": "MID"},
            {"id": 4, "singular_name_short": "FWD"},
        ],
        "elements": [
            {
                "id": player_id,
                "web_name": f"P{player_id}",
                "team": (player_id % 4) + 1,
                "element_type": type_id[position],
                "status": "a",
                "chance_of_playing_next_round": 100,
                "news": "",
                "event_points": player_id % 8,
                "total_points": player_id * 10,
                "minutes": 900,
                "starts": 10,
                "goals_scored": player_id // 5,
                "assists": player_id // 4,
                "clean_sheets": player_id // 3,
                "bonus": player_id,
                "expected_goal_involvements": str(player_id / 4),
                "form": str(player_id / 2),
                "points_per_game": str(player_id / 3),
                "ep_next": str(player_id / 3),
                "now_cost": 45 + player_id,
                "selected_by_percent": str(player_id),
                "transfers_in_event": player_id * 100,
                "transfers_out_event": player_id * 10,
                "cost_change_event": 0,
                "cost_change_start": player_id % 3,
            }
            for player_id, position in POSITIONS.items()
        ],
    }


def _picks():
    return {
        "active_chip": None,
        "automatic_subs": [],
        "entry_history": {
            "event": 1,
            "points": 61,
            "bank": 5,
            "value": 1005,
            "event_transfers": 0,
            "event_transfers_cost": 0,
        },
        "picks": [
            {
                "element": player_id,
                "position": player_id,
                "multiplier": 2 if player_id == 13 else 1 if player_id <= 11 else 0,
                "is_captain": player_id == 13,
                "is_vice_captain": player_id == 12,
            }
            for player_id in POSITIONS
        ],
    }


def _fixtures():
    rows = []
    for gameweek in range(2, 6):
        rows.extend([
            {
                "event": gameweek,
                "team_h": 1,
                "team_a": 2,
                "team_h_difficulty": 2,
                "team_a_difficulty": 4,
                "started": False,
                "finished": False,
            },
            {
                "event": gameweek,
                "team_h": 3,
                "team_a": 4,
                "team_h_difficulty": 3,
                "team_a_difficulty": 3,
                "started": False,
                "finished": False,
            },
        ])
    return rows


class _Client:
    def bootstrap_static(self):
        return _bootstrap()

    def fixtures(self):
        return _fixtures()

    def entry(self, entry_id):
        assert entry_id == "123456"
        return {"id": 123456, "name": "Private POC Team", "player_first_name": "Do not retain"}

    def entry_history(self, entry_id):
        return {"current": [_picks()["entry_history"]], "chips": [], "past": []}

    def entry_picks(self, entry_id, gameweek):
        assert gameweek == 1
        return _picks()


def test_extracts_entry_id_from_normal_standard_fpl_url():
    assert standard_entry_id_from_url(
        "https://fantasy.premierleague.com/en/entry/123456/event/1"
    ) == "123456"
    assert standard_entry_id_from_url("https://draft.premierleague.com/entry/123456/") is None


def test_standard_settings_accept_entry_url_and_keep_private_default(monkeypatch):
    monkeypatch.delenv("FPL_STANDARD_ENTRY_ID", raising=False)
    monkeypatch.setenv(
        "FPL_STANDARD_ENTRY_URL",
        "https://fantasy.premierleague.com/en/entry/123456/event/1",
    )
    settings = StandardFplSettings.from_env()
    assert settings.entry_id == "123456"
    assert settings.output_path == "data/private/standard-fpl-poc.json"


def test_standard_settings_reject_mismatched_id_and_url(monkeypatch):
    monkeypatch.setenv("FPL_STANDARD_ENTRY_ID", "111")
    monkeypatch.setenv("FPL_STANDARD_ENTRY_URL", "https://fantasy.premierleague.com/en/entry/222/event/1")
    with pytest.raises(ConfigError, match="different entries"):
        StandardFplSettings.from_env()


def test_standard_settings_reject_output_in_public_directory(monkeypatch):
    monkeypatch.delenv("FPL_STANDARD_ENTRY_URL", raising=False)
    monkeypatch.setenv("FPL_STANDARD_ENTRY_ID", "123456")
    monkeypatch.setenv("FPL_STANDARD_OUTPUT", "public/data/latest.json")
    with pytest.raises(ConfigError, match="data/private"):
        StandardFplSettings.from_env()


def test_normalizer_maps_prices_pick_flags_and_shared_player_contract():
    players = normalize_standard_player_pool(_bootstrap(), _picks(), "123456")
    player = next(row for row in players if row["player_id"] == 13)
    assert player["position"] == "FWD"
    assert player["is_owned"] is True
    assert player["owner_entry_id"] == "123456"
    assert player["submitted_captain"] is True
    assert player["now_cost"] == 5.8
    assert player["selected_by_percent"] == 13.0


def test_locked_current_gameweek_is_used_as_latest_public_squad():
    assert confirmed_squad_gameweek(_bootstrap()) == 1
    with pytest.raises(StandardFplDataError, match="not present"):
        confirmed_squad_gameweek(_bootstrap(), 38)


def test_collect_standard_fpl_reuses_intelligence_lineup_and_captaincy(tmp_path):
    settings = StandardFplSettings(
        entry_id="123456",
        planning_horizon=4,
        output_path=str(tmp_path / "report.json"),
        performance_baseline_path=str(tmp_path / "missing-baseline.json"),
    )
    report = collect_standard_fpl(settings, client=_Client())

    assert report["mode"] == "standard_fpl"
    assert report["current_gameweek"] == 1
    assert report["decision_gameweek"] == 2
    assert report["planning_gameweeks"] == [2, 3, 4, 5]
    assert report["squad_source"]["gameweek"] == 1
    assert report["squad_source"]["is_exact_for_decision_gameweek"] is False
    assert "hidden" in report["squad_source"]["warning"]
    assert report["summary"]["squad_count"] == 15
    assert len(report["confirmed_lineup"]["starters"]) == 11
    assert report["recommended_lineup"]["is_valid"] is True
    assert report["recommended_lineup"]["mode"] == "standard_fpl"
    assert "Draft" not in report["recommended_lineup"]["note"]
    assert [row["selection"]["bench_order"] for row in report["recommended_lineup"]["bench"]] == [1, 2, 3]
    starter_ids = {row["player_id"] for row in report["recommended_lineup"]["starters"]}
    assert report["captaincy"]["captain"]["player_id"] in starter_ids
    assert report["captaincy"]["vice_captain"]["player_id"] in starter_ids
    assert report["captaincy"]["captain"]["player_id"] != report["captaincy"]["vice_captain"]["player_id"]
    assert report["financial_snapshot"]["bank"] == 0.5
    assert report["financial_snapshot"]["has_current_selling_prices"] is False
    serialized = json.dumps(report)
    assert "player_first_name" not in serialized
    assert "owner_entry_id" not in serialized
    assert "owner_raw" not in serialized
    assert "123456" not in serialized
    assert report["limitations"]
