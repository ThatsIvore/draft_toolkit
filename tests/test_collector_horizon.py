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
    def bootstrap_static(self):
        return {"events": [], "elements": []}

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


class FinalisedDraftClient(DraftClient):
    def bootstrap_static(self):
        return {
            "events": {
                "current": 2,
                "next": 3,
                "data": [
                    {"id": 1, "finished": True},
                    {"id": 2, "finished": False},
                    {"id": 3, "finished": False},
                ],
            },
            "teams": [{"id": 4, "code": 94, "short_name": "BRE"}],
            "element_types": [{"id": 3, "singular_name_short": "MID"}],
            "elements": [
                {
                    "id": 556,
                    "code": 513545,
                    "web_name": "M.Sangaré",
                    "team": 4,
                    "element_type": 3,
                    "status": "a",
                    "minutes": 75,
                    "starts": 1,
                    "total_points": 14,
                    "event_points": 14,
                }
            ],
        }

    def element_status(self, league_id):
        return {"element_status": [{"element": 556, "status": "a", "owner": None}]}


class FinalisedFantasyClient:
    def bootstrap_static(self):
        return {
            "events": [{"id": 1, "finished": True, "data_checked": True}],
            "elements": [{"id": 565, "code": 513545}],
        }

    def fixtures(self):
        return [
            {"event": 2, "started": True, "finished": False},
            {"event": 3, "started": False, "finished": False},
        ]

    def event_live(self, gameweek):
        assert gameweek == 1
        return {
            "elements": [
                {
                    "id": 565,
                    "stats": {
                        "minutes": 75,
                        "starts": 1,
                        "total_points": 14,
                        "bonus": 3,
                        "bps": 41,
                        "expected_goal_involvements": "0.38",
                        "played": True,
                    },
                }
            ]
        }


def test_collector_attaches_standard_match_evidence_to_different_draft_player_id(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    report = collect(
        Settings(
            draft_entry_id="1001",
            draft_league_id="77",
            planning_horizon=4,
            output_dir=str(tmp_path / "data"),
        ),
        client=FinalisedDraftClient(),
        fantasy_client=FinalisedFantasyClient(),
    )

    [sangare] = report["available_players"]
    recent = sangare["intelligence"]["recent_match_evidence"]
    assert sangare["player_id"] == 556
    assert recent["status"] == "available"
    assert recent["appearances"] == 1
    assert recent["gameweeks"][0]["points"] == 14
    assert report["intelligence_model"]["recent_match_evidence"] == {
        "version": "v1",
        "status": "available",
        "completed_gameweeks": [1],
    }
