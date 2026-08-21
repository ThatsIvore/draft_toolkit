from fpl_toolkit.waivers import attach_replacement_analysis


def player(player_id, name, position, roster, stash, fixture=60, start=70, minutes=60, availability=100, floor=60, upside=60, confidence=80):
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
            "floor_score": floor,
            "upside_score": upside,
            "sample_confidence": confidence,
        },
    }


def test_replacement_engine_uses_same_position():
    squad = [player(1, "Weak MID", "MID", 50, 48), player(2, "Weak DEF", "DEF", 30, 30)]
    available = [player(3, "Upgrade MID", "MID", 75, 72, fixture=75, start=85, minutes=75, floor=74, upside=76)]
    result = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    assert result["drop_player"] == "Weak MID"
    assert result["drop_player"] != "Weak DEF"
    assert result["roster_delta"] == 25.0
    assert result["combined_delta"] > 0


def test_clear_upgrade_is_swap_now_in_season():
    squad = [player(1, "Bench MID", "MID", 45, 45, fixture=45, start=50, minutes=45, floor=45, upside=48)]
    available = [player(2, "Starter MID", "MID", 82, 78, fixture=80, start=90, minutes=80, floor=82, upside=85)]
    result = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    assert result["action"] == "SWAP NOW"
    assert result["immediate_delta"] > 0
    assert result["confidence"] == "HIGH"


def test_preseason_guardrail_downgrades_marginal_swap():
    squad = [player(1, "Owned MID", "MID", 60, 60, fixture=55, start=75, minutes=68, floor=64, upside=72)]
    available = [player(2, "Free MID", "MID", 72, 70, fixture=66, start=85, minutes=75, floor=68, upside=78)]
    in_season = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    preseason = attach_replacement_analysis(available, squad, current_gameweek=0)[0]["replacement"]
    assert in_season["combined_delta"] == preseason["combined_delta"]
    assert preseason["action"] != "SWAP NOW"
    assert preseason["preseason_guardrail"] is True


def test_low_sample_confidence_blocks_swap_now():
    squad = [player(1, "Owned FWD", "FWD", 50, 50, floor=50, upside=55, confidence=25)]
    available = [player(2, "Free FWD", "FWD", 85, 82, fixture=80, start=90, minutes=82, floor=82, upside=90, confidence=25)]
    result = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    assert result["confidence"] == "LOW"
    assert result["action"] != "SWAP NOW"


def test_negative_upgrade_keeps_roster():
    squad = [player(1, "Strong FWD", "FWD", 82, 80, fixture=75, start=90, minutes=82, floor=84, upside=82)]
    available = [player(2, "Depth FWD", "FWD", 55, 58, fixture=60, start=60, minutes=55, floor=58, upside=62)]
    result = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    assert result["action"] == "KEEP ROSTER"
    assert result["combined_delta"] < 0
