from fpl_toolkit.waivers import attach_replacement_analysis


def player(player_id, name, position, roster, stash, fixture=60, start=70, minutes=60, availability=100):
    return {
        "player_id": player_id,
        "player": name,
        "position": position,
        "club": "TST",
        "intelligence": {
            "roster_score": roster,
            "stash_score": stash,
            "fixture_score": fixture,
            "start_probability": start,
            "expected_minutes": minutes,
            "availability_score": availability,
        },
    }


def test_replacement_engine_uses_same_position():
    squad = [
        player(1, "Weak MID", "MID", 50, 48),
        player(2, "Weak DEF", "DEF", 30, 30),
    ]
    available = [player(3, "Upgrade MID", "MID", 75, 72, fixture=75, start=85, minutes=75)]
    result = attach_replacement_analysis(available, squad)[0]["replacement"]
    assert result["drop_player"] == "Weak MID"
    assert result["drop_player"] != "Weak DEF"
    assert result["roster_delta"] == 25.0
    assert result["combined_delta"] > 0


def test_clear_upgrade_is_swap_now():
    squad = [player(1, "Bench MID", "MID", 45, 45, fixture=45, start=50, minutes=45)]
    available = [player(2, "Starter MID", "MID", 80, 75, fixture=80, start=90, minutes=80)]
    result = attach_replacement_analysis(available, squad)[0]["replacement"]
    assert result["action"] == "SWAP NOW"
    assert result["immediate_delta"] > 0


def test_negative_upgrade_keeps_roster():
    squad = [player(1, "Strong FWD", "FWD", 82, 80, fixture=75, start=90, minutes=82)]
    available = [player(2, "Depth FWD", "FWD", 55, 58, fixture=60, start=60, minutes=55)]
    result = attach_replacement_analysis(available, squad)[0]["replacement"]
    assert result["action"] == "KEEP ROSTER"
    assert result["combined_delta"] < 0
