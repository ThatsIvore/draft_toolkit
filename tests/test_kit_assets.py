from fpl_toolkit.normalize import normalize_ownership


def test_normalized_player_exposes_official_team_code_for_kit_assets():
    element_status = [{"element": 10, "status": "a", "owner": None}]
    league_details = {"league_entries": []}
    bootstrap = {
        "elements": [
            {
                "id": 10,
                "web_name": "Example",
                "team": 1,
                "element_type": 3,
                "chance_of_playing_next_round": 100,
            }
        ],
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS", "code": 3}],
        "element_types": [{"id": 3, "singular_name": "Midfielder", "singular_name_short": "MID"}],
    }

    [player] = normalize_ownership(element_status, league_details, bootstrap)

    assert player["team_id"] == 1
    assert player["team_code"] == 3
    assert player["club"] == "ARS"
