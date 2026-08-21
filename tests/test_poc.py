import pytest

from fpl_toolkit.config import ConfigError, Settings
from fpl_toolkit.diff import diff_ownership
from fpl_toolkit.fixtures import build_team_fixture_matrix, planning_gameweeks
from fpl_toolkit.intelligence import attach_intelligence, usage_scores
from fpl_toolkit.lineup import fallback_lineup, normalize_lineup
from fpl_toolkit.normalize import discover_league_ids, normalize_ownership
from fpl_toolkit.privacy import sanitize_public_report
from fpl_toolkit.report import current_gameweek


def test_rejects_profile_uuid(monkeypatch):
    monkeypatch.setenv("FPL_DRAFT_ENTRY_ID", "11111111-2222-3333-4444-555555555555")
    with pytest.raises(ConfigError, match="numeric Draft entry ID"):
        Settings.from_env()


def test_discovers_nested_league_id():
    assert discover_league_ids({"entry": {"leagues": [{"id": 77}]}}) == ["77"]


def test_detects_opponent_drop_and_builds_fixture_matrix():
    bootstrap = {
        "events": [{"id": 1, "is_current": True, "finished": False}],
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}, {"id": 2, "name": "Chelsea", "short_name": "CHE"}],
        "element_types": [{"id": 3, "singular_name_short": "MID"}],
        "elements": [{"id": 11, "web_name": "Beta", "team": 1, "element_type": 3, "chance_of_playing_next_round": 50, "news": "Back in training", "total_points": 4, "minutes": 75, "starts": 1}],
    }
    league = {"league_entries": [{"id": 502, "entry_id": 23978, "entry_name": "Opponent XI"}]}
    before = normalize_ownership({"element_status": [{"element": 11, "status": "o", "owner": 502}]}, league, bootstrap)
    after = normalize_ownership({"element_status": [{"element": 11, "status": "a", "owner": None}]}, league, bootstrap)
    changes = diff_ownership(before, after)
    assert changes[0]["type"] == "drop"
    assert changes[0]["from_owner_name"] == "Opponent XI"
    assert after[0]["minutes"] == 75
    assert after[0]["starts"] == 1
    matrix = build_team_fixture_matrix([{"event": 1, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4}], bootstrap, 4)
    assert matrix["1"][0]["matches"][0]["opponent"] == "CHE"
    assert matrix["1"][0]["matches"][0]["difficulty"] == 2
    assert matrix["2"][0]["matches"][0]["difficulty"] == 4


def test_preseason_planning_uses_fixture_event_ids():
    bootstrap = {"events": []}
    fixtures = [
        {"event": 1, "finished": False},
        {"event": 2, "finished": False},
        {"event": 3, "finished": False},
        {"event": 4, "finished": False},
        {"event": 5, "finished": False},
    ]
    assert planning_gameweeks(bootstrap, 4, fixtures) == [1, 2, 3, 4]
    assert current_gameweek(bootstrap, [1, 2, 3, 4]) == 0


def test_intelligence_rewards_strong_baseline_easy_fixtures_and_role():
    players = [
        {
            "player_id": 1,
            "position": "MID",
            "total_points": 180,
            "chance_next_round": 100,
            "minutes": 810,
            "starts": 9,
            "news": "",
            "fixtures": [{"gameweek": gw, "matches": [{"difficulty": 2}]} for gw in range(1, 5)],
        },
        {
            "player_id": 2,
            "position": "MID",
            "total_points": 60,
            "chance_next_round": 100,
            "minutes": 360,
            "starts": 8,
            "news": "",
            "fixtures": [{"gameweek": gw, "matches": [{"difficulty": 4}]} for gw in range(1, 5)],
        },
    ]
    enriched = attach_intelligence(players)
    assert enriched[0]["intelligence"]["roster_score"] > enriched[1]["intelligence"]["roster_score"]
    assert enriched[0]["intelligence"]["fixture_score"] > enriched[1]["intelligence"]["fixture_score"]
    assert enriched[0]["intelligence"]["start_probability"] > enriched[1]["intelligence"]["start_probability"]


def test_usage_scores_scale_with_availability():
    fit_start, fit_minutes = usage_scores({"starts": 10, "minutes": 800, "chance_next_round": 100})
    doubt_start, doubt_minutes = usage_scores({"starts": 10, "minutes": 800, "chance_next_round": 50})
    assert fit_start > doubt_start
    assert fit_minutes > doubt_minutes
    assert fit_minutes <= 90


def test_preseason_usage_fallback_is_explicitly_conservative():
    start, minutes = usage_scores({"starts": 0, "minutes": 0, "chance_next_round": 100})
    assert start == 70
    assert minutes == 60


def test_intelligence_flags_return_watch():
    enriched = attach_intelligence([{ 
        "player_id": 1,
        "position": "FWD",
        "total_points": 100,
        "chance_next_round": 50,
        "minutes": 400,
        "starts": 5,
        "news": "Back in training",
        "fixtures": [{"gameweek": 1, "matches": [{"difficulty": 2}]}],
    }])
    assert enriched[0]["intelligence"]["injury_return_signal"] == "return-watch"


def test_intelligence_suppresses_players_who_left_the_league():
    players = [
        {
            "player_id": 1,
            "position": "DEF",
            "total_points": 200,
            "chance_next_round": 0,
            "minutes": 900,
            "starts": 10,
            "news": "Has joined Another Club permanently",
            "fixtures": [{"gameweek": 1, "matches": [{"difficulty": 1}]}],
        }
    ]
    enriched = attach_intelligence(players)
    assert enriched[0]["intelligence"]["roster_score"] < 10
    assert enriched[0]["intelligence"]["stash_score"] < 10


def test_normalizes_exact_draft_lineup_and_bench_order():
    squad = [{"player_id": player_id, "player": f"P{player_id}", "owner_name": "Private"} for player_id in range(1, 16)]
    payload = {"picks": [{"element": player_id, "position": player_id} for player_id in range(1, 16)]}
    lineup = normalize_lineup(payload, squad, 1)
    assert lineup is not None
    assert lineup["is_exact"] is True
    assert [row["player_id"] for row in lineup["starters"]] == list(range(1, 12))
    assert [row["player_id"] for row in lineup["bench"]] == [12, 13, 14, 15]


def test_incomplete_lineup_uses_non_authoritative_fallback():
    squad = [{"player_id": player_id} for player_id in range(1, 16)]
    assert normalize_lineup({"picks": [{"element": 1, "position": 1}]}, squad, 1) is None
    fallback = fallback_lineup(squad, 1)
    assert fallback["is_exact"] is False
    assert fallback["starters"] == []


def test_public_report_redacts_manager_identity():
    public = sanitize_public_report({
        "entry_id": "336654",
        "manager": {"entry_name": "Private"},
        "my_squad": [{"player": "Alpha", "owner_name": "Private", "owner_entry_id": 336654}],
        "available_players": [],
        "injury_watch": [],
        "lineup": {"starters": [{"player": "Alpha", "owner_name": "Private", "owner_entry_id": 336654}], "bench": []},
        "league_activity": [{"type": "drop", "player": "Beta", "from_owner": "12", "from_owner_name": "Opponent"}],
    })
    assert "entry_id" not in public
    assert "manager" not in public
    assert "owner_name" not in public["my_squad"][0]
    assert "owner_name" not in public["lineup"]["starters"][0]
    assert "from_owner_name" not in public["league_activity"][0]
