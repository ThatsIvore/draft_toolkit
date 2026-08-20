import pytest

from fpl_toolkit.config import ConfigError, Settings
from fpl_toolkit.diff import diff_ownership
from fpl_toolkit.fixtures import build_team_fixture_matrix
from fpl_toolkit.normalize import discover_league_ids, normalize_ownership
from fpl_toolkit.privacy import sanitize_public_report


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
        "elements": [{"id": 11, "web_name": "Beta", "team": 1, "element_type": 3, "chance_of_playing_next_round": 50, "news": "Back in training", "total_points": 4}],
    }
    league = {"league_entries": [{"id": 502, "entry_id": 23978, "entry_name": "Opponent XI"}]}
    before = normalize_ownership({"element_status": [{"element": 11, "status": "o", "owner": 502}]}, league, bootstrap)
    after = normalize_ownership({"element_status": [{"element": 11, "status": "a", "owner": None}]}, league, bootstrap)
    changes = diff_ownership(before, after)
    assert changes[0]["type"] == "drop"
    assert changes[0]["from_owner_name"] == "Opponent XI"
    matrix = build_team_fixture_matrix([{"event": 1, "team_h": 1, "team_a": 2}], bootstrap, 4)
    assert matrix["1"][0]["matches"][0]["opponent"] == "CHE"


def test_public_report_redacts_manager_identity():
    public = sanitize_public_report({
        "entry_id": "336654",
        "manager": {"entry_name": "Private"},
        "my_squad": [{"player": "Alpha", "owner_name": "Private", "owner_entry_id": 336654}],
        "available_players": [],
        "injury_watch": [],
        "league_activity": [{"type": "drop", "player": "Beta", "from_owner": "12", "from_owner_name": "Opponent"}],
    })
    assert "entry_id" not in public
    assert "manager" not in public
    assert "owner_name" not in public["my_squad"][0]
    assert "from_owner_name" not in public["league_activity"][0]
