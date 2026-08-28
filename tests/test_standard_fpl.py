import json

import pytest

from fpl_toolkit.config import ConfigError, StandardFplSettings, standard_entry_id_from_url
from fpl_toolkit.standard_fpl import (
    StandardFplDataError,
    collect_standard_fpl,
    confirmed_squad_gameweek,
    normalize_standard_player_pool,
)
from fpl_toolkit.standard_fpl_snapshot import (
    SCHEMA_VERSION,
    StandardFplSnapshotError,
    load_private_snapshot,
    snapshot_to_picks_payload,
    validate_private_snapshot,
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
            for team_id in range(1, 7)
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
                "team": (player_id % 5) + 1,
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
        ] + [
            {
                "id": 16,
                "web_name": "Available MID",
                "team": 6,
                "element_type": type_id["MID"],
                "status": "a",
                "chance_of_playing_next_round": 100,
                "news": "",
                "event_points": 10,
                "total_points": 180,
                "minutes": 900,
                "starts": 10,
                "goals_scored": 8,
                "assists": 8,
                "clean_sheets": 5,
                "bonus": 20,
                "expected_goal_involvements": "10.0",
                "form": "10.0",
                "points_per_game": "8.0",
                "ep_next": "8.0",
                "now_cost": 55,
                "selected_by_percent": "20.0",
                "transfers_in_event": 1000,
                "transfers_out_event": 10,
                "cost_change_event": 0,
                "cost_change_start": 0,
            }
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
            {
                "event": gameweek,
                "team_h": 5,
                "team_a": 6,
                "team_h_difficulty": 3,
                "team_a_difficulty": 3,
                "started": False,
                "finished": False,
            },
        ])
    return rows


def _private_snapshot():
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at": "2026-08-22T20:00:00+00:00",
        "decision_gameweek": 2,
        "squad": [
            {
                "player_id": player_id,
                "lineup_position": player_id,
                "multiplier": 2 if player_id == 10 else 1 if player_id <= 11 else 0,
                "is_captain": player_id == 10,
                "is_vice_captain": player_id == 9,
                "purchase_price_tenths": 45 + player_id,
                "selling_price_tenths": 45 + player_id,
            }
            for player_id in POSITIONS
        ],
        "transfers": {
            "bank_tenths": 7,
            "squad_value_tenths": 1007,
            "free_transfers": 2,
            "transfers_made": 0,
        },
        "chips": [
            {"name": "wildcard", "number": 1, "status": "available", "played_gameweek": None},
            {"name": "freehit", "number": 1, "status": "available", "played_gameweek": None},
        ],
    }


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


class _FutureSeasonClient(_Client):
    def bootstrap_static(self):
        payload = _bootstrap()
        payload["events"][0]["deadline_time"] = "2027-08-13T17:30:00Z"
        return payload


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


def test_standard_settings_accept_private_snapshot_path(monkeypatch):
    monkeypatch.delenv("FPL_STANDARD_ENTRY_URL", raising=False)
    monkeypatch.setenv("FPL_STANDARD_ENTRY_ID", "123456")
    monkeypatch.setenv("FPL_STANDARD_PRIVATE_SNAPSHOT", "data/private/current-team.json")
    settings = StandardFplSettings.from_env()
    assert settings.private_snapshot_path == "data/private/current-team.json"


def test_standard_settings_reject_snapshot_outside_private_directory(monkeypatch):
    monkeypatch.delenv("FPL_STANDARD_ENTRY_URL", raising=False)
    monkeypatch.setenv("FPL_STANDARD_ENTRY_ID", "123456")
    monkeypatch.setenv("FPL_STANDARD_PRIVATE_SNAPSHOT", "public/data/current-team.json")
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


def test_private_snapshot_contract_is_strict_and_identifier_free():
    snapshot = validate_private_snapshot(
        _private_snapshot(),
        known_player_ids=set(POSITIONS),
    )
    assert snapshot["schema_version"] == SCHEMA_VERSION
    assert snapshot["transfers"]["free_transfers"] == 2
    picks = snapshot_to_picks_payload(snapshot)
    assert len(picks["picks"]) == 15
    assert picks["picks"][9]["purchase_price"] == 55
    assert picks["picks"][9]["is_captain"] is True
    assert "entry_id" not in json.dumps(snapshot)


