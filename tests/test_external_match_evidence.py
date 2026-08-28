import json

from fpl_toolkit.external_match_evidence import (
    build_api_football_shadow,
    canonical_team_name,
    map_api_football_player_code,
    public_shadow_summary,
)


def _bootstrap():
    return {
        "events": [{"id": 1, "deadline_time": "2026-08-21T17:30:00Z"}],
        "teams": [
            {"id": 1, "name": "Arsenal", "short_name": "ARS"},
            {"id": 2, "name": "Leeds", "short_name": "LEE"},
        ],
        "elements": [
            {"id": 10, "code": 1001, "first_name": "Bukayo", "second_name": "Saka", "web_name": "Saka", "team": 1, "element_type": 3},
            {"id": 11, "code": 1002, "first_name": "Martin", "second_name": "Odegaard", "web_name": "Odegaard", "team": 1, "element_type": 3},
            {"id": 20, "code": 2001, "first_name": "Anton", "second_name": "Stach", "web_name": "Stach", "team": 2, "element_type": 3},
            {"id": 21, "code": 2002, "first_name": "Alex", "second_name": "Smith", "web_name": "Smith", "team": 2, "element_type": 3},
            {"id": 22, "code": 2003, "first_name": "Adam", "second_name": "Smith", "web_name": "Smith", "team": 2, "element_type": 3},
        ],
    }


def _fpl_fixtures():
    return [{"id": 1, "event": 1, "team_h": 1, "team_a": 2, "kickoff_time": "2026-08-22T14:00:00Z", "finished": True}]


def _provider_fixture_list():
    return [{"fixture": {"id": 9001, "date": "2026-08-22T14:00:00+00:00"}, "teams": {"home": {"id": 42, "name": "Arsenal"}, "away": {"id": 63, "name": "Leeds United"}}}]


def _appearance(player_id, name, minutes, shots, on, key, dribbles):
    return {
        "player": {"id": player_id, "name": name},
        "statistics": [{
            "games": {"minutes": minutes, "position": "M"},
            "shots": {"total": shots, "on": on},
            "passes": {"key": key},
            "dribbles": {"success": dribbles},
            "tackles": {"total": 99, "interceptions": 99},
        }],
    }


def _provider_fixture_details():
    return [{
        "fixture": {"id": 9001, "date": "2026-08-22T14:00:00+00:00"},
        "players": [
            {"team": {"id": 42, "name": "Arsenal"}, "players": [_appearance(501, "B. Saka", 90, 5, 3, 2, 1), _appearance(502, "M. Odegaard", 90, 1, 0, 1, 0)]},
            {"team": {"id": 63, "name": "Leeds United"}, "players": [_appearance(601, "A. Stach", 90, 2, 1, 4, 2), _appearance(602, "A. Smith", 90, 3, 1, 1, 1)]},
        ],
    }]


class FakeClient:
    def __init__(self):
        self.calls = []

    def fixtures(self, **params):
        self.calls.append(params)
        if "ids" in params:
            return _provider_fixture_details()
        return _provider_fixture_list()


def test_team_aliases_cover_common_provider_names():
    assert canonical_team_name("Leeds United") == "leeds"
    assert canonical_team_name("Tottenham Hotspur") == "spurs"
    assert canonical_team_name("Wolverhampton Wanderers") == "wolves"
    assert canonical_team_name("Nott'm Forest") == "nottm forest"
    assert canonical_team_name("Nottingham Forest") == "nottm forest"


def test_player_mapping_requires_unique_team_scoped_match_and_supports_override():
    bootstrap = _bootstrap()
    assert map_api_football_player_code({"id": 501, "name": "B. Saka"}, "Arsenal", bootstrap) == (1001, "matched")
    assert map_api_football_player_code({"id": 602, "name": "A. Smith"}, "Leeds United", bootstrap) == (None, "ambiguous")
    assert map_api_football_player_code({"id": 602, "name": "A. Smith"}, "Leeds United", bootstrap, overrides={602: 2002}) == (2002, "override")


def test_shadow_mode_uses_derived_process_only_and_does_not_publish_raw_provider_rows():
    client = FakeClient()
    result = build_api_football_shadow(
        provider="api_football",
        api_key="secret-key",
        bootstrap=_bootstrap(),
        fixtures=_fpl_fixtures(),
        completed_gameweeks=[1],
        official_scores_by_code={1001: 90.0, 1002: 50.0, 2001: 70.0},
        client=client,
    )

    assert result["status"] == "available"
    assert result["season"] == 2026
    assert result["mapped_appearances"] == 3
    assert result["ambiguous_appearances"] == 1
    assert client.calls[0]["from"] == "2026-08-22"
    assert client.calls[1] == {"ids": "9001"}
    assert result["players"]["1001"]["process_score"] > result["players"]["1002"]["process_score"]
    assert result["players"]["1001"]["effective_external_weight"] < 0.03
    assert result["players"]["1001"]["combined_score"] > 89.0

    serialized = json.dumps(result)
    assert "secret-key" not in serialized
    assert "9001" not in serialized
    assert '"501"' not in serialized
    assert '"shots"' not in serialized
    assert '"rating"' not in serialized

    summary = public_shadow_summary(result)
    assert summary["recommendations_affected"] is False
    assert summary["derived_players"] == 3
    assert "players" not in summary


def test_missing_key_fails_neutral_without_calling_provider():
    client = FakeClient()
    result = build_api_football_shadow(
        provider="api_football",
        api_key=None,
        bootstrap=_bootstrap(),
        fixtures=_fpl_fixtures(),
        completed_gameweeks=[1],
        client=client,
    )

    assert result["status"] == "missing_api_key"
    assert result["players"] == {}
    assert client.calls == []
