from pathlib import Path

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


def test_compact_kit_dimensions_apply_outside_bench_cards():
    styles = Path("public/recommended-xi.css").read_text(encoding="utf-8")
    index = Path("public/index.html").read_text(encoding="utf-8")

    assert ".recommended-kit.compact{width:40px;height:44px;margin:0}" in styles
    assert ".recommended-bench-card .recommended-kit.compact{grid-row:1/3}" in styles
    assert ".recommended-bench-card .recommended-kit.compact{grid-row:1/3;width:40px" not in styles
    assert "recommended-xi.css?v=20260821.3" in index
