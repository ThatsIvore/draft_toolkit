from fpl_toolkit.waivers import attach_replacement_analysis


def player(player_id, name, position, roster, stash, fixture=60, start=70, minutes=60, availability=100, floor=60, upside=60, confidence=80, return_signal="fit", usage=70):
    return {
        "player_id": player_id,
        "player": name,
        "position": position,
        "club": "TST",
        "fixtures": [{"gameweek": 2, "matches": [{"difficulty": 3}]}],
        "intelligence": {
            "roster_score": roster,
            "stash_score": stash,
            "fixture_score": fixture,
            "start_probability": start,
            "expected_minutes": minutes,
            "usage_score": usage,
            "availability_score": availability,
            "floor_score": floor,
            "upside_score": upside,
            "sample_confidence": confidence,
            "injury_return_signal": return_signal,
        },
    }


def test_replacement_engine_uses_same_position():
    squad = [player(1, "Weak MID", "MID", 50, 48), player(2, "Weak DEF", "DEF", 30, 30)]
    available = [player(3, "Upgrade MID", "MID", 75, 72, fixture=75, start=85, minutes=75, floor=74, upside=76, usage=85)]
    result = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    assert result["drop_player"] == "Weak MID"
    assert result["drop_player"] != "Weak DEF"
    assert result["roster_delta"] == 25.0
    assert result["combined_delta"] > 0


def test_clear_upgrade_is_swap_now_in_season():
    squad = [player(1, "Bench MID", "MID", 45, 45, fixture=45, start=50, minutes=45, floor=45, upside=48, usage=50)]
    available = [player(2, "Starter MID", "MID", 82, 78, fixture=80, start=90, minutes=80, floor=82, upside=85, usage=90)]
    result = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    assert result["action"] == "PRIORITY MOVE"
    assert result["immediate_delta"] > 0
    assert result["confidence"] == "HIGH"


def test_fit_future_led_player_is_consider_not_stash_swap():
    squad = [player(1, "Owned FWD", "FWD", 60, 55, floor=60, upside=55, usage=70)]
    available = [player(2, "Fit Future FWD", "FWD", 71, 78, floor=63, upside=82, availability=100, return_signal="fit", usage=72)]
    result = attach_replacement_analysis(available, squad, current_gameweek=0)[0]["replacement"]
    assert result["true_stash_candidate"] is False
    assert result["action"] == "CONSIDER"


def test_unavailable_future_led_player_can_be_stash_swap():
    squad = [player(1, "Owned FWD", "FWD", 60, 55, floor=60, upside=55, usage=70)]
    available = [player(2, "Recovering FWD", "FWD", 72, 82, floor=61, upside=88, availability=75, return_signal="near-return", usage=65)]
    result = attach_replacement_analysis(available, squad, current_gameweek=0)[0]["replacement"]
    assert result["true_stash_candidate"] is True
    assert result["action"] == "CONSIDER"


def test_preseason_guardrail_downgrades_marginal_swap():
    squad = [player(1, "Owned MID", "MID", 60, 60, fixture=55, start=75, minutes=68, floor=64, upside=72, usage=74)]
    available = [player(2, "Free MID", "MID", 72, 70, fixture=66, start=85, minutes=75, floor=68, upside=78, usage=84)]
    in_season = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    preseason = attach_replacement_analysis(available, squad, current_gameweek=0)[0]["replacement"]
    assert in_season["combined_delta"] == preseason["combined_delta"]
    assert preseason["action"] != "PRIORITY MOVE"
    assert preseason["preseason_guardrail"] is True


def test_low_sample_confidence_blocks_swap_now():
    squad = [player(1, "Owned FWD", "FWD", 50, 50, floor=50, upside=55, confidence=25, usage=55)]
    available = [player(2, "Free FWD", "FWD", 85, 82, fixture=80, start=90, minutes=82, floor=82, upside=90, confidence=25, usage=90)]
    result = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    assert result["confidence"] == "LOW"
    assert result["action"] != "PRIORITY MOVE"


def test_negative_upgrade_keeps_roster():
    squad = [player(1, "Strong FWD", "FWD", 82, 80, fixture=75, start=90, minutes=82, floor=84, upside=82, usage=90)]
    available = [player(2, "Depth FWD", "FWD", 55, 58, fixture=60, start=60, minutes=55, floor=58, upside=62, usage=60)]
    result = attach_replacement_analysis(available, squad, current_gameweek=2)[0]["replacement"]
    assert result["action"] == "HOLD / WATCH"
    assert result["combined_delta"] < 0


def test_only_one_priority_per_drop_and_order_does_not_change_leader():
    squad = [player(1, "Injured", "DEF", 40, 40, minutes=20, availability=25, floor=40, usage=20)]
    candidates = [player(i, f"Option {i}", "DEF", 90-i, 85, minutes=85, floor=85, upside=85, usage=90) for i in range(2, 6)]
    result = attach_replacement_analysis(candidates, squad, 2)
    assert [p["replacement"]["action"] for p in result].count("PRIORITY MOVE") == 1
    lead = next(p for p in result if p["replacement"]["action"] == "PRIORITY MOVE")
    assert all(p["replacement"]["lead_player_id"] == lead["player_id"] for p in result)
    assert sum(p["replacement"]["action"] == "ALTERNATIVE" for p in result) == 3
    reversed_result = attach_replacement_analysis(list(reversed(candidates)), squad, 2)
    assert next(p["player_id"] for p in reversed_result if p["replacement"]["action"] == "PRIORITY MOVE") == lead["player_id"]
    assert all("replacement" not in p for p in candidates)


def test_priority_requires_timing_fixtures_and_production_value():
    drop = player(1, "Owned", "DEF", 40, 40, minutes=85, floor=40, usage=20)
    target = player(2, "Target", "DEF", 90, 85, minutes=85, floor=85, upside=85, usage=90)
    assert attach_replacement_analysis([target], [drop], 2)[0]["replacement"]["action"] == "CONSIDER"
    drop["intelligence"]["availability_score"] = 25
    target["fixtures"] = []
    assert attach_replacement_analysis([target], [drop], 2)[0]["replacement"]["action"] == "CONSIDER"
    target["fixtures"] = [{"gameweek": 2, "matches": [{"difficulty": 3}]}]
    drop["intelligence"]["baseline_score"] = 95
    target["intelligence"]["baseline_score"] = 70
    assert attach_replacement_analysis([target], [drop], 2)[0]["replacement"]["action"] == "CONSIDER"


def test_h2h_cannot_promote_alternative_or_consider_into_a_move():
    from fpl_toolkit.h2h import _simulate_best_move
    candidate = player(2, "Tempting", "MID", 95, 95)
    for action in ("ALTERNATIVE", "CONSIDER", "HOLD / WATCH"):
        candidate["replacement"] = {"model": "v0.6.0", "action": action, "drop_player_id": 1}
        assert _simulate_best_move([candidate], [player(1, "Owned", "MID", 30, 30)], 2, {"starters": []}) is None
