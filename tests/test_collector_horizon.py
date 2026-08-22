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
