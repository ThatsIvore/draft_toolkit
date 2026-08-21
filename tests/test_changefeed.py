from fpl_toolkit.changefeed import build_change_feed, capture_decision_state


def _player(player_id=1, name="Player", position="MID", *, role="MEDIUM", availability=100, minutes=70, recommendation="HOLD", waiver=None):
    row = {
        "player_id": player_id,
        "player": name,
        "club": "AAA",
        "team_code": 1,
        "position": position,
        "status": "a",
        "chance_next_round": availability,
        "news": "",
        "intelligence": {
            "availability_score": availability,
            "expected_minutes": minutes,
            "role_evidence": role,
            "health_trend": "stable",
            "recommendation": recommendation,
            "roster_score": 70,
            "stash_score": 68,
        },
    }
    if waiver:
        row["replacement"] = waiver
    return row


def _report(my_player=None, available=None, lineup_role="START", toughest=3, h2h="EVEN"):
    my_player = my_player or _player()
    available = available or []
    lineup = {
        "formation": "4-4-2",
        "starters": [my_player] if lineup_role == "START" else [],
        "bench": [my_player] if lineup_role == "BENCH" else [],
        "reserve_goalkeeper": None,
    }
    return {
        "generated_at": "2026-08-21T12:00:00+00:00",
        "current_gameweek": 1,
        "my_squad": [my_player],
        "available_players": available,
        "recommended_lineup": lineup,
        "schedule_planner": {"weakest_gameweek": toughest},
        "h2h_matchup": {"available": True, "matchup": {"signal": h2h, "start_score_edge": 0.0}},
    }


def test_change_feed_surfaces_material_role_availability_and_lineup_changes():
    before = _report(_player(role="MEDIUM", availability=100, minutes=70), lineup_role="BENCH")
    previous = capture_decision_state(before)
    current = _report(_player(role="HIGH", availability=75, minutes=82), lineup_role="START")

    feed = build_change_feed(previous, current)
    kinds = {item["kind"] for item in feed["items"]}

    assert feed["baseline"] is False
    assert "lineup_change" in kinds
    assert "availability" in kinds
    assert "role_change" in kinds
    assert 1 in feed["changed_player_ids"]


def test_change_feed_surfaces_waiver_upgrade_and_opponent_drop_without_manager_identity():
    old_free = _player(
        2,
        "Free Agent",
        "FWD",
        waiver={"action": "KEEP ROSTER", "drop_player": "Owned Fwd", "combined_delta": 1.0},
    )
    new_free = _player(
        2,
        "Free Agent",
        "FWD",
        waiver={"action": "SWAP NOW", "drop_player": "Owned Fwd", "combined_delta": 12.4},
    )
    previous = capture_decision_state(_report(available=[old_free]))
    current = _report(available=[new_free])
    activity = [{
        "type": "drop",
        "player_id": 2,
        "player": "Free Agent",
        "club": "AAA",
        "from_owner": "secret-id",
        "from_owner_name": "Secret Manager",
        "to_owner": None,
    }]

    feed = build_change_feed(previous, current, activity)
    kinds = {item["kind"] for item in feed["items"]}
    text = str(feed)

    assert "waiver_change" in kinds
    assert "opponent_drop" in kinds
    assert "Secret Manager" not in text
    assert "secret-id" not in text


def test_change_feed_suppresses_small_score_noise_and_tracks_planner_or_h2h_shift():
    previous = capture_decision_state(_report(toughest=2, h2h="EDGE"))
    current = _report(toughest=3, h2h="TRAIL")
    current["h2h_matchup"]["matchup"]["start_score_edge"] = -4.2

    feed = build_change_feed(previous, current)
    kinds = [item["kind"] for item in feed["items"]]

    assert kinds.count("planning_change") == 1
    assert kinds.count("h2h_change") == 1
    assert not any(kind in {"minutes_change", "availability", "role_change"} for kind in kinds)
