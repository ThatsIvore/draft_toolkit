from fpl_toolkit.collector import collect
from fpl_toolkit.config import Settings


class DraftClient:
    def __init__(self):
        self.entry_event_calls = []

    def entry_public(self, entry_id):
        return {}

    def bootstrap_static(self):
        return {
            "events": {
                "current": 1,
                "next": 2,
                "data": [
                    {"id": gameweek, "finished": False}
                    for gameweek in range(1, 7)
                ],
            },
            "teams": [],
            "element_types": [],
            "elements": [],
        }

    def league_details(self, league_id):
        return {"league_entries": [], "matches": [], "standings": []}

    def element_status(self, league_id):
        return {"element_status": []}

    def entry_event(self, entry_id, gameweek):
        self.entry_event_calls.append((entry_id, gameweek))
        return {"picks": []}


class FantasyClient:
    def fixtures(self):
        return [
            {"event": 1, "started": True, "finished": False},
            *[
                {"event": gameweek, "started": False, "finished": False}
                for gameweek in range(2, 7)
            ],
        ]


class PostWaiverDraftClient(DraftClient):
    def bootstrap_static(self):
        position_types = [1, 1, *([2] * 5), *([3] * 5), *([4] * 4)]
        return {
            "events": {
                "current": 1,
                "next": 2,
                "data": [
                    {"id": gameweek, "finished": False}
                    for gameweek in range(1, 7)
                ],
            },
            "teams": [{"id": 1, "name": "Test Club", "short_name": "TST", "code": 1}],
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
                    "team": 1,
                    "element_type": position_types[player_id - 1],
                    "chance_of_playing_next_round": 100,
                    "news": "",
                    "event_points": 2,
                    "total_points": 2,
                    "minutes": 90,
                    "starts": 1,
                    "goals_scored": 0,
                    "assists": 0,
                    "clean_sheets": 0,
                    "bonus": 0,
                    "expected_goal_involvements": "0.00",
                    "form": "2.0",
                    "points_per_game": "2.0",
                }
                for player_id in range(1, 17)
            ],
        }

    def league_details(self, league_id):
        return {
            "league_entries": [{"id": 501, "entry_id": 1001, "entry_name": "My Team"}],
            "matches": [],
            "standings": [],
        }

    def element_status(self, league_id):
        return {
            "element_status": [
                {
                    "element": player_id,
                    "owner": 501 if player_id <= 14 or player_id == 16 else None,
                    "status": "o" if player_id <= 14 or player_id == 16 else "l",
                }
                for player_id in range(1, 17)
            ]
        }

    def entry_event(self, entry_id, gameweek):
        self.entry_event_calls.append((entry_id, gameweek))
        return {
            "entry_history": {"points": 42},
            "picks": [
                {"element": player_id, "position": player_id}
                for player_id in range(1, 16)
            ],
        }


def test_collector_keeps_live_scoring_on_gw1_and_moves_actions_to_gw2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    draft_client = DraftClient()

    report = collect(
        Settings(
            draft_entry_id="1001",
            draft_league_id="77",
            planning_horizon=4,
            output_dir=str(tmp_path / "data"),
        ),
        client=draft_client,
        fantasy_client=FantasyClient(),
    )

    assert report["current_gameweek"] == 1
    assert report["gameweek_phase"] == "LIVE"
    assert report["decision_gameweek"] == 2
    assert report["planning_gameweeks"] == [2, 3, 4, 5]
    assert report["recommended_lineup"]["gameweek"] == 2
    assert report["h2h_matchup"]["gameweek"] == 2
    assert report["lineup"]["gameweek"] == 1
    assert report["outcome_diagnostics"]["current"]["gameweek"] == 1
    assert draft_client.entry_event_calls == [("1001", 1)]


def test_collector_preserves_all_15_locked_picks_after_a_waiver(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    draft_client = PostWaiverDraftClient()

    report = collect(
        Settings(
            draft_entry_id="1001",
            draft_league_id="77",
            planning_horizon=4,
            output_dir=str(tmp_path / "data"),
        ),
        client=draft_client,
        fantasy_client=FantasyClient(),
    )

    assert report["summary"]["my_squad_count"] == 15
    assert {row["player_id"] for row in report["my_squad"]} == {*range(1, 15), 16}
    assert report["lineup"]["is_exact"] is True
    assert len(report["lineup"]["starters"]) == 11
    assert len(report["lineup"]["bench"]) == 4
    assert report["lineup"]["bench"][-1]["player_id"] == 15
    assert report["lineup"]["bench"][-1]["player"] == "P15"
