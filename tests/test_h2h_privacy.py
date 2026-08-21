from fpl_toolkit.privacy import sanitize_public_report


def test_public_h2h_redacts_manager_identity_but_keeps_player_comparison():
    player = {
        "player_id": 1,
        "player": "Alpha",
        "owner_raw": 502,
        "owner_entry_id": 888888,
        "owner_name": "Opponent XI",
    }
    report = {
        "entry_id": "336654",
        "manager": {"entry_name": "Mine"},
        "my_squad": [],
        "available_players": [],
        "injury_watch": [],
        "league_activity": [],
        "h2h_matchup": {
            "available": True,
            "opponent": {
                "display_name": "Opponent XI",
                "entry_id": "888888",
                "league_entry_id": "502",
                "rank": 4,
            },
            "opponent_squad": [dict(player)],
            "my_lineup": {"starters": [], "bench": []},
            "opponent_lineup": {"starters": [dict(player)], "bench": []},
            "opponent_threats": [{"player_id": 1, "player": "Alpha"}],
        },
        "h2h_outlook": {
            "gameweeks": [{
                "gameweek": 2,
                "opponent": {"display_name": "Future Opponent", "entry_id": "777777", "league_entry_id": "503"},
            }],
            "summary": {
                "toughest_matchup": {"gameweek": 2, "opponent": "Future Opponent"},
                "best_opportunity": {"gameweek": 3, "opponent": "Another Opponent"},
            },
        },
    }

    public = sanitize_public_report(report)
    opponent = public["h2h_matchup"]["opponent"]
    assert opponent["display_name"] == "League opponent"
    assert "entry_id" not in opponent
    assert "league_entry_id" not in opponent
    assert "owner_name" not in public["h2h_matchup"]["opponent_squad"][0]
    assert "owner_entry_id" not in public["h2h_matchup"]["opponent_lineup"]["starters"][0]
    assert public["h2h_matchup"]["opponent_threats"][0]["player"] == "Alpha"
    future = public["h2h_outlook"]["gameweeks"][0]["opponent"]
    assert future == {"display_name": "League opponent"}
    assert public["h2h_outlook"]["summary"]["toughest_matchup"]["opponent"] == "League opponent"