def test_private_snapshot_rejects_extra_identity_or_credential_fields():
    snapshot = _private_snapshot()
    snapshot["entry_id"] = 123456
    with pytest.raises(StandardFplSnapshotError, match="unsupported fields: entry_id"):
        validate_private_snapshot(snapshot)

    snapshot = _private_snapshot()
    snapshot["squad"][0]["access_token"] = "do-not-store"
    with pytest.raises(StandardFplSnapshotError, match="unsupported fields: access_token"):
        validate_private_snapshot(snapshot)


def test_private_snapshot_rejects_stale_or_malformed_team_state():
    duplicate = _private_snapshot()
    duplicate["squad"][1]["player_id"] = duplicate["squad"][0]["player_id"]
    with pytest.raises(StandardFplSnapshotError, match="player_id values must be unique"):
        validate_private_snapshot(duplicate)

    missing_captain = _private_snapshot()
    missing_captain["squad"][9]["is_captain"] = False
    missing_captain["squad"][9]["multiplier"] = 1
    with pytest.raises(StandardFplSnapshotError, match="exactly one captain"):
        validate_private_snapshot(missing_captain)

    stale_player = _private_snapshot()
    stale_player["squad"][0]["player_id"] = 999
    with pytest.raises(StandardFplSnapshotError, match="unknown player IDs"):
        validate_private_snapshot(stale_player, known_player_ids=set(POSITIONS))

    bench_captain = _private_snapshot()
    bench_captain["squad"][9]["is_captain"] = False
    bench_captain["squad"][9]["multiplier"] = 1
    bench_captain["squad"][12]["is_captain"] = True
    bench_captain["squad"][12]["multiplier"] = 2
    with pytest.raises(StandardFplSnapshotError, match="must be starters"):
        validate_private_snapshot(bench_captain)


def test_private_snapshot_file_errors_are_actionable(tmp_path):
    with pytest.raises(StandardFplSnapshotError, match="Could not read private snapshot"):
        load_private_snapshot(tmp_path / "missing.json")


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
    assert report["rules"]["season"] == "2026-27"
    assert report["squad_legality"]["is_legal"] is True
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
    assert report["single_transfer_candidates"]["is_available"] is False
    assert report["single_transfer_candidates"]["candidates"] == []
    serialized = json.dumps(report)
    assert "player_first_name" not in serialized
    assert "owner_entry_id" not in serialized
    assert "owner_raw" not in serialized
    assert "123456" not in serialized
    assert report["limitations"]


def test_collect_standard_fpl_uses_valid_private_snapshot_for_current_state(tmp_path):
    snapshot_path = tmp_path / "current-team.json"
    snapshot_path.write_text(json.dumps(_private_snapshot()), encoding="utf-8")
    settings = StandardFplSettings(
        entry_id="123456",
        planning_horizon=4,
        output_path=str(tmp_path / "report.json"),
        performance_baseline_path=str(tmp_path / "missing-baseline.json"),
        private_snapshot_path=str(snapshot_path),
    )
    report = collect_standard_fpl(settings, client=_Client())

    assert report["poc_version"] == "phase-1-v0.6"
    assert report["squad_source"]["type"] == "private_current_team_snapshot"
    assert report["squad_source"]["gameweek"] == 2
    assert report["squad_source"]["is_exact_for_decision_gameweek"] is True
    assert report["squad_source"]["warning"] is None
    assert report["confirmed_lineup"]["source"] == "standard_fpl_private_snapshot"
    assert report["financial_snapshot"]["bank"] == 0.7
    assert report["financial_snapshot"]["squad_value"] == 100.7
    assert report["financial_snapshot"]["free_transfers"] == 2
    assert report["financial_snapshot"]["has_current_selling_prices"] is True
    assert report["single_transfer_candidates"]["is_available"] is True
    assert report["single_transfer_candidates"]["advisory_only"] is True
    assert report["single_transfer_candidates"]["candidates"]
    assert report["transfer_decision"]["is_available"] is True
    assert report["transfer_decision"]["recommendation"] in {"HOLD", "CONSIDER"}
    assert report["transfer_decision"]["reasons"]
    assert report["transfer_outcomes"]["current"]["forecast"]["gameweek"] == 2
    assert report["transfer_outcomes"]["current"]["forecast"]["calibration_eligible"] is True
    assert report["squad_outlook"]["is_valid"] is True
    assert report["squad_outlook"]["gameweeks"] == [2, 3, 4, 5]
    assert len(report["squad_outlook"]["rounds"]) == 4
    assert all(len(row["starters"]) == 11 for row in report["squad_outlook"]["rounds"])
    captain = next(row for row in report["squad"] if row["submitted_captain"])
    assert captain["purchase_price"] == 5.5
    assert captain["selling_price"] == 5.5
    serialized = json.dumps(report)
    assert "123456" not in serialized
    assert "access_token" not in serialized


def test_collect_standard_fpl_accepts_private_snapshot_in_memory_without_writing(tmp_path):
    output_path = tmp_path / "must-not-exist.json"
    settings = StandardFplSettings(
        entry_id="123456",
        planning_horizon=4,
        output_path=str(output_path),
        performance_baseline_path=str(tmp_path / "missing-baseline.json"),
    )

    report = collect_standard_fpl(
        settings,
        client=_Client(),
        previous_report={},
        private_snapshot=_private_snapshot(),
    )

    assert report["squad_source"]["type"] == "private_current_team_snapshot"
    assert report["financial_snapshot"]["free_transfers"] == 2
    assert not output_path.exists()


def test_collect_standard_fpl_rejects_stale_in_memory_snapshot(tmp_path):
    snapshot = _private_snapshot()
    snapshot["decision_gameweek"] = 3
    settings = StandardFplSettings(
        entry_id="123456",
        output_path=str(tmp_path / "must-not-exist.json"),
        performance_baseline_path=str(tmp_path / "missing-baseline.json"),
    )

    with pytest.raises(StandardFplDataError, match="Capture a fresh snapshot"):
        collect_standard_fpl(
            settings,
            client=_Client(),
            previous_report={},
            private_snapshot=snapshot,
        )


def test_collect_standard_fpl_reuses_same_team_frozen_decision(tmp_path):
    snapshot_path = tmp_path / "current-team.json"
    snapshot_path.write_text(json.dumps(_private_snapshot()), encoding="utf-8")
    settings = StandardFplSettings(
        entry_id="123456",
        output_path=str(tmp_path / "report.json"),
        performance_baseline_path=str(tmp_path / "missing-baseline.json"),
        private_snapshot_path=str(snapshot_path),
    )
    first = collect_standard_fpl(settings, client=_Client())
    second = collect_standard_fpl(settings, client=_Client(), previous_report=first)

    assert (
        second["transfer_outcomes"]["current"]["forecast"]["captured_at"]
        == first["transfer_outcomes"]["current"]["forecast"]["captured_at"]
    )


def test_collect_standard_fpl_does_not_carry_outcomes_between_team_names(tmp_path):
    snapshot_path = tmp_path / "current-team.json"
    snapshot_path.write_text(json.dumps(_private_snapshot()), encoding="utf-8")
    settings = StandardFplSettings(
        entry_id="123456",
        output_path=str(tmp_path / "report.json"),
        performance_baseline_path=str(tmp_path / "missing-baseline.json"),
        private_snapshot_path=str(snapshot_path),
    )
    previous = {
        "mode": "standard_fpl",
        "entry_context": {"team_name": "Different Team"},
        "transfer_outcomes": {
            "current": {
                "forecast": {
                    "gameweek": 2,
                    "captured_at": "2000-01-01T00:00:00+00:00",
                    "captured_phase": "SCHEDULED",
                    "calibration_eligible": True,
                    "recommendation": "HOLD",
                    "summary": "Wrong team forecast",
                    "candidate": None,
                }
            },
            "history": [],
        },
    }

    report = collect_standard_fpl(settings, client=_Client(), previous_report=previous)

    assert report["transfer_outcomes"]["current"]["forecast"]["captured_at"] != "2000-01-01T00:00:00+00:00"
    assert report["transfer_outcomes"]["current"]["forecast"]["summary"] != "Wrong team forecast"


def test_collect_standard_fpl_rejects_snapshot_for_wrong_decision_gameweek(tmp_path):
    snapshot = _private_snapshot()
    snapshot["decision_gameweek"] = 3
    snapshot_path = tmp_path / "stale-team.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    settings = StandardFplSettings(
        entry_id="123456",
        output_path=str(tmp_path / "report.json"),
        performance_baseline_path=str(tmp_path / "missing-baseline.json"),
        private_snapshot_path=str(snapshot_path),
    )
    with pytest.raises(StandardFplDataError, match="Capture a fresh snapshot"):
        collect_standard_fpl(settings, client=_Client())


def test_collect_standard_fpl_fails_closed_for_unverified_future_rules(tmp_path):
    settings = StandardFplSettings(
        entry_id="123456",
        output_path=str(tmp_path / "report.json"),
        performance_baseline_path=str(tmp_path / "missing-baseline.json"),
    )
    with pytest.raises(StandardFplDataError, match="newest verified Standard FPL ruleset"):
        collect_standard_fpl(settings, client=_FutureSeasonClient())
